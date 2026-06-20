"""Render rack elevations as a draw.io (.drawio / mxGraph XML) document.

One movable group (container) per rack, one editable mxCell per device — same U→pixel
geometry and category colors as the SVG renderer (`render/svg.py`), so the diagram opens
in draw.io / diagrams.net ready to drag and annotate. Multiple racks lay out left→right on
a single canvas, so a whole AZ or Rack-Type exports as one editable sheet.
"""

from __future__ import annotations

import html
from typing import Optional, Sequence

from ..catalog import Catalog
from ..design import LoadedRack
from ..overlay import CategoryBook
from .svg import _CAT_FILL

# darker outline per category fill, for a NetBox-ish device chip
_STROKE = {
    "#2563eb": "#1e40af",   # server
    "#16a34a": "#15803d",   # network
    "#9333ea": "#6b21a8",   # storage
    "#64748b": "#475569",   # other
}

U_PX = 16        # canvas pixels per rack U
RACK_W = 220     # rack frame width
GAP = 60         # horizontal space between racks
MARGIN = 40      # canvas margin
TITLE_H = 28     # frame title band height (device geometry is relative, below this)


def _xml_attr(s: str) -> str:
    return html.escape(str(s), quote=True)


def rack_elevation_drawio(
    racks: Sequence[LoadedRack],
    catalog: Catalog,
    *,
    categories: Optional[CategoryBook] = None,
    highlight_release: Optional[str] = None,
    title: str = "rack elevations",
) -> str:
    categories = categories or CategoryBook()
    cells: list[str] = []

    for col, lr in enumerate(racks):
        design = lr.design
        rk = catalog.get_rack_type(design.rack_model.slug)
        rack_u = int(rk.u_height) if rk else 42
        body_h = rack_u * U_PX
        x0 = MARGIN + col * (RACK_W + GAP)
        frame_id = f"rack{col}"

        rack_label = f"{lr.rack_id}  ·  {design.rack_model.slug}  ({rack_u}U)"
        # container frame: a movable group; devices are children with relative geometry
        cells.append(
            f'<mxCell id="{frame_id}" value="{_xml_attr(rack_label)}" '
            'style="rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;'
            'verticalAlign=top;fontStyle=1;fontSize=11;fillColor=#f8fafc;strokeColor=#cbd5e1;'
            'spacingTop=6;" vertex="1" parent="1">'
            f'<mxGeometry x="{x0}" y="{MARGIN}" width="{RACK_W}" height="{body_h + TITLE_H}" '
            'as="geometry"/></mxCell>'
        )

        seen = 0
        for pl in design.placements:
            dev = catalog.get_device_type(pl.device)
            if dev is None or not dev.u_height:
                continue
            span = max(1, int(round(dev.u_height)))
            if pl.position < 1 or pl.position + span - 1 > rack_u:
                continue
            cat = categories.get(pl.device, model=dev.model, manufacturer=dev.manufacturer)
            fill = _CAT_FILL.get(cat, _CAT_FILL["other"])
            highlit = highlight_release is not None and pl.release == highlight_release
            stroke = "#f59e0b" if highlit else _STROKE.get(fill, "#475569")
            sw = 3 if highlit else 1
            # U descends top→bottom; geometry is relative to the frame, below the title band
            y = TITLE_H + (rack_u - (pl.position + span - 1)) * U_PX
            h = span * U_PX - 2
            seen += 1
            value = f"{dev.model}\nU{pl.position} · {pl.release}"
            style = (f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                     f"strokeWidth={sw};fontColor=#ffffff;fontSize=10;align=left;spacingLeft=6;")
            cells.append(
                f'<mxCell id="{frame_id}_d{seen}" value="{_xml_attr(value)}" style="{style}" '
                f'vertex="1" parent="{frame_id}">'
                f'<mxGeometry x="6" y="{y + 1}" width="{RACK_W - 12}" height="{h}" as="geometry"/>'
                '</mxCell>'
            )

    body = "".join(cells)
    return (
        '<mxfile host="bombom">'
        f'<diagram name="{_xml_attr(title)}">'
        '<mxGraphModel dx="900" dy="640" grid="1" gridSize="10" guides="1" tooltips="1" '
        'connect="0" arrows="0" fold="1" page="1" pageScale="1" pageWidth="1169" '
        'pageHeight="826" math="0" shadow="0">'
        '<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'{body}'
        '</root></mxGraphModel></diagram></mxfile>'
    )
