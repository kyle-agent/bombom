"""FastAPI app — read-only views over a workspace. Writing base data is via the CLI."""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from ..confirm import ConfirmError, ConfirmScope, GateBlocked
from ..confirm import approve as confirm_approve
from ..confirm import detail as confirm_detail
from ..confirm import gate_to_dict
from ..confirm import list_confirmations
from ..bom import PriceBook
from ..candidates import (
    Candidate,
    add_candidate,
    load_pool,
    remove_candidate,
    set_note,
    set_price,
)
from ..confirm import request as confirm_request
from ..dashboard import build_dashboard
from ..design import LoadedRack, RackDesign, load_racks, parse_hierarchy, validate_rack
from ..design.writer import write_rack
from ..export import build_data, inject
from ..gitops import add_commit
from ..hierarchy import list_hierarchy
from ..render import rack_elevation_svg
from ..report import investment_csv, investment_rows, placed_rows
from ..scaffold import (
    scaffold_offering,
    scaffold_rack,
    scaffold_rack_type,
    scaffold_region,
    scaffold_zone,
)
from ..workspace import Workspace

_VIEWER = Path(__file__).resolve().parents[2] / "web" / "viewer.html"

# Org-node identifiers become directory/file names — keep them filesystem-safe and traversal-proof.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _safe_id(value: str, field: str) -> str:
    value = (value or "").strip()
    if not _SAFE_ID.match(value) or ".." in value:
        raise ValueError(f"{field} must match [A-Za-z0-9._-] (no leading dot, no '..')")
    return value


class NewRackBody(BaseModel):
    """Create a rack under an existing Offering→Region→Zone→Rack-Type path."""

    offering: str
    region: str
    zone: str
    rack_type: str
    rack: str
    rack_model: str  # catalog RackTypeSpec slug, e.g. vertiv-vr3300

    @field_validator("offering", "region", "zone", "rack_type", "rack")
    @classmethod
    def _check_id(cls, v: str, info) -> str:
        return _safe_id(v, info.field_name)

    @field_validator("rack_model")
    @classmethod
    def _check_model(cls, v: str) -> str:
        return _safe_id(v, "rack_model")


class ConfirmRequestBody(BaseModel):
    """Open/refresh a confirmation: run the gate, write it as in-review."""

    id: str
    kind: Literal["release", "build"]
    scope: ConfirmScope = Field(default_factory=ConfirmScope)
    requester: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        return _safe_id(v, "id")


class ConfirmApproveBody(BaseModel):
    approver: Optional[str] = None


class HierarchyBody(BaseModel):
    """Create one base-data node (기준정보) — offering / region / zone / rack_type."""

    level: Literal["offering", "region", "zone", "rack_type"]
    offering: str
    region: Optional[str] = None
    zone: Optional[str] = None
    rack_type: Optional[str] = None
    name: Optional[str] = None


class CandidateAddBody(BaseModel):
    slug: str
    note: Optional[str] = Field(default=None, max_length=500)


class CandidateUpdateBody(BaseModel):
    """Edit a candidate from the selection screen: price and/or extra note."""

    note: Optional[str] = Field(default=None, max_length=500)
    unit_cost: Optional[int] = Field(default=None, ge=0)
    source: Optional[str] = Field(default=None, max_length=200)


