"""Workspace-wide search: find a node, a rack, or a placed device by name without walking the
tree by hand. Read-only over the same on-disk model the screens use (hierarchy + rack YAML),
so results always reflect the working tree. The org tree is small relative to the catalog, so
a direct scan is fine — no separate search index to keep in sync.
"""

from __future__ import annotations

from pathlib import Path

from .design import load_racks
from .hierarchy import list_hierarchy


def _device_label(catalog, slug: str) -> str:
    d = catalog.get_device_type(slug)
    return f"{d.manufacturer} {d.model}" if d else slug


def _crumb(*parts: str) -> str:
    return " / ".join(p for p in parts if p)


def _node_hit(hits: list, q: str, kind: str, ident: str, name: str, location: str) -> None:
    if q in (ident or "").lower() or q in (name or "").lower():
        hits.append({"kind": kind, "label": name or ident, "ident": ident, "location": location})


def search_workspace(ws, root: Path, q: str, *, path: str = "offerings", limit: int = 100) -> list[dict]:
    """Hits across hierarchy nodes (id + display name), rack ids, and placed devices (slug +
    catalog model name). Node search is global; rack/device search is scoped to ``path``."""
    q = (q or "").strip().lower()
    if not q:
        return []
    root = Path(root)
    hits: list[dict] = []

    for off in list_hierarchy(root):
        _node_hit(hits, q, "offering", off["offering"], off["name"], _crumb(off["name"]))
        for reg in off["regions"]:
            _node_hit(hits, q, "region", reg["region"], reg["name"], _crumb(off["name"], reg["name"]))
            for zon in reg["zones"]:
                zloc = _crumb(off["name"], reg["name"], zon["name"])
                _node_hit(hits, q, "zone", zon["zone"], zon["name"], zloc)
                for rt in zon["rack_types"]:
                    _node_hit(hits, q, "rack_type", rt["rack_type"], rt["name"],
                              _crumb(zloc, rt["name"]))

    for lr in load_racks(root / path).racks:
        if len(hits) >= limit:
            break
        rel = Path(lr.path).resolve().relative_to(root.resolve()).as_posix()
        h = lr.hierarchy
        loc = _crumb(h.get("region", ""), h.get("zone", ""), h.get("rack_type", ""))
        rack_id = Path(lr.path).stem
        if q in rack_id.lower():
            hits.append({"kind": "rack", "label": rack_id, "location": loc,
                         "path": rel, "rack": rack_id})
        for pl in lr.design.placements:
            name = _device_label(ws.catalog, pl.device)
            if q in pl.device.lower() or q in name.lower():
                hits.append({"kind": "device", "label": name, "device": pl.device,
                             "location": _crumb(loc, rack_id) + f" · U{pl.position}",
                             "path": rel, "rack": rack_id, "position": pl.position})

    return hits[:limit]
