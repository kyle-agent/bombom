"""확정(Confirm) workflow — local git, screen-driven, no git knowledge required of users.

A *confirmation* is a reviewed change set sealed by an annotated git tag. Two kinds share one
gate + state machine + tag:
  - release : incremental device additions for a release (scope.release, e.g. R26.07)
  - build   : a new offering / subtree, often cloned, shipped on its own timeline (scope.paths)

State: draft → in-review → confirmed. Stored as `confirmations/<id>.yaml` so the manifest is
itself part of git's source of truth. All git ops (commit, tag) run in the backend via the
existing helpers — callers (API/CLI) never re-implement git. The gate reuses `validate_rack`
and `required_missing`; the change set / CAPEX mirror the BOM engine's per-placement logic.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..design import Issue, load_racks, validate_rack
from ..gitops import add_commit
from ..overlay import required_missing
from ..release import list_tags, tag_release

CONFIRMATIONS_DIR = "confirmations"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── manifest model ────────────────────────────────────────────────────────
class ConfirmScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    release: Optional[str] = None        # kind=release
    paths: list[str] = Field(default_factory=list)   # kind=build (under workspace root)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["release", "build"]
    scope: ConfirmScope = Field(default_factory=ConfirmScope)
    status: Literal["draft", "in-review", "confirmed"] = "draft"
    requester: Optional[str] = None
    approver: Optional[str] = None
    created_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    tag: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not _ID.match(v or "") or ".." in v:
            raise ValueError("id must match [A-Za-z0-9._-] (no leading dot, no '..')")
        return v


# ── exceptions ────────────────────────────────────────────────────────────
class ConfirmError(RuntimeError):
    """Workflow precondition failed (not found / wrong state / immutable tag)."""


class GateBlocked(Exception):
    """The confirm gate has errors — request/approve refused."""

    def __init__(self, gate: "GateResult"):
        self.gate = gate
        super().__init__("confirm gate failed")


# ── persistence ───────────────────────────────────────────────────────────
def confirmations_dir(root: Path) -> Path:
    return Path(root) / CONFIRMATIONS_DIR


def manifest_path(root: Path, conf_id: str) -> Path:
    if not _ID.match(conf_id or "") or ".." in conf_id:
        raise ConfirmError(f"invalid confirmation id: {conf_id!r}")
    return confirmations_dir(root) / f"{conf_id}.yaml"


def load_confirmation(root: Path, conf_id: str) -> Optional[Confirmation]:
    p = manifest_path(root, conf_id)
    if not p.exists():
        return None
    return Confirmation.model_validate(yaml.safe_load(p.read_text()) or {})


def list_confirmations(root: Path) -> list[Confirmation]:
    out: list[Confirmation] = []
    d = confirmations_dir(root)
    if d.exists():
        for p in sorted(d.glob("*.y*ml")):
            try:
                out.append(Confirmation.model_validate(yaml.safe_load(p.read_text()) or {}))
            except Exception:  # noqa: BLE001 — a malformed manifest must not break the list
                continue
    return out


def write_confirmation(root: Path, conf: Confirmation) -> Path:
    p = manifest_path(root, conf.id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(conf.model_dump(), allow_unicode=True, sort_keys=False))
    os.replace(tmp, p)
    return p


# ── gate + change set ─────────────────────────────────────────────────────
@dataclass
class ChangeItem:
    rack_id: str
    rack_path: str
    name: str
    device: Optional[str]
    category: str
    release: Optional[str]
    qty: int
    unit_cost: Optional[int]      # KRW; None = unpriced

    @property
    def subtotal(self) -> int:
        return (self.unit_cost or 0) * self.qty


@dataclass
class GateResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    items: list[ChangeItem] = field(default_factory=list)
    affected_racks: list[str] = field(default_factory=list)
    capex: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _scope_roots(root: Path, conf: Confirmation) -> list[Path]:
    root = Path(root).resolve()
    if conf.kind == "build":
        roots: list[Path] = []
        for rel in conf.scope.paths:
            cand = (root / rel).resolve()
            if cand == root or root in cand.parents:   # stay under workspace
                roots.append(cand)
        return roots
    return [root]   # release: walk the whole tree, filter by release


def run_gate(ws, conf: Confirmation) -> GateResult:
    """Validate the affected racks and build the change set. Reuses validate_rack +
    required_missing + the price book; mirrors the BOM engine's per-placement accounting."""
    res = GateResult()
    rel = conf.scope.release if conf.kind == "release" else None
    as_of = date.today()
    seen: set[str] = set()
    seen_type_slugs: set[str] = set()        # device_type-level meta checked once per slug

    for scope_root in _scope_roots(ws.root, conf):
        loaded = load_racks(scope_root)
        res.errors.extend(i for i in loaded.issues if i.level == "error")
        for lr in loaded.racks:
            if lr.path in seen:
                continue
            in_scope = [(i, p) for i, p in enumerate(lr.design.placements)
                        if rel is None or p.release == rel]
            if rel is not None and not in_scope:
                continue  # rack has nothing in this release
            seen.add(lr.path)
            res.affected_racks.append(lr.path)
            role = lr.hierarchy.get("rack_type")     # purpose comes from the Rack-Type dir
            scope_idx = {i for i, _ in in_scope}

            rack_issues = validate_rack(lr, ws.catalog)
            # rack-level errors (index None) always block; per-placement errors block only when
            # they hit a placement in this confirmation's scope (don't let another release's bad
            # placement block this one).
            res.errors.extend(i for i in rack_issues if i.index is None or i.index in scope_idx)
            skip = {i.index for i in rack_issues if i.index is not None and i.level == "error"}

            for idx, pl in in_scope:
                if idx in skip:
                    continue
                device = ws.catalog.get_device_type(pl.device)
                if device is None:
                    continue  # already reported by validate_rack
                cat = ws.categories.get(pl.device, model=device.model,
                                        manufacturer=device.manufacturer)
                type_vals = ws.type_meta.get(pl.device)
                merged = {**type_vals, **(pl.meta or {})}
                for key in required_missing(ws.fields, merged, applies_to="placement",
                                            category=cat, role=role):
                    res.errors.append(Issue(lr.path, "error", f"{pl.device} 메타 필수 누락: {key}", idx))
                if pl.device not in seen_type_slugs:
                    seen_type_slugs.add(pl.device)
                    for key in required_missing(ws.fields, type_vals, applies_to="device_type",
                                                category=cat):
                        res.errors.append(Issue(lr.path, "error", f"{pl.device} 타입 메타 필수 누락: {key}"))
                price = ws.pricebook.lookup(as_of, slug=pl.device, part_number=device.part_number)
                unit = price.unit_cost if price else None
                if unit is None:
                    res.warnings.append(Issue(lr.path, "warn", f"가격 미등록: {pl.device}", idx))
                res.items.append(ChangeItem(lr.rack_id, lr.path, device.model, pl.device, cat,
                                            pl.release, pl.qty, unit))
                if unit is not None:
                    res.capex += unit * pl.qty

            for ci in lr.design.custom_line_items:
                if rel is not None and ci.release != rel:
                    continue
                if ci.unit_cost is None:
                    res.warnings.append(Issue(lr.path, "warn", f"가격 미등록(커스텀): {ci.name}"))
                res.items.append(ChangeItem(lr.rack_id, lr.path, ci.name, None, ci.category,
                                            ci.release, ci.qty, ci.unit_cost))
                if ci.unit_cost is not None:
                    res.capex += ci.unit_cost * ci.qty

    return res


