"""Device candidate pool (선정 장비 후보풀) — the curated shortlist a designer places from.

Workspace-global: `candidates/pool.yaml` lists candidate device slugs (+ an optional note).
Price stays separate in the pricing overlay (ADR spec-cost-separation), so a candidate can
exist *before* its price is known ("가격 미정 후보"). Selecting price/extra-info from the
candidate screen writes the pricing overlay (`pricing/manual.yaml`) and the pool note.

Reads/writes files only; the API layer commits the returned paths (mirrors scaffold/hierarchy).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

CANDIDATES_DIR = "candidates"
POOL_FILE = "pool.yaml"
PRICING_MANUAL = "manual.yaml"          # pricing/manual.yaml — UI-entered prices


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    note: Optional[str] = None
    added_at: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)   # org-defined candidate fields (meta/fields.yaml)


def pool_path(root: Path) -> Path:
    return Path(root) / CANDIDATES_DIR / POOL_FILE


def load_pool(root: Path) -> list[Candidate]:
    p = pool_path(root)
    if not p.exists():
        return []
    try:
        doc = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError:
        return []                     # a corrupt pool must degrade, not 500
    out = []
    for raw in doc.get("candidates", []):
        try:
            out.append(Candidate.model_validate(raw))
        except Exception:  # noqa: BLE001 — a malformed row must not break the pool
            continue
    return out


def _write_pool(root: Path, items: list[Candidate]) -> Path:
    p = pool_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = []
    for c in items:
        d = c.model_dump(exclude_none=True)
        if not d.get("meta"):           # never persist an empty meta dict
            d.pop("meta", None)
        body.append(d)
    p.write_text(yaml.safe_dump({"candidates": body}, allow_unicode=True, sort_keys=False))
    return p


def add_candidate(root: Path, slug: str, note: Optional[str] = None) -> tuple[Candidate, Path]:
    items = load_pool(root)
    if any(c.slug == slug for c in items):
        raise FileExistsError(f"이미 후보입니다: {slug}")
    cand = Candidate(slug=slug, note=(note or None), added_at=date.today().isoformat())
    items.append(cand)
    return cand, _write_pool(root, items)


def remove_candidate(root: Path, slug: str) -> Path:
    items = load_pool(root)
    kept = [c for c in items if c.slug != slug]
    if len(kept) == len(items):
        raise KeyError(slug)
    return _write_pool(root, kept)


def set_note(root: Path, slug: str, note: Optional[str]) -> Path:
    items = load_pool(root)
    hit = next((c for c in items if c.slug == slug), None)
    if hit is None:
        raise KeyError(slug)
    hit.note = (note or None)
    return _write_pool(root, items)


def set_meta(root: Path, slug: str, meta: dict[str, Any]) -> Path:
    """Replace a candidate's org-defined fields. Empty values are dropped, so clearing a field
    removes it (mirrors how placement meta is cleared in the editor)."""
    items = load_pool(root)
    hit = next((c for c in items if c.slug == slug), None)
    if hit is None:
        raise KeyError(slug)
    hit.meta = {k: v for k, v in (meta or {}).items() if v not in (None, "", False)}
    return _write_pool(root, items)


def set_price(root: Path, slug: str, unit_cost: int, *, source: Optional[str] = None) -> Path:
    """Upsert a KRW price for `slug` into pricing/manual.yaml (kept out of catalog/design)."""
    p = Path(root) / "pricing" / PRICING_MANUAL
    doc = (yaml.safe_load(p.read_text()) if p.exists() else None) or {}
    entries = doc.get("entries", [])
    hit = next((e for e in entries if e.get("slug") == slug), None)
    if hit is None:
        hit = {"slug": slug}
        entries.append(hit)
    hit["unit_cost"] = int(unit_cost)
    hit["source"] = source or "candidate screen"
    hit["valid_from"] = date.today().isoformat()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False))
    return p
