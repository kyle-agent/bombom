"""Workspace health: every blocking/advisory issue in one place, so a designer can clear them
before confirming. Pure aggregation over the existing engine — `compute_bom` already collects
validation errors, missing-required-meta, and pricing-load problems into one issue list, and
tracks unpriced line items separately — plus candidate-pool gaps (unpriced / missing fields).
Read-only; nothing here writes.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .bom import compute_bom
from .candidates import load_pool
from .design import parse_hierarchy
from .overlay import required_missing


def _loc(path: str) -> dict:
    p = Path(path)
    h = parse_hierarchy(p)
    rack = p.stem if "/racks/" in str(path).replace("\\", "/") else ""
    parts = [h.get("region"), h.get("zone"), h.get("rack_type"), rack]
    return {"location": " / ".join(x for x in parts if x), "rack": rack}


def build_health(ws, root_path: Path) -> dict:
    root_path = Path(root_path)
    bom = compute_bom(root_path, catalog=ws.catalog, pricebook=ws.pricebook,
                      categories=ws.categories, fields=ws.fields, type_meta=ws.type_meta)

    errors = [{**_loc(i.path), "message": i.message} for i in bom.issues if i.level == "error"]
    warnings = [{**_loc(i.path), "message": i.message} for i in bom.issues if i.level == "warn"]
    unpriced = [{**_loc(li.rack_path), "device": li.name, "category": li.category, "qty": li.qty}
                for li in bom.unpriced]

    # candidate pool is workspace-global (candidates/pool.yaml at ws.root, independent of path)
    cand_unpriced, cand_meta = [], []
    for c in load_pool(Path(ws.root)):
        dev = ws.catalog.get_device_type(c.slug)
        cat = (ws.categories.get(c.slug, model=dev.model, manufacturer=dev.manufacturer)
               if dev else "other")
        price = (ws.pricebook.lookup(date.today(), slug=c.slug,
                                     part_number=dev.part_number if dev else None) if dev else None)
        if price is None:
            cand_unpriced.append({"slug": c.slug, "model": dev.model if dev else None})
        missing = required_missing(ws.fields, c.meta or {}, applies_to="candidate", category=cat)
        if missing:
            cand_meta.append({"slug": c.slug, "model": dev.model if dev else None, "missing": missing})

    groups = {
        "errors": errors, "warnings": warnings, "unpriced": unpriced,
        "candidate_unpriced": cand_unpriced, "candidate_meta_missing": cand_meta,
    }
    counts = {k: len(v) for k, v in groups.items()}
    return {
        "path": str(root_path),
        "valuation_date": bom.valuation_date.isoformat(),
        "counts": counts,
        "total": sum(counts.values()),
        "ok": sum(counts.values()) == 0,
        **groups,
    }