def gate_to_dict(gate: GateResult) -> dict:
    return {
        "ok": gate.ok,
        "errors": [vars(i) for i in gate.errors],
        "warnings": [vars(i) for i in gate.warnings],
        "affected_racks": gate.affected_racks,
        "capex": gate.capex,
        "items": [{**vars(i), "subtotal": i.subtotal} for i in gate.items],
    }


# ── high-level operations (write + commit, approve also tags) ──────────────
def request(ws, *, conf_id: str, kind: str, scope, requester: Optional[str] = None,
            message: Optional[str] = None) -> tuple[Confirmation, GateResult, Optional[str]]:
    """Run the gate; on pass, write the manifest as in-review and commit. Raises GateBlocked
    if the gate has errors (nothing written)."""
    scope = scope if isinstance(scope, ConfirmScope) else ConfirmScope.model_validate(scope or {})
    conf = Confirmation(id=conf_id, kind=kind, scope=scope, requester=requester)
    existing = load_confirmation(ws.root, conf_id)
    if existing and existing.status == "confirmed":
        raise ConfirmError(f"이미 확정됨(재확정 불가): {conf_id}")
    gate = run_gate(ws, conf)
    if not gate.ok:
        raise GateBlocked(gate)
    conf.status = "in-review"
    conf.created_at = (existing.created_at if existing else None) or _now()
    path = write_confirmation(ws.root, conf)
    sha = add_commit([path], message or f"confirm request {conf_id}", cwd=Path(ws.root))
    return conf, gate, sha


def approve(ws, *, conf_id: str, approver: Optional[str] = None,
            message: Optional[str] = None) -> tuple[Confirmation, GateResult, Optional[str], str]:
    """Approve an in-review confirmation: re-run the gate, mark confirmed, commit, and seal
    with an annotated tag (= the confirmation id). Raises on wrong state / re-tag / gate fail."""
    conf = load_confirmation(ws.root, conf_id)
    if conf is None:
        raise ConfirmError(f"확정요청 없음: {conf_id}")
    if conf.status != "in-review":
        raise ConfirmError(f"in-review 상태가 아님 (status={conf.status}): {conf_id}")
    tag = conf.id
    if tag in list_tags(cwd=Path(ws.root)):
        raise ConfirmError(f"이미 태그 존재(재확정 불가): {tag}")
    gate = run_gate(ws, conf)
    if not gate.ok:
        raise GateBlocked(gate)
    conf.status = "confirmed"
    conf.approver = approver
    conf.confirmed_at = _now()
    conf.tag = tag
    path = write_confirmation(ws.root, conf)
    sha = add_commit([path], message or f"confirm {conf_id}", cwd=Path(ws.root))
    try:
        tag_release(tag, message=f"bombom confirm {conf_id} ({conf.kind})", cwd=Path(ws.root))
    except RuntimeError as exc:
        # The seal (tag) failed — roll the manifest back to in-review so the confirmation is
        # not wedged as confirmed-but-unsealed; it can be approved again once the cause is fixed.
        conf.status, conf.approver, conf.confirmed_at, conf.tag = "in-review", None, None, None
        write_confirmation(ws.root, conf)
        add_commit([path], f"revert confirm {conf_id} (tag failed)", cwd=Path(ws.root))
        raise ConfirmError(f"태그 생성 실패, 확정 취소됨: {exc}") from exc
    return conf, gate, sha, tag


def detail(ws, conf_id: str) -> Optional[tuple[Confirmation, GateResult]]:
    conf = load_confirmation(ws.root, conf_id)
    if conf is None:
        return None
    return conf, run_gate(ws, conf)


__all__ = [
    "Confirmation", "ConfirmScope", "ConfirmError", "GateBlocked", "GateResult", "ChangeItem",
    "run_gate", "gate_to_dict", "request", "approve", "detail",
    "load_confirmation", "list_confirmations", "write_confirmation", "confirmations_dir",
]
