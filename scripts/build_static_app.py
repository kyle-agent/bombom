#!/usr/bin/env python3
"""Bake the WHOLE bombom app into a backend-free static bundle for GitHub Pages.

Approach: run the real FastAPI app (TestClient) against a filled showcase workspace, capture
every GET API response, then for each page (web/*.html) rewrite inter-page links for static
hosting and inject a shim that (a) serves captured GET responses via a `fetch` override,
(b) blocks writes with a toast, (c) shows a read-only banner. The viewer is baked with data
via `bombom export`. A landing index.html links every screen.

    python scripts/build_static_app.py --out public      # writes public/*.html
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from showcase import seed as seed_showcase  # noqa: E402

from bombom.api import create_app  # noqa: E402
from bombom.export import build_data, inject  # noqa: E402
from bombom.workspace import Workspace  # noqa: E402


# Minimal ASGI GET client — drives the real FastAPI app without TestClient (which pulls in
# httpx/httpx2, a version-fragile test dep not installed for the Pages build).
class _Resp:
    def __init__(self, status: int, ct: str, text: str):
        self.status_code, self._ct, self.text = status, ct, text
        self.headers = {"content-type": ct}

    def json(self):
        return json.loads(self.text)


class _AsgiClient:
    def __init__(self, app):
        self.app = app

    def get(self, path: str, params: dict | None = None) -> _Resp:
        qs = urlencode(params or {}).encode()
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": qs, "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80), "client": ("127.0.0.1", 50000),
        }
        out: list[dict] = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(m):
            out.append(m)

        try:
            asyncio.run(self.app(scope, receive, send))
        except Exception as exc:  # noqa: BLE001 — record as 500 like raise_server_exceptions=False
            return _Resp(500, "text/plain", repr(exc))
        status, ct, body = 500, "application/json", b""
        for m in out:
            if m["type"] == "http.response.start":
                status = m["status"]
                hdrs = {k.decode().lower(): v.decode() for k, v in m.get("headers", [])}
                ct = hdrs.get("content-type", ct)
            elif m["type"] == "http.response.body":
                body += m.get("body", b"")
        return _Resp(status, ct, body.decode("utf-8"))

REPO = Path(__file__).resolve().parent.parent
WEB = REPO / "web"

# in-app route → static file (for link rewriting). "/" is the viewer.
ROUTES = {
    "/": "viewer.html", "/edit": "editor.html", "/placed": "placed.html",
    "/dashboard": "dashboard.html", "/diff": "diff.html", "/health": "health.html",
    "/search": "search.html", "/layout": "layout.html", "/manage": "manage.html",
    "/candidates": "candidates.html", "/home": "index.html", "/zone": "zone.html",
    "/summary": "summary.html",
}
PAGES = ["viewer.html", "editor.html", "placed.html", "dashboard.html", "diff.html",
         "health.html", "search.html", "layout.html", "manage.html", "candidates.html",
         "home.html", "zone.html", "summary.html"]


def _key(pathname: str, params: dict) -> str:
    """Stable cache key: pathname + sorted decoded params (matches the JS shim)."""
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{pathname}|{qs}"


def _node_paths(root: Path) -> list[str]:
    paths = ["offerings"]
    for off in sorted((root / "offerings").glob("*/")):
        if not off.is_dir():
            continue
        paths.append(f"offerings/{off.name}")
        for reg in sorted((off / "regions").glob("*/")):
            paths.append(f"offerings/{off.name}/regions/{reg.name}")
            for zone in sorted((reg / "zones").glob("*/")):
                zp = f"offerings/{off.name}/regions/{reg.name}/zones/{zone.name}"
                paths.append(zp)
                for rt in sorted((zone / "rack-types").glob("*/")):
                    paths.append(f"{zp}/rack-types/{rt.name}")
    return paths


def capture(client: _AsgiClient, root: Path) -> dict[str, dict]:
    """Return {key: {status, ct, body}} for every GET the frontend can issue."""
    cache: dict[str, dict] = {}

    def grab(pathname: str, params: dict):
        r = client.get(pathname, params=params)
        ct = r.headers.get("content-type", "application/json")
        cache[_key(pathname, params)] = {"status": r.status_code, "ct": ct, "body": r.text}

    # no-param endpoints
    for ep in ("/api/tree", "/api/hierarchy", "/api/candidates", "/api/candidate-fields",
               "/api/confirm"):
        grab(ep, {})

    # per-node-path endpoints
    nodes = _node_paths(root)
    for p in nodes:
        for ep in ("/api/dashboard", "/api/placed", "/api/health", "/api/layout",
                   "/api/overview", "/api/tree"):
            grab(ep, {"path": p})

    # single-rack loads for the editor (tree node → /api/rack?path=<file>.yaml)
    for rf in sorted((root / "offerings").glob("*/regions/*/zones/*/rack-types/*/racks/*.yaml")):
        grab("/api/rack", {"path": rf.relative_to(root).as_posix()})

    # complete search corpus: union results across every entity token (empty q returns nothing),
    # baked once under a sentinel key; the shim substring-filters it client-side.
    from bombom.design import load_racks
    tokens: set[str] = set()
    for lr in load_racks(root).racks:
        tokens.add(lr.rack_id)
        tokens.update(v for v in lr.hierarchy.values() if v)
        tokens.update(pl.device for pl in lr.design.placements)
    corpus: dict[str, dict] = {}
    for t in sorted(tokens):
        for item in client.get("/api/search", params={"q": t, "path": "offerings",
                                                       "limit": "500"}).json().get("results", []):
            corpus[json.dumps(item, sort_keys=True, ensure_ascii=False)] = item
    cache["/api/search#corpus"] = {"status": 200, "ct": "application/json",
                                   "body": json.dumps(list(corpus.values()), ensure_ascii=False)}

    for pool in ("0", "1"):
        grab("/api/catalog/search", {"q": "", "kind": "device", "pool": pool, "limit": "500"})
    grab("/api/catalog/search", {"q": "", "kind": "rack", "limit": "500"})

    # release diff — every ordered pair among the sealed tags + WORKING, root + per zone
    confs = json.loads(cache[_key("/api/confirm", {})]["body"])
    refs = [c["tag"] for c in confs if c.get("tag")] + ["WORKING"]
    diff_paths = ["offerings"] + [p for p in nodes if "/zones/" in p and "/rack-types/" not in p]
    for base in refs:
        for head in refs:
            if base == head:
                continue
            for p in diff_paths:
                for pr in ("0", "1"):
                    grab("/api/release/diff",
                         {"base": base, "head": head, "path": p, "priced_at_ref": pr})
    return cache


# ── per-page transform ──────────────────────────────────────────────────────
_BANNER_CSS = (
    "#demobar{position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#1e293b;color:#e2e8f0;"
    "font:12px system-ui;padding:5px 12px;display:flex;gap:12px;align-items:center}"
    "#demobar a{color:#93c5fd;text-decoration:none}#demobar .sp{margin-left:auto}"
    "#demotoast{position:fixed;left:50%;bottom:42px;transform:translateX(-50%);z-index:10000;"
    "background:#0f172a;color:#fff;font:13px system-ui;padding:8px 14px;border-radius:8px;"
    "opacity:0;transition:opacity .2s;pointer-events:none}#demotoast.on{opacity:.95}"
)


def _link_rewrite(html: str) -> str:
    """Rewrite in-app absolute routes ("/dashboard", "/?path=", '/layout?path='+x) to static
    files. Longest routes first so "/" doesn't clobber "/dashboard"."""
    for route in sorted(ROUTES, key=len, reverse=True):
        f = ROUTES[route]
        if route == "/":
            # only the standalone root link forms — not every "/" in the file
            html = re.sub(r"(['\"`])/(\?)", rf"\1{f}\2", html)          # "/?path=" , `/?path=`
            html = re.sub(r"(['\"`])/(\1)", rf"\1{f}\2", html)          # "/" exact
        else:
            esc = re.escape(route)
            # "/route" or '/route' or `/route` possibly followed by ? or closing quote
            html = re.sub(rf"(['\"`]){esc}(?=[?'\"`])", rf"\1{f}", html)
    return html