def _search_catalog(db_path: str, q: str, limit: int = 50, kind: str = "device") -> list[dict]:
    if kind not in ("device", "rack", "module"):
        kind = "device"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT kind, manufacturer, model, slug, u_height FROM specs "
            "WHERE kind = ? AND (model LIKE ? OR slug LIKE ?) ORDER BY model LIMIT ?",
            (kind, f"%{q}%", f"%{q}%", limit),
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def create_app(root: Path | str = ".", *, db_path: Path | None = None) -> FastAPI:
    ws = Workspace.open(root, db_path=db_path)
    app = FastAPI(title="bombom", docs_url="/api/docs")

    @app.get("/", response_class=HTMLResponse)
    def index(path: str = "offerings"):
        # Serve the viewer with live data baked in (falls back to the template's sample).
        if not _VIEWER.exists():
            return HTMLResponse("<h1>viewer not built</h1>", status_code=500)
        try:
            payload = build_data(ws, _resolve(root, path), is_mock=False)
            return HTMLResponse(inject(_VIEWER.read_text(), payload))
        except Exception:
            logging.exception("index: build_data failed for path=%s", path)
            return HTMLResponse(_VIEWER.read_text())

    @app.get("/edit", response_class=HTMLResponse)
    def editor():
        editor_html = _VIEWER.parent / "editor.html"
        if not editor_html.exists():
            return HTMLResponse("<h1>editor not built</h1>", status_code=500)
        return HTMLResponse(editor_html.read_text())

    @app.get("/api/tree")
    def tree(path: str = "offerings"):
        return build_data(ws, _resolve(root, path))["tree"]

    @app.get("/api/catalog/search")
    def catalog_search(q: str = "", category: Optional[str] = None, limit: int = 50,
                       kind: str = "device", pool: bool = False):
        if pool and kind == "device":
            # placement source = the curated candidate pool only (Phase 3), with entered prices
            return _pool_search(q, category, min(max(limit, 1), 500))
        rows = _search_catalog(ws.catalog.db_path, q, min(max(limit, 1), 500), kind=kind)
        if kind == "device":
            for r in rows:
                r["category"] = ws.categories.get(r["slug"], model=r["model"],
                                                  manufacturer=r["manufacturer"])
            if category:
                rows = [r for r in rows if r["category"] == category]
        return rows

    @app.get("/api/bom")
    def bom(path: str = "offerings", release: Optional[str] = None):
        data = build_data(ws, _resolve(root, path), release=release)
        return JSONResponse({"current_release": data["current_release"], **data["bom"]})

    @app.get("/api/rack/elevation.svg")
    def rack_svg(path: str, release: Optional[str] = None):
        loaded = load_racks(_resolve(root, path))
        if not loaded.racks:
            raise HTTPException(404, "no rack found at path")
        svg = rack_elevation_svg(loaded.racks[0].design, ws.catalog,
                                 categories=ws.categories, highlight_release=release)
        return Response(svg, media_type="image/svg+xml")

    @app.get("/api/rack")
    def get_rack(path: str):
        data = build_data(ws, _resolve(root, path))
        if not data["racks"]:
            raise HTTPException(404, "no rack at path")
        return {
            "rack": next(iter(data["racks"].values())),
            "fields": data["fields"],
            "releases": data["releases"],
            "current_release": data["current_release"],
        }

    @app.put("/api/rack")
    def put_rack(body: RackDesign, path: str, message: str = ""):
        target = _resolve_rack_write(root, path)
        loaded = LoadedRack(rack_id=target.stem, path=str(target),
                            hierarchy=parse_hierarchy(target), design=body)
        errors = [i for i in validate_rack(loaded, ws.catalog) if i.level == "error"]
        if errors:
            raise HTTPException(400, {"issues": [vars(i) for i in errors]})
        write_rack(target, body)
        msg = (message or f"edit {target.stem}").replace("\n", " ").strip()[:500] or f"edit {target.stem}"
        sha = add_commit([target], msg, cwd=Path(root))
        data = build_data(ws, target)
        return {
            "ok": True, "commit": sha,
            "issues": data["bom"]["issues"],          # non-blocking (e.g. meta required missing)
            "rack": next(iter(data["racks"].values()), None),
        }

    @app.post("/api/rack/new")
    def new_rack(body: NewRackBody, message: str = ""):
        if ws.catalog.get_rack_type(body.rack_model) is None:
            raise HTTPException(400, f"unknown rack_model: {body.rack_model}")
        base = Path(root)
        zone_dir = (base / "offerings" / body.offering / "regions" / body.region
                    / "zones" / body.zone)
        if not zone_dir.is_dir():
            raise HTTPException(404, "zone does not exist (scaffold the hierarchy first)")
        target = zone_dir / "rack-types" / body.rack_type / "racks" / f"{body.rack}.yaml"
        if target.exists():
            raise HTTPException(409, f"rack already exists: {body.rack}")
        try:
            scaffold_rack(base, body.offering, body.region, body.zone, body.rack_type,
                          body.rack, rack_model_slug=body.rack_model)
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
        msg = (message or f"add rack {body.rack}").replace("\n", " ").strip()[:500] or f"add rack {body.rack}"
        sha = add_commit([target], msg, cwd=base)
        rel = target.relative_to(base).as_posix()
        return {"ok": True, "commit": sha, "path": rel, "rack": body.rack}

    # ── confirm workflow (release + build) ────────────────────────────────
    @app.post("/api/confirm/request")
    def confirm_request_ep(body: ConfirmRequestBody):
        _validate_scope(root, body.kind, body.scope)
        try:
            conf, gate, sha = confirm_request(ws, conf_id=body.id, kind=body.kind,
                                              scope=body.scope, requester=body.requester)
        except GateBlocked as gb:
            raise HTTPException(400, {"gate": gate_to_dict(gb.gate)}) from gb
        except ConfirmError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True, "commit": sha, "confirmation": conf.model_dump(),
                "gate": gate_to_dict(gate)}

    @app.post("/api/confirm/approve")
    def confirm_approve_ep(body: ConfirmApproveBody, id: str):
        try:
            conf, gate, sha, tag = confirm_approve(ws, conf_id=id, approver=body.approver)
        except GateBlocked as gb:
            raise HTTPException(400, {"gate": gate_to_dict(gb.gate)}) from gb
        except ConfirmError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True, "commit": sha, "tag": tag, "confirmation": conf.model_dump(),
                "gate": gate_to_dict(gate)}

    @app.get("/api/confirm")
    def confirm_list_ep():
        return [c.model_dump() for c in list_confirmations(ws.root)]

    @app.get("/api/confirm/{id}")
    def confirm_detail_ep(id: str):
        got = confirm_detail(ws, id)
        if got is None:
            raise HTTPException(404, "confirmation not found")
        conf, gate = got
        return {"confirmation": conf.model_dump(), "gate": gate_to_dict(gate)}

    # ── reports + dashboard (P2/P3) ───────────────────────────────────────
    @app.get("/api/report/invest.csv")
    def report_invest_csv(release: str, path: str = "offerings"):
        if not _SAFE_ID.match(release or ""):   # also keeps `release` safe in the filename header
            raise HTTPException(400, "invalid release")
        rows = investment_rows(ws, _resolve(root, path), release)
        csv_text = investment_csv(rows, release=release)
        return Response(csv_text, media_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="invest-{release}.csv"'})

    @app.get("/api/dashboard")
    def dashboard_ep(path: str = "offerings"):
        return build_dashboard(ws, _resolve(root, path))

    @app.get("/api/placed")
    def placed_ep(path: str = "offerings", release: Optional[str] = None):
        rows = placed_rows(ws, _resolve(root, path), release=release)
        return {
            "rows": rows,
            "total_capex": sum(r["subtotal"] for r in rows),
            "qty": sum(r["qty"] for r in rows),
            "unpriced": sum(1 for r in rows if not r["priced"]),
            "releases": sorted({r["release"] for r in rows if r["release"]}),
        }

    @app.get("/placed", response_class=HTMLResponse)
    def placed_page():
        page = _VIEWER.parent / "placed.html"
        if not page.exists():
            return HTMLResponse("<h1>placed page not built</h1>", status_code=500)
        return HTMLResponse(page.read_text())

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_page():
        page = _VIEWER.parent / "dashboard.html"
        if not page.exists():
            return HTMLResponse("<h1>dashboard not built</h1>", status_code=500)
        return HTMLResponse(page.read_text())

    # ── base-data hierarchy management (기준정보 / Rack-Type) ──────────────
    @app.get("/api/hierarchy")
    def hierarchy_list():
        return list_hierarchy(Path(root))

    @app.post("/api/hierarchy")
    def hierarchy_create(body: HierarchyBody):
        base = Path(root)
        try:
            off = _safe_id(body.offering, "offering")
            reg = _safe_id(body.region, "region") if body.region else None
            zon = _safe_id(body.zone, "zone") if body.zone else None
            rt = _safe_id(body.rack_type, "rack_type") if body.rack_type else None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        name = ((body.name or "").strip()[:200]) or None

        try:
            if body.level == "offering":
                target = scaffold_offering(base, off, name=name)
            elif body.level == "region":
                _require(reg, "region")
                _require_dir(base / "offerings" / off, "offering")
                target = scaffold_region(base, off, reg, name=name)
            elif body.level == "zone":
                _require(reg, "region")
                _require(zon, "zone")
                _require_dir(base / "offerings" / off / "regions" / reg, "region")
                target = scaffold_zone(base, off, reg, zon, name=name)
            else:  # rack_type
                _require(reg, "region")
                _require(zon, "zone")
                _require(rt, "rack_type")
                _require_dir(base / "offerings" / off / "regions" / reg / "zones" / zon, "zone")
                target = scaffold_rack_type(base, off, reg, zon, rt, name=name)
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc

        sha = add_commit([target], f"add {body.level} {target.parent.name}", cwd=base)
        return {"ok": True, "commit": sha,
                "path": target.relative_to(base).as_posix(),
                "hierarchy": list_hierarchy(base)}

    @app.get("/manage", response_class=HTMLResponse)
    def manage_page():
        page = _VIEWER.parent / "manage.html"
        if not page.exists():
            return HTMLResponse("<h1>manage page not built</h1>", status_code=500)
        return HTMLResponse(page.read_text())

    # ── device candidate pool (후보풀 + 가격/부가정보) ──────────────────────
    def _refresh_prices():
        # the pool/dashboard/report/confirm views all read ws.pricebook — keep it live after a
        # price write so a just-entered price shows up everywhere without a server restart.
        ws.pricebook = PriceBook.load(Path(root) / "pricing")

    def _candidate_row(cand) -> dict:
        dev = ws.catalog.get_device_type(cand.slug)
        price = ws.pricebook.lookup(date.today(), slug=cand.slug,
                                    part_number=dev.part_number if dev else None) if dev else None
        return {
            "slug": cand.slug,
            "model": dev.model if dev else None,
            "manufacturer": dev.manufacturer if dev else None,
            "in_catalog": dev is not None,
            "category": ws.categories.get(cand.slug, model=dev.model, manufacturer=dev.manufacturer)
            if dev else "other",
            "note": cand.note,
            "added_at": cand.added_at,
            "unit_cost": price.unit_cost if price else None,
            "priced": price is not None,
        }

    def _pool_search(q: str, category: Optional[str], limit: int) -> list[dict]:
        ql = (q or "").strip().lower()
        out = []
        for c in load_pool(Path(root)):
            dev = ws.catalog.get_device_type(c.slug)
            if dev is None:
                continue
            cat = ws.categories.get(c.slug, model=dev.model, manufacturer=dev.manufacturer)
            if category and cat != category:
                continue
            hay = f"{dev.model} {c.slug} {dev.manufacturer or ''}".lower()
            if ql and ql not in hay:
                continue
            price = ws.pricebook.lookup(date.today(), slug=c.slug, part_number=dev.part_number)
            out.append({"slug": c.slug, "model": dev.model, "manufacturer": dev.manufacturer,
                        "u_height": dev.u_height, "category": cat,
                        "unit_cost": price.unit_cost if price else None,
                        "priced": price is not None})
        return out[:limit]

    @app.get("/api/candidates")
    def candidates_list():
        return [_candidate_row(c) for c in load_pool(Path(root))]

    @app.post("/api/candidates")
    def candidates_add(body: CandidateAddBody):
        slug = _safe_slug(body.slug)
        if ws.catalog.get_device_type(slug) is None:
            raise HTTPException(404, f"unknown device: {slug}")
        try:
            cand, path = add_candidate(Path(root), slug, body.note)
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
        add_commit([path], f"candidate add {slug}", cwd=Path(root))
        return {"ok": True, "candidate": _candidate_row(cand)}

    @app.put("/api/candidates/{slug}")
    def candidates_update(slug: str, body: CandidateUpdateBody):
        slug = _safe_slug(slug)
        if not any(c.slug == slug for c in load_pool(Path(root))):
            raise HTTPException(404, f"not a candidate: {slug}")
        paths = []
        try:
            if body.note is not None:
                paths.append(set_note(Path(root), slug, body.note))
            if body.unit_cost is not None:
                paths.append(set_price(Path(root), slug, body.unit_cost, source=body.source))
        except KeyError as exc:
            raise HTTPException(404, f"not a candidate: {slug}") from exc
        if not paths:
            raise HTTPException(400, "nothing to update (note or unit_cost required)")
        add_commit(paths, f"candidate update {slug}", cwd=Path(root))
        if body.unit_cost is not None:
            _refresh_prices()
        cand = next((c for c in load_pool(Path(root)) if c.slug == slug), Candidate(slug=slug))
        return {"ok": True, "candidate": _candidate_row(cand)}

    @app.delete("/api/candidates/{slug}")
    def candidates_delete(slug: str):
        slug = _safe_slug(slug)
        try:
            path = remove_candidate(Path(root), slug)
        except KeyError as exc:
            raise HTTPException(404, f"not a candidate: {slug}") from exc
        add_commit([path], f"candidate remove {slug}", cwd=Path(root))
        return {"ok": True, "slug": slug}

    @app.get("/candidates", response_class=HTMLResponse)
    def candidates_page():
        page = _VIEWER.parent / "candidates.html"
        if not page.exists():
            return HTMLResponse("<h1>candidates page not built</h1>", status_code=500)
        return HTMLResponse(page.read_text())

    return app


def _safe_slug(value: str) -> str:
    try:
        return _safe_id(value, "slug")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _require(value, field: str) -> None:
    if not value:
        raise HTTPException(400, f"{field} is required for this level")


def _require_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise HTTPException(404, f"parent {label} does not exist: {path.name}")


def _validate_scope(root: Path | str, kind: str, scope: ConfirmScope) -> None:
    if kind == "release":
        if not scope.release:
            raise HTTPException(400, "release kind requires scope.release")
    else:  # build
        if not scope.paths:
            raise HTTPException(400, "build kind requires scope.paths")
        for rel in scope.paths:
            _resolve(root, rel)   # under-root + existence guard (400/404)


def _resolve_rack_write(root: Path | str, path: str) -> Path:
    base = Path(root).resolve()
    cand = (base / path).resolve()
    if cand != base and base not in cand.parents:
        raise HTTPException(400, "path outside workspace")
    if cand.suffix not in (".yaml", ".yml") or cand.parent.name != "racks":
        raise HTTPException(400, "target must be a .../racks/<rack>.yaml")
    if not cand.parent.exists():
        raise HTTPException(404, "racks directory does not exist (scaffold the hierarchy first)")
    return cand


def _resolve(root: Path | str, path: str) -> Path:
    # Resolve under the workspace root and reject traversal outside it (read-only API,
    # but we still don't want arbitrary-path reads from a query string).
    base = Path(root).resolve()
    cand = (base / path).resolve()
    if cand != base and base not in cand.parents:
        raise HTTPException(400, "path outside workspace")
    if not cand.exists():
        raise HTTPException(404, "path not found")
    return cand
