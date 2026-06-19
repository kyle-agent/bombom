"""FastAPI app — read-only views over a workspace. Writing base data is via the CLI."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ..design import LoadedRack, RackDesign, load_racks, parse_hierarchy, validate_rack
from ..design.writer import write_rack
from ..export import build_data, inject
from ..gitops import add_commit
from ..render import rack_elevation_svg
from ..workspace import Workspace

_VIEWER = Path(__file__).resolve().parents[2] / "web" / "viewer.html"


def _search_catalog(db_path: str, q: str, limit: int = 50) -> list[dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT kind, manufacturer, model, slug, u_height FROM specs "
            "WHERE kind='device' AND (model LIKE ? OR slug LIKE ?) ORDER BY model LIMIT ?",
            (f"%{q}%", f"%{q}%", limit),
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
    def catalog_search(q: str = "", category: Optional[str] = None, limit: int = 50):
        rows = _search_catalog(ws.catalog.db_path, q, min(max(limit, 1), 500))
        for r in rows:
            r["category"] = ws.categories.get(r["slug"], model=r["model"], manufacturer=r["manufacturer"])
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

    return app


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
