"""Render a rack elevation as an SVG string (front face), NetBox-style.

Computed from the rack's u_height and each placement's position + the device's u_height.
The placement's release is highlighted (amber outline) when it equals `highlight_release`.
Shared by the API endpoint and the static export so screen and data stay consistent.
"""

from __future__ import annotations

import html
from typing import Optional

from ..catalog import Catalog
from ..design import RackDesign
from ..overlay import CategoryBook

_CAT_FILL = {
    "server": "#2563eb",
    "network": "#16a34a",
    "storage": "#9333ea",
    "other": "#64748b",
}


def rack_elevation_svg(
    design: RackDesign,
    catalog: Catalog,
    *,
    categories: Optional[CategoryBook] = None,
    highlight_release: Optional[str] = None,
    u_px: int = 16,
    width: int = 240,
) -> str:
    categories = categories or CategoryBook()
    rack = catalog.get_rack_type(design.rack_type.slug)
    rack_u = int(rack.u_height) if rack else 42
    h = rack_u * u_px
    pad_left = 26
    body_w = width - pad_left - 8

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h + 4}" '
        f'viewBox="0 0 {width} {h + 4}" font-family="sans-serif">',
        f'<rect x="{pad_left}" y="2" width="{body_w + 4}" height="{h}" '
        f'fill="#f1f5f9" stroke="#cbd5e1" stroke-width="2" rx="4"/>',
    ]
    # U gridlines + numbers (descending top→bottom)
    for u in range(rack_u, 0, -1):
        y = 2 + (rack_u - u) * u_px
        parts.append(f'<line x1="{pad_left}" y1="{y}" x2="{pad_left + body_w + 4}" y2="{y}" '
                     f'stroke="#e2e8f0" stroke-dasharray="2 2"/>')
        parts.append(f'<text x="{pad_left - 4}" y="{y + u_px - 4}" font-size="8" '
                     f'fill="#94a3b8" text-anchor="end">{u}</text>')

    for pl in design.placements:
        device = catalog.get_device_type(pl.device)
        if device is None or not device.u_height:
            continue
        span = max(1, int(round(device.u_height)))
        if pl.position < 1 or pl.position + span - 1 > rack_u:
            continue
        cat = categories.get(pl.device, model=device.model, manufacturer=device.manufacturer)
        fill = _CAT_FILL.get(cat, _CAT_FILL["other"])
        y = 2 + (rack_u - (pl.position + span - 1)) * u_px
        bh = span * u_px - 2
        sel = highlight_release is not None and pl.release == highlight_release
        stroke = '#f59e0b' if sel else 'rgba(255,255,255,.3)'
        sw = 2 if sel else 1
        label = html.escape(device.model)
        parts.append(
            f'<g><rect x="{pad_left + 1}" y="{y + 1}" width="{body_w}" height="{bh}" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<text x="{pad_left + 6}" y="{y + 1 + bh / 2 + 3}" font-size="9" fill="#fff">'
            f'{label} <tspan fill="#e2e8f0">U{pl.position}·{pl.release}</tspan></text></g>'
        )

    parts.append("</svg>")
    return "".join(parts)
