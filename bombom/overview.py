"""Overview aggregation — powers the main page (offering→region→zone structure) and the
selectable rollup report (group by offering / region / zone / rack-type).

The tree comes from the **directory hierarchy** (`list_hierarchy`), so empty offerings/regions/
zones still show. Counts/CAPEX are overlaid from `placed_rows` (every priced/unpriced line item
tagged with its full hierarchy), so they reconcile with the BOM engine. Server count = line
items whose category is "server"; device count = all qty; rack count = distinct racks.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from .hierarchy import list_hierarchy
from .report import placed_rows


class _Agg:
    __slots__ = ("racks", "servers", "devices", "capex", "rack_types")

    def __init__(self):
        self.racks: set = set()
        self.rack_types: set = set()
        self.servers = 0
        self.devices = 0
        self.capex = 0

    def add(self, r: dict):
        self.racks.add((r["offering"], r["region"], r["zone"], r["rack_type"], r["rack"]))
        self.rack_types.add((r["offering"], r["region"], r["zone"], r["rack_type"]))
        self.devices += r["qty"]
        if r["category"] == "server":
            self.servers += r["qty"]
        if r["priced"]:
            self.capex += r["subtotal"]

    def row(self, key: str, label: str) -> dict:
        return {"key": key, "label": label, "racks": len(self.racks),
                "rack_types": len(self.rack_types), "servers": self.servers,
                "devices": self.devices, "capex": self.capex}


_EMPTY = _Agg()


def build_overview(ws, root, *, release: Optional[str] = None,
                   valuation_date: Optional[date] = None) -> dict:
    # Hierarchy comes from the workspace root (the dir holding offerings/); the `root` arg may be
    # a resolved sub-node path used only to scope which placements are aggregated.
    hier = list_hierarchy(Path(getattr(ws, "root", root)))
    all_rows = placed_rows(ws, root, valuation_date=valuation_date)
    releases = sorted({r["release"] for r in all_rows if r["release"]})  # DRAFT=미태그 작업본
    rows = all_rows if not release else [r for r in all_rows if r["release"] == release]

    # placement aggregates keyed by hierarchy names
    z_agg: dict[tuple, _Agg] = {}
    r_agg: dict[tuple, _Agg] = {}
    o_agg: dict[str, _Agg] = {}
    rt_agg: dict[str, _Agg] = {}
    total = _Agg()
    for r in rows:
        total.add(r)
        z_agg.setdefault((r["offering"], r["region"], r["zone"]), _Agg()).add(r)
        r_agg.setdefault((r["offering"], r["region"]), _Agg()).add(r)
        o_agg.setdefault(r["offering"], _Agg()).add(r)
        rt_agg.setdefault(r["rack_type"], _Agg()).add(r)

    # tree from the directory hierarchy (empty nodes included), aggregates overlaid
    tree_out, n_regions, n_zones = [], 0, 0
    for o in hier:
        off = o["offering"]
        reg_list = []
        for rg in o["regions"]:
            n_regions += 1
            region = rg["region"]
            zone_list = []
            for z in rg["zones"]:
                n_zones += 1
                zr = z_agg.get((off, region, z["zone"]), _EMPTY).row("", z.get("name") or z["zone"])
                zr["zone"] = z["zone"]
                zr["path"] = f"offerings/{off}/regions/{region}/zones/{z['zone']}"
                zone_list.append(zr)
            rr = r_agg.get((off, region), _EMPTY).row(f"{off}/{region}", rg.get("name") or region)
            rr["region"] = region
            rr["zones"] = zone_list
            reg_list.append(rr)
        orow = o_agg.get(off, _EMPTY).row(off, o.get("name") or off)
        orow["offering"] = off
        orow["regions"] = reg_list
        tree_out.append(orow)

    totals = total.row("", "전체")
    totals["regions"] = n_regions
    totals["zones"] = n_zones

    # groups for the bars/report — offerings & regions span the whole hierarchy (0 when empty)
    def grp_offering():
        out = [o_agg.get(o["offering"], _EMPTY).row(o["offering"], o.get("name") or o["offering"])
               for o in hier]
        return sorted(out, key=lambda x: x["capex"], reverse=True)

    def grp_region():
        out = []
        for o in hier:
            for rg in o["regions"]:
                a = r_agg.get((o["offering"], rg["region"]), _EMPTY)
                out.append(a.row(f"{o['offering']}/{rg['region']}", f"{o['offering']} · {rg['region']}"))
        return sorted(out, key=lambda x: x["capex"], reverse=True)

    def grp_zone():
        out = []
        for o in hier:
            for rg in o["regions"]:
                for z in rg["zones"]:
                    a = z_agg.get((o["offering"], rg["region"], z["zone"]), _EMPTY)
                    path = f"offerings/{o['offering']}/regions/{rg['region']}/zones/{z['zone']}"
                    out.append(a.row(path, f"{rg['region']} / {z['zone']}"))
        return sorted(out, key=lambda x: x["capex"], reverse=True)

    def grp_rack_type():
        out = [a.row(k, k) for k, a in rt_agg.items()]
        return sorted(out, key=lambda x: x["capex"], reverse=True)

    return {
        "path": str(root),
        "currency": "₩",
        "release": release or "",
        "releases": releases,
        "totals": totals,
        "tree": tree_out,
        "groups": {
            "offering": grp_offering(),
            "region": grp_region(),
            "zone": grp_zone(),
            "rack_type": grp_rack_type(),
        },
    }
