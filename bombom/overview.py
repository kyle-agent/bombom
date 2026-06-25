"""Overview aggregation — powers the main page (offering→region→zone summary) and the
selectable rollup report (group by offering / region / zone / rack-type).

Built from `placed_rows` (every priced/unpriced line item tagged with its full hierarchy), so
the counts and CAPEX reconcile with the dashboard and the BOM engine. Server count = line
items whose category is "server"; device count = all qty; rack count = distinct racks.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from .report import placed_rows


def _zone_path(r: dict) -> str:
    return (f"offerings/{r['offering']}/regions/{r['region']}"
            f"/zones/{r['zone']}")


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


def build_overview(ws, root, *, release: Optional[str] = None,
                   valuation_date: Optional[date] = None) -> dict:
    all_rows = placed_rows(ws, root, valuation_date=valuation_date)
    # release values present (DRAFT = untagged 작업본); used by report/tagging dropdowns
    releases = sorted({r["release"] for r in all_rows if r["release"]})
    rows = all_rows if not release else [r for r in all_rows if r["release"] == release]

    groups: dict[str, dict[str, _Agg]] = {"offering": {}, "region": {}, "zone": {}, "rack_type": {}}
    # nested offering→region→zone aggregation for the main-page tree
    tree: dict = {}
    total = _Agg()

    for r in rows:
        total.add(r)
        keys = {
            "offering": (r["offering"], r["offering"]),
            "region": (f"{r['offering']}/{r['region']}", f"{r['offering']} / {r['region']}"),
            "zone": (_zone_path(r), f"{r['region']} / {r['zone']}"),
            "rack_type": (r["rack_type"], r["rack_type"]),
        }
        for level, (k, _label) in keys.items():
            groups[level].setdefault(k, _Agg()).add(r)
        (tree.setdefault(r["offering"], {})
             .setdefault(r["region"], {})
             .setdefault(r["zone"], _Agg())).add(r)

    # materialise the tree with labels + per-zone paths
    tree_out = []
    for off, regions in sorted(tree.items()):
        off_agg = groups["offering"][off]
        reg_list = []
        for reg, zones in sorted(regions.items()):
            reg_agg = groups["region"][f"{off}/{reg}"]
            zone_list = []
            for zn, agg in sorted(zones.items()):
                z = agg.row("", zn)
                z["zone"] = zn
                z["path"] = f"offerings/{off}/regions/{reg}/zones/{zn}"
                zone_list.append(z)
            r = reg_agg.row(f"{off}/{reg}", reg)
            r["region"] = reg
            r["zones"] = zone_list
            reg_list.append(r)
        o = off_agg.row(off, off)
        o["offering"] = off
        o["regions"] = reg_list
        tree_out.append(o)

    def rows_for(level: str) -> list[dict]:
        labels = {
            "offering": lambda k: k,
            "region": lambda k: k.split("/", 1)[-1],
            "zone": lambda k: k,           # zone key is its path; label set below
            "rack_type": lambda k: k,
        }
        out = []
        for k, agg in groups[level].items():
            out.append(agg.row(k, labels[level](k)))
        return sorted(out, key=lambda x: x["capex"], reverse=True)

    # nicer zone labels for the report (region / zone), keyed by path
    zone_label = {z["path"]: f"{rg['region']} / {z['zone']}"
                  for o in tree_out for rg in o["regions"] for z in rg["zones"]}
    zone_rows = rows_for("zone")
    for zr in zone_rows:
        zr["label"] = zone_label.get(zr["key"], zr["key"])

    return {
        "path": str(root),
        "currency": "₩",
        "release": release or "",
        "releases": releases,
        "totals": total.row("", "전체"),
        "tree": tree_out,
        "groups": {
            "offering": rows_for("offering"),
            "region": rows_for("region"),
            "zone": zone_rows,
            "rack_type": rows_for("rack_type"),
        },
    }
