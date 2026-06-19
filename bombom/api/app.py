"""FastAPI app — read-only views over a workspace. Writing base data is via the CLI."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ..design import load_racks
from ..export import build_data
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
            blob = "/*__BOMBOM_DATA__*/ " + json.dumps(payload, ensure_ascii=False) + " /*__END__*/"
            html = re.sub(r"/\*__BOMBOM_DATA__\*/.*?/\*__END__\*/", lambda _: blob,
                          _VIEWER.read_text(), count=1, flags=re.S)
            return HTMLResponse(html)
        except Exception:
            return HTMLResponse(_VIEWER.read_text())

    @app.get("/api/tree")
    def tree(path: str = "offerings"):
        return build_data(ws, _resolve(root, path))["tree"]

    @app.get("/api/catalog/search")
    def catalog_search(q: str = "", category: Optional[str] = None, limit: int = 50):
        rows = _search_catalog(ws.catalog.db_path, q, limit)
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

    return app


def _resolve(root: Path | str, path: str) -> Path:
    # Prefer root-relative (the workspace) before an ambiguous cwd-relative match.
    rooted = Path(root) / path
    if rooted.exists():
        return rooted
    return Path(path)