def _shim() -> str:
    return (
        f"<style>{_BANNER_CSS}</style>\n"
        "<script src=\"_api.js\"></script>\n<script>\n"
        "const __API__=window.__API__||{};\n"
        "function __key__(u){const x=new URL(u,location.href);"
        "const ps=[...x.searchParams.entries()].map(([k,v])=>k+'='+v).sort();"
        "return x.pathname+'|'+ps.join('&');}\n"
        "function __resp__(o){return new Response(o.body,{status:o.status,"
        "headers:{'Content-Type':o.ct||'application/json'}});}\n"
        "function __toast__(m){let t=document.getElementById('demotoast');"
        "if(!t){t=document.createElement('div');t.id='demotoast';document.body.appendChild(t);}"
        "t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('on'),1800);}\n"
        "const _f=window.fetch;\n"
        "window.fetch=function(u,o){o=o||{};const m=(o.method||'GET').toUpperCase();"
        "const url=String(typeof u==='object'?u.url:u);\n"
        "  if(m!=='GET'){__toast__('정적 데모 — 편집/저장은 비활성화되어 있습니다');"
        "    return Promise.resolve(new Response(JSON.stringify({ok:false,demo:true,"
        "detail:'read-only demo'}),{status:403,headers:{'Content-Type':'application/json'}}));}\n"
        "  if(url.indexOf('/api/')===-1) return _f(u,o);\n"
        "  const x=new URL(url,location.href); const k=__key__(url);\n"
        "  if(__API__[k]) return Promise.resolve(__resp__(__API__[k]));\n"
        "  // client-side filter for search corpora baked at q=''\n"
        "  if(x.pathname==='/api/search'){const q=(x.searchParams.get('q')||'').toLowerCase();"
        "    const sp=x.searchParams.get('path')||'offerings';"
        "    const base=__API__['/api/search#corpus'];"
        "    if(base){let rs=JSON.parse(base.body).filter(r=>JSON.stringify(r).toLowerCase().includes(q));"
        "      if(sp&&sp!=='offerings') rs=rs.filter(r=>r.kind==='rack_type'||r.kind==='zone'||"
        "!r.path||r.path.indexOf(sp)===0);"
        "      return Promise.resolve(new Response(JSON.stringify({q:x.searchParams.get('q'),count:rs.length,results:rs}),"
        "{status:200,headers:{'Content-Type':'application/json'}}));}}\n"
        "  if(x.pathname==='/api/catalog/search'){const q=(x.searchParams.get('q')||'').toLowerCase();"
        "    const kind=x.searchParams.get('kind')||'device';const pool=x.searchParams.get('pool')||'0';"
        "    const bk=kind==='rack'?__key__('/api/catalog/search?kind=rack&limit=500&q='):"
        "__key__('/api/catalog/search?kind=device&limit=500&pool='+pool+'&q=');"
        "    const base=__API__[bk]; if(base){const rows=JSON.parse(base.body).filter(r=>"
        "JSON.stringify(r).toLowerCase().includes(q));"
        "    return Promise.resolve(new Response(JSON.stringify(rows),{status:200,headers:{'Content-Type':'application/json'}}));}}\n"
        "  return Promise.resolve(new Response('{}',{status:404,headers:{'Content-Type':'application/json'}}));\n"
        "};\n"
        "addEventListener('DOMContentLoaded',()=>{const b=document.createElement('div');b.id='demobar';"
        "b.innerHTML='🔒 bombom 정적 데모 (읽기전용) · "
        "<a href=\"index.html\">메인</a> <a href=\"summary.html\">투자 리포트</a> "
        "<a href=\"dashboard.html\">현황</a> <a href=\"viewer.html\">뷰어</a> <a href=\"editor.html\">에디터</a>"
        "<span class=\"sp\"></span>편집·저장은 비활성화';document.body.appendChild(b);"
        "document.body.style.paddingBottom='34px';"
        "document.querySelectorAll('#csvBtn,#reportBtn').forEach(el=>el.addEventListener('click',"
        "e=>{e.preventDefault();e.stopImmediatePropagation();__toast__('정적 데모 — 다운로드는 비활성화되어 있습니다');},true));"
        "});\n"
        "</script>\n"
    )


