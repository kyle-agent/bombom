"""Base-data hierarchy as a browsable tree (기준정보 관리).

The directory tree under `offerings/` IS the hierarchy; each node carries a marker YAML
(`offering.yaml`/`region.yaml`/`zone.yaml`/`rack-type.yaml`) with a display `name`. This
module reads that tree for the management UI; writes go through `bombom.scaffold` (reused by
the API) so there is one place that lays down a node.
"""

from __future__ import annotations

from pathlib import Path

import yaml

LEVELS = ("offering", "region", "zone", "rack_type")
_MARKER = {
    "offering": "offering.yaml", "region": "region.yaml",
    "zone": "zone.yaml", "rack_type": "rack-type.yaml",
}


def _name(node_dir: Path, level: str) -> str:
    marker = node_dir / _MARKER[level]
    if marker.exists():
        try:
            doc = yaml.safe_load(marker.read_text()) or {}
            if isinstance(doc, dict) and doc.get("name"):
                return str(doc["name"])
        except yaml.YAMLError:
            pass
    return node_dir.name


def _children(parent: Path, group: str) -> list[Path]:
    base = parent / group
    if not base.is_dir():
        return []
    return sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name)


def list_hierarchy(root: Path) -> list[dict]:
    """Nested tree: offerings → regions → zones → rack-types (each with id, name, children)."""
    out = []
    for off in _children(Path(root), "offerings"):
        regions = []
        for reg in _children(off, "regions"):
            zones = []
            for zon in _children(reg, "zones"):
                rtypes = []
                for rt in _children(zon, "rack-types"):
                    racks = [p.stem for p in sorted((rt / "racks").glob("*.y*ml"))] \
                        if (rt / "racks").is_dir() else []
                    rtypes.append({"rack_type": rt.name, "name": _name(rt, "rack_type"),
                                   "racks": racks})
                zones.append({"zone": zon.name, "name": _name(zon, "zone"), "rack_types": rtypes})
            regions.append({"region": reg.name, "name": _name(reg, "region"), "zones": zones})
        out.append({"offering": off.name, "name": _name(off, "offering"), "regions": regions})
    return out
