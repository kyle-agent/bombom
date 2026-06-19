"""Validate rack designs against the catalog index.

Checks per rack: the rack_model slug exists; each placed device slug exists; the device fits
within the rack height; no two devices overlap on the same U. Returns issues (path + reason)
— callers exclude the offending placement but keep totalling the valid ones.
"""

from __future__ import annotations

import math

from ..catalog import Catalog
from .loader import Issue, LoadedRack


def _footprint(position: int, u_height: float) -> range:
    # 0U devices (PDUs) occupy no rack units; fractional U rounds up to whole-U slots.
    span = math.ceil(u_height) if u_height and u_height > 0 else 0
    return range(position, position + span)


def validate_rack(loaded: LoadedRack, catalog: Catalog) -> list[Issue]:
    issues: list[Issue] = []
    path = loaded.path
    design = loaded.design

    rack = catalog.get_rack_type(design.rack_model.slug)
    if rack is None:
        issues.append(Issue(path, "error", f"rack_model slug not in catalog: {design.rack_model.slug}"))
    # NOTE: if the rack_model is unknown, rack_u is None and per-placement height checks below
    # are skipped (the rack-level error is still reported). Placements still total — deliberate.
    rack_u = int(rack.u_height) if rack else None

    # NOTE: a placement's `qty` is a cost-line multiplier (BRIEF), not stacked physical units —
    # overlap is checked for the single footprint at `position` only, not qty×footprint.
    occupied: dict[int, str] = {}
    for idx, pl in enumerate(design.placements):
        device = catalog.get_device_type(pl.device)
        if device is None:
            issues.append(Issue(path, "error", f"device slug not in catalog: {pl.device}", idx))
            continue
        if pl.position < 1:
            issues.append(Issue(path, "error", f"{pl.device} position U{pl.position} < 1", idx))
            continue
        foot = _footprint(pl.position, device.u_height)
        if rack_u is not None and foot and (foot.stop - 1) > rack_u:
            issues.append(
                Issue(path, "error",
                      f"{pl.device} at U{pl.position} ({device.u_height}U) exceeds rack {rack_u}U", idx)
            )
            continue
        clash = next((u for u in foot if u in occupied), None)
        if clash is not None:
            issues.append(
                Issue(path, "error", f"U{clash} overlap: {pl.device} vs {occupied[clash]}", idx)
            )
            continue
        for u in foot:
            occupied[u] = pl.device

    return issues
