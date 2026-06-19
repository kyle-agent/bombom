"""Build the viewer payload (BOMBOM_DATA) from real data, and bake it into web/viewer.html.

The same payload powers the static export (offline file) and the live API, so screen and
numbers stay consistent.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

from .bom import compute_bom
from .design import load_racks
from .overlay import required_missing
from .render import rack_elevation_svg
from .workspace import Workspace

_MARKER = re.compile(r"/\*__BOMBOM_DATA__\*/.*?/\*__END__\*/", re.S)


def _device_u(catalog, slug) -> int:
    d = catalog.get_device_type(slug)
    return max(1, int(round(d.u_height))) if (d and d.u_height) else 0


def build_data(
    ws: Workspace,
    root_path: Path,
    *,
    release: Optional[str] = None,
    valuation_date: Optional[date] = None,
    is_mock: bool = False,
) -> dict:
    root_path = Path(root_path)
    loaded = load_racks(root_path)

    releases = sorted({pl.release for lr in loaded.racks for pl in lr.design.placements})
    current = release or (releases[-1] if releases else None)

    bom = compute_bom(
        root_path, catalog=ws.catalog, pricebook=ws.pricebook, release=current,
        valuation_date=valuation_date, categories=ws.categories, fields=ws.fields,
        type_meta=ws.type_meta,
    )

    racks: dict[str, dict] = {}
    tree_offering = None
    nest: dict = {}
    for lr in loaded.racks:
        design = lr.design
        rt = ws.catalog.get_rack_type(design.rack_type.slug)
        placements = []
        used_u = 0
        cap = 0
        power = 0
        for pl in design.placements:
            dev = ws.catalog.get_device_type(pl.device)
            if dev is None:
                continue
            cat = ws.categories.get(pl.device, model=dev.model, manufacturer=dev.manufacturer)
            merged = {**ws.type_meta.get(pl.device), **(pl.meta or {})}
            missing = required_missing(ws.fields, merged, applies_to="placement",
                                       category=cat, role=design.role)
            price = ws.pricebook.lookup(valuation_date or date.today(), slug=pl.device,
                                        part_number=dev.part_number)
            u = _device_u(ws.catalog, pl.device)
            used_u += u * pl.qty
            watts = sum(p.maximum_draw or 0 for p in dev.power_ports)
            power += watts * pl.qty
            if price:
                cap += price.unit_cost * pl.qty
            placements.append({
                "device": pl.device, "name": dev.model, "category": cat,
                "position": pl.position, "u": u, "release": pl.release, "qty": pl.qty,
                "unit_cost": price.unit_cost if price else None,
                "meta": merged, "meta_missing": missing,
            })
        customs = []
        for ci in design.custom_line_items:
            cap += ci.unit_cost * ci.qty
            customs.append({"name": ci.name, "qty": ci.qty, "unit_cost": ci.unit_cost,
                            "release": ci.release, "category": ci.category})
        racks[lr.rack_id] = {
            "id": lr.rack_id, "role": design.role,
            "rack_type": {"slug": design.rack_type.slug, "u_height": int(rt.u_height) if rt else 42},
            "svg": rack_elevation_svg(design, ws.catalog, categories=ws.categories,
                                      highlight_release=current),
            "placements": placements, "custom_line_items": customs,
            "summary": {"used_u": used_u, "capex": cap, "power_w": power},
        }
        # build the (single-offering) hierarchy tree
        hp = lr.hierarchy
        tree_offering = tree_offering or hp.get("offering", "offering")
        (nest.setdefault(hp.get("region", "?"), {})
             .setdefault(hp.get("zone", "?"), {})
             .setdefault(hp.get("rack_group", "?"), [])
             .append(lr.rack_id))

    tree = {
        "offering": tree_offering or "offering", "name": tree_offering or "offering",
        "regions": [
            {"region": r, "zones": [
                {"zone": z, "rack_groups": [
                    {"rack_group": g, "racks": rk} for g, rk in zs.items()
                ]} for z, zs in rs.items()
            ]} for r, rs in nest.items()
        ],
    }

    return {
        "currency": "₩",
        "is_mock": is_mock,
        "releases": releases,
        "current_release": current,
        "fields": [f.model_dump() for f in ws.fields],
        "tree": tree,
        "racks": racks,
        "bom": {
            "total_capex": bom.total_capex,
            "by_category": bom.by_category,
            "by_release": bom.by_release,
            "power_w": bom.power_w,
            "unpriced": [{"name": li.name, "qty": li.qty} for li in bom.unpriced],
            "issues": [{"path": i.path, "level": i.level, "message": i.message} for i in bom.issues],
        },
    }


def write_export(payload: dict, out_path: Path, *, template: Path) -> Path:
    template = Path(template)
    if not template.exists():
        raise FileNotFoundError(f"viewer template not found: {template}")
    html = template.read_text()
    blob = "/*__BOMBOM_DATA__*/ " + json.dumps(payload, ensure_ascii=False) + " /*__END__*/"
    if not _MARKER.search(html):
        raise ValueError("template missing /*__BOMBOM_DATA__*/ … /*__END__*/ markers")
    out = _MARKER.sub(lambda _: blob, html, count=1)
    out_path = Path(out_path)
    out_path.write_text(out)
    return out_path