def _hide_downloads(html: str) -> str:
    # download links (CSV/draw.io/report) can't be generated statically → hide to avoid dead links
    return html + (
        "<style>[href*='.csv'],[href*='elevation.drawio'],[href*='report.html'],"
        "[href*='invest.csv'],#dl{display:none!important}</style>\n"
    )



def build(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = seed_showcase(Path(tmp) / "ws")
        ws = Workspace.open(root)
        app = create_app(root, db_path=ws.catalog.db_path)
        client = _AsgiClient(app)

        cache = capture(client, root)
        # strip the throwaway workspace's absolute path so screens show "offerings/…" not /tmp/…
        for rs in (str(root.resolve()), str(root)):
            for v in cache.values():
                v["body"] = v["body"].replace(rs + "/", "").replace(rs, "offerings")
        # shared API cache as one external file (pages stay small, load once)
        (out / "_api.js").write_text(
            "window.__API__=" + json.dumps(cache, ensure_ascii=False) + ";\n")
        shim = _shim()

        # viewer: baked data (self-contained), then shim for nav + downloads hidden
        viewer = inject((WEB / "viewer.html").read_text(),
                        build_data(ws, root, is_mock=False))
        viewer = _hide_downloads(_link_rewrite(viewer)).replace("</head>", shim + "</head>", 1)
        (out / "viewer.html").write_text(viewer)

        for page in PAGES:
            if page == "viewer.html":
                continue
            html = (WEB / page).read_text()
            html = _hide_downloads(_link_rewrite(html)).replace("</head>", shim + "</head>", 1)
            (out / page).write_text(html)

        # main page = the overview (home.html), served as the Pages landing
        (out / "index.html").write_text((out / "home.html").read_text())
        (out / ".nojekyll").write_text("")  # serve _api.js (Jekyll skips underscore files)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "public"))
    args = ap.parse_args(argv)
    o = build(Path(args.out))
    n = len(list(o.glob("*.html")))
    print(f"wrote {n} pages to {o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
