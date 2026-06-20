"""Status dashboard aggregation — the read-only "현황" over confirmed/designed data.

Headline metric is the **cumulative total CAPEX** (BOM view "c", ROADMAP decision). Rollups
are derived from `compute_bom` line items: by hierarchy level (region/zone/rack-type), by
category, per-release trend (increment + cumulative), and top-spend devices. Unpriced and
meta-missing items are surfaced as counts, never costed as ₩0.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from .bom import compute_bom
from .design import parse_hierarchy
from .report import summarize_releases


def build_dashboard(ws, path, *, valuation_date: Optional[date] = None) -> dict:
    result = compute_bom(
        Path(path), catalog=ws.catalog, pricebook=ws.pricebook, valuation_date=valuation_date,
        categories=ws.categories, fields=ws.fields, type_meta=ws.type_meta,
    )

    by_region: dict[str, int] = {}
    by_zone: dict[str, int] = {}
    by_rack_type: dict[str, int] = {}
    by_device: dict[str, dict] = {}
    racks: set[str] = set()
    total_qty = 0

    for li in result.line_items:
        total_qty += li.qty
        racks.add(li.rack_path or li.rack_id)
        if li.unit_cost is None:
            continue        # unpriced: counted (qty/racks/counts.unpriced) but never costed as ₩0
        h = parse_hierarchy(Path(li.rack_path)) if li.rack_path else {}
        region, zone, rtype = h.get("region", "—"), h.get("zone", "—"), h.get("rack_type", "—")
        sub = li.subtotal
        by_region[region] = by_region.get(region, 0) + sub
        by_zone[f"{region} / {zone}"] = by_zone.get(f"{region} / {zone}", 0) + sub
        by_rack_type[rtype] = by_rack_type.get(rtype, 0) + sub
        d = by_device.setdefault(li.name, {"name": li.name, "qty": 0, "capex": 0})
        d["qty"] += li.qty
        d["capex"] += sub

    top_devices = sorted(by_device.values(), key=lambda d: d["capex"], reverse=True)[:10]
    meta_missing = sum(1 for i in result.issues if i.level == "error" and "메타 필수 누락" in i.message)

    return {
        "path": str(path),
        "valuation_date": result.valuation_date.isoformat(),
        "headline_capex": result.total_capex,        # cumulative total (view c)
        "power_w": result.power_w,
        "by_level": {
            "region": _as_rows(by_region),
            "zone": _as_rows(by_zone),
            "rack_type": _as_rows(by_rack_type),
        },
        "by_category": _as_rows(result.by_category),
        "release_summary": summarize_releases(result),
        "top_devices": top_devices,
        "counts": {
            "racks": len(racks),
            "devices": total_qty,
            "unpriced": len(result.unpriced),
            "meta_missing": meta_missing,
        },
    }


def _as_rows(d: dict[str, int]) -> list[dict]:
    return [{"label": k, "capex": v} for k, v in sorted(d.items(), key=lambda kv: kv[1], reverse=True)]
