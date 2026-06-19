"""Serialize a RackDesign back to YAML (atomic write). The inverse of the loader — used by
the write API so screen edits land in git as the same files the designer would hand-write.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from .models import RackDesign


def rack_to_dict(design: RackDesign) -> dict:
    rm: dict = {"slug": design.rack_model.slug}
    if design.rack_model.manufacturer:
        rm["manufacturer"] = design.rack_model.manufacturer
    out: dict = {"rack_model": rm}
    placements = []
    for p in design.placements:
        item = {"device": p.device, "position": p.position, "release": p.release}
        if p.qty != 1:
            item["qty"] = p.qty
        if p.meta:
            item["meta"] = p.meta
        placements.append(item)
    out["placements"] = placements
    if design.custom_line_items:
        out["custom_line_items"] = [
            ci.model_dump(exclude_defaults=False, exclude_none=True) for ci in design.custom_line_items
        ]
    return out


def write_rack(path: Path, design: RackDesign) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(rack_to_dict(design), allow_unicode=True, sort_keys=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)          # atomic on POSIX
    return path
