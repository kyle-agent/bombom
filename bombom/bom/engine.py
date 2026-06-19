"""BOM engine: walk a design subtree, join catalog + pricing, roll up CAPEX (KRW) + power.

Quantity is derived from placements (a placement is one instance unless it carries `qty`).
Totals are KRW. Power is summed for capacity only (not costed — CAPEX-first). Unmatched
prices are surfaced in `unpriced`, never silently treated as ₩0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from ..catalog import Catalog
from ..design import load_racks, validate_rack
from .pricing import PriceBook


@dataclass
class LineItem:
    rack_id: str
    name: str
    category: str
    release: Optional[str]
    qty: int
    unit_cost: Optional[int]      # KRW; None = unpriced
    watts: int

    @property
    def subtotal(self) -> int:
        return (self.unit_cost or 0) * self.qty


@dataclass
class BomResult:
    valuation_date: date
    release: Optional[str]
    total_capex: int = 0
    power_w: int = 0
    by_rack: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_release: dict[str, int] = field(default_factory=dict)
    line_items: list[LineItem] = field(default_factory=list)
    unpriced: list[LineItem] = field(default_factory=list)
    issues: list = field(default_factory=list)         # design.Issue

    @property
    def release_delta(self) -> int:
        """CAPEX of the selected release only (0 if no release selected)."""
        if self.release is None:
            return 0
        return self.by_release.get(self.release, 0)


# Placeholder category heuristic until the dedicated category overlay feature lands
# (ADR device-categorization). Keys off model/slug name cues only.
def _category(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("switch", "nexus", "dcs-", "catalyst", "router", "arista")):
        return "network"
    if any(k in n for k in ("storage", "powerstore", "aff", "netapp", "isilon", "vsp")):
        return "storage"
    if any(k in n for k in ("poweredge", "proliant", "server", "blade", "ucs")):
        return "server"
    return "other"


def compute_bom(
    root: Path,
    *,
    catalog: Catalog,
    pricebook: PriceBook,
    release: Optional[str] = None,
    valuation_date: Optional[date] = None,
) -> BomResult:
    as_of = valuation_date or date.today()
    result = BomResult(valuation_date=as_of, release=release)

    loaded = load_racks(Path(root))
    result.issues.extend(loaded.issues)

    for lr in loaded.racks:
        rack_issues = validate_rack(lr, catalog)
        result.issues.extend(rack_issues)
        skip = {iss.index for iss in rack_issues if iss.index is not None and iss.level == "error"}

        for idx, pl in enumerate(lr.design.placements):
            if idx in skip:
                continue  # invalid placement (bad slug / overlap / out-of-bounds) — excluded
            device = catalog.get_device_type(pl.device)
            if device is None:
                continue
            price = pricebook.lookup(as_of, slug=pl.device, part_number=device.part_number)
            watts = _max_draw(device)
            li = LineItem(
                rack_id=lr.rack_id,
                name=device.model,
                category=_category(device.model + " " + device.manufacturer),
                release=pl.release,
                qty=pl.qty,
                unit_cost=price.unit_cost if price else None,
                watts=watts,
            )
            _accumulate(result, li)

        for ci in lr.design.custom_line_items:
            li = LineItem(
                rack_id=lr.rack_id,
                name=ci.name,
                category=ci.category,
                release=ci.release,
                qty=ci.qty,
                unit_cost=ci.unit_cost,
                watts=0,
            )
            _accumulate(result, li)

    return result


def _max_draw(device) -> int:
    return sum(p.maximum_draw or 0 for p in device.power_ports)


def _accumulate(result: BomResult, li: LineItem) -> None:
    result.line_items.append(li)
    result.power_w += li.watts * li.qty
    if li.unit_cost is None:
        result.unpriced.append(li)
        return
    result.total_capex += li.subtotal
    result.by_rack[li.rack_id] = result.by_rack.get(li.rack_id, 0) + li.subtotal
    result.by_category[li.category] = result.by_category.get(li.category, 0) + li.subtotal
    if li.release:
        result.by_release[li.release] = result.by_release.get(li.release, 0) + li.subtotal
