"""Bake the interactive rack-layout view into a single self-contained HTML page for static
hosting (GitHub Pages). No backend: every zone's rack SVGs + metadata are embedded, and a
small shim serves them through a `fetch` override so `web/layout.html` runs UNCHANGED.

    python scripts/build_static_demo.py [--out docs/index.html]

Reuses the default catalog index (.index/catalog.db); seeds a throwaway demo workspace.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from bombom.design import load_racks
from bombom.render import rack_elevation_svg
from bombom.workspace import Workspace

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo import seed  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LAYOUT_HTML = REPO / "web" / "layout.html"


def _zone_layout(ws: Workspace, zone_dir: Path) -> list[dict]:
    loaded = load_racks(zone_dir)
    racks = sorted(loaded.racks, key=lambda r: r.path)
    out = []
    for lr in racks:
        rk = ws.catalog.get_rack_type(lr.design.rack_model.slug)
        out.append({
            "rack_id": lr.rack_id,
            "hierarchy": lr.hierarchy,
            "rack_model": lr.design.rack_model.slug,
            "rack_u": int(rk.u_height) if rk else 42,
            "svg": rack_elevation_svg(lr.design, ws.catalog, categories=ws.categories,
                                      highlight_release=None, u_px=18, width=240),
        })
    return out


def build(out_path: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = seed(Path(tmp) / "ws")
        ws = Workspace.open(root)

        layouts: dict[str, dict] = {}
        zones: list[dict] = []
        for zone_dir in sorted(root.glob("offerings/*/regions/*/zones/*")):
            if not list(zone_dir.glob("rack-types/*/racks/*.yaml")):
                continue
            racks = _zone_layout(ws, zone_dir)
            if not racks:
                continue
            rel = zone_dir.relative_to(root).as_posix()  # offerings/.../zones/az1
            parts = rel.split("/")
            label = f"{parts[1]} / {parts[3]} / {parts[5]} ({len(racks)}랙)"
            layouts[rel] = {"path": rel, "count": len(racks), "racks": racks}
            zones.append({"path": rel, "label": label})

    if not zones:
        raise SystemExit("no zones with racks found in seeded demo")

    first = zones[0]["path"]
    shim = (
        "<style>#dl{display:none!important}nav.topnav{display:none!important}"
        "#zonesel{background:#fff;color:#0f172a;border:1px solid #cbd5e1;border-radius:6px;"
        "padding:5px 8px;font-size:13px}.demoflag{margin-left:auto;color:#94a3b8;font-size:12px}"
        "</style>\n"
        "<script>\n"
        f"const __LAYOUTS__={json.dumps(layouts, ensure_ascii=False)};\n"
        f"const __ZONES__={json.dumps(zones, ensure_ascii=False)};\n"
        f"if(!new URLSearchParams(location.search).get('path')){{location.replace('?path='+encodeURIComponent({json.dumps(first)}));}}\n"
        "const _f=window.fetch;window.fetch=(u,o)=>{const m=String(u);\n"
        "  if(m.includes('/api/layout')){const p=new URL(m,location.origin).searchParams.get('path');\n"
        "    const d=__LAYOUTS__[p];return Promise.resolve(new Response(d?JSON.stringify(d):'{}',\n"
        "      {status:d?200:404,headers:{'Content-Type':'application/json'}}));}\n"
        "  return _f(u,o);};\n"
        "addEventListener('DOMContentLoaded',()=>{\n"
        "  const cur=new URLSearchParams(location.search).get('path');\n"
        "  const sel=document.createElement('select');sel.id='zonesel';\n"
        "  sel.innerHTML=__ZONES__.map(z=>`<option value=\"${z.path}\" ${z.path===cur?'selected':''}>${z.label}</option>`).join('');\n"
        "  sel.onchange=()=>location.href='?path='+encodeURIComponent(sel.value);\n"
        "  const tb=document.querySelector('.toolbar');tb.parentNode.insertBefore(sel,tb);\n"
        "  const flag=document.createElement('span');flag.className='demoflag';\n"
        "  flag.innerHTML='정적 데모 (GitHub Pages) · 읽기전용 · <a href=\"viewer.html\" style=\"color:#2563eb\">뷰어 →</a>';\n"
        "  document.querySelector('header').appendChild(flag);\n"
        "});\n"
        "</script>\n"
    )

    html = LAYOUT_HTML.read_text()
    html = html.replace("</head>", shim + "</head>", 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "docs" / "index.html"),
                    help="output HTML path (default: docs/index.html)")
    args = ap.parse_args(argv)
    out = build(Path(args.out))
    kb = out.stat().st_size / 1024
    print(f"wrote {out} ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
