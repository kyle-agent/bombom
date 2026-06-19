"""Create base data (the org hierarchy) as YAML skeletons, and clone subtrees.

This is how designers *enter* base data without hand-writing the directory tree. Paths follow
offerings/<o>/regions/<r>/zones/<z>/rack-groups/<g>/racks/<rack>.yaml.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml


def _write(path: Path, data: dict, *, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return path


def scaffold_offering(root: Path, offering: str, *, name: str | None = None) -> Path:
    return _write(Path(root) / "offerings" / offering / "offering.yaml",
                  {"name": name or offering})


def scaffold_region(root: Path, offering: str, region: str, *, name: str | None = None) -> Path:
    base = Path(root) / "offerings" / offering / "regions" / region
    return _write(base / "region.yaml", {"name": name or region})


def scaffold_zone(root: Path, offering: str, region: str, zone: str, *, name: str | None = None) -> Path:
    base = Path(root) / "offerings" / offering / "regions" / region / "zones" / zone
    return _write(base / "zone.yaml", {"name": name or zone})


def scaffold_rack_group(root: Path, offering: str, region: str, zone: str, group: str,
                        *, name: str | None = None) -> Path:
    base = (Path(root) / "offerings" / offering / "regions" / region / "zones" / zone
            / "rack-groups" / group)
    return _write(base / "rack-group.yaml", {"name": name or group})


def scaffold_rack(root: Path, offering: str, region: str, zone: str, group: str, rack: str,
                  *, rack_type_slug: str, role: str | None = None) -> Path:
    base = (Path(root) / "offerings" / offering / "regions" / region / "zones" / zone
            / "rack-groups" / group / "racks")
    data = {"rack_type": {"slug": rack_type_slug}, "placements": []}
    if role:
        data = {"rack_type": {"slug": rack_type_slug}, "role": role, "placements": []}
    return _write(base / f"{rack}.yaml", data)


def clone_subtree(src: Path, dst_name: str) -> Path:
    """Copy a hierarchy subtree to a sibling with a new identifier (new region/zone bootstrap)."""
    src = Path(src)
    if not src.is_dir():
        raise NotADirectoryError(f"clone source must be a directory: {src}")
    dst = src.parent / dst_name
    if dst.exists():
        raise FileExistsError(f"already exists: {dst}")
    shutil.copytree(src, dst)
    # rename the node's own meta file (region.yaml/zone.yaml/...) name field if present
    for meta_name in ("zone.yaml", "region.yaml", "rack-group.yaml", "offering.yaml"):
        meta = dst / meta_name
        if meta.exists():
            doc = yaml.safe_load(meta.read_text()) or {}
            doc["name"] = dst_name
            meta.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
            break
    return dst
