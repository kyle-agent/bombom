"""Create base data (the org hierarchy) as YAML skeletons, and clone subtrees.

This is how designers *enter* base data without hand-writing the directory tree. Paths follow
offerings/<o>/regions/<r>/zones/<z>/rack-types/<type>/racks/<rack>.yaml.
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


def scaffold_rack_type(root: Path, offering: str, region: str, zone: str, rack_type: str,
                       *, name: str | None = None) -> Path:
    # rack_type = purpose: control / data / storage / network
    base = (Path(root) / "offerings" / offering / "regions" / region / "zones" / zone
            / "rack-types" / rack_type)
    return _write(base / "rack-type.yaml", {"name": name or rack_type})


def scaffold_rack(root: Path, offering: str, region: str, zone: str, rack_type: str, rack: str,
                  *, rack_model_slug: str) -> Path:
    # rack_model = the chosen physical rack from the catalog (e.g. vertiv-vr3300)
    base = (Path(root) / "offerings" / offering / "regions" / region / "zones" / zone
            / "rack-types" / rack_type / "racks")
    return _write(base / f"{rack}.yaml", {"rack_model": {"slug": rack_model_slug}, "placements": []})


def clone_rack(src: Path, dst_rack: str) -> Path:
    """Copy one rack file to a new rack id in the same rack-type dir, placements and all.

    A byte-for-byte copy: every Placement (device, position, release, qty, meta) and custom
    line item is preserved, so "lay one rack out, then make N more like it" is one call each.
    The new rack inherits its hierarchy from the destination path (same as the source)."""
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(f"clone source must be a rack file: {src}")
    if not dst_rack or "/" in dst_rack or "\\" in dst_rack or ".." in dst_rack:
        raise ValueError(f"unsafe rack id: {dst_rack!r}")   # self-defending; API also validates
    dst = src.parent / f"{dst_rack}.yaml"
    if dst.exists():
        raise FileExistsError(f"already exists: {dst}")
    shutil.copy2(src, dst)
    return dst


def clone_racks(src: Path, dst_racks: list[str]) -> list[Path]:
    """Clone one rack into several new ids at once (lay one rack out, stamp N more like it).

    All-or-nothing on conflicts: every destination is checked free before any copy, so a
    collision aborts the batch without writing a partial set."""
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(f"clone source must be a rack file: {src}")
    targets: list[Path] = []
    for name in dst_racks:
        if not name or "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"unsafe rack id: {name!r}")
        dst = src.parent / f"{name}.yaml"
        if dst.exists() or dst in targets:
            raise FileExistsError(f"already exists: {dst}")
        targets.append(dst)
    for dst in targets:
        shutil.copy2(src, dst)
    return targets


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
    for meta_name in ("zone.yaml", "region.yaml", "rack-type.yaml", "offering.yaml"):
        meta = dst / meta_name
        if meta.exists():
            doc = yaml.safe_load(meta.read_text()) or {}
            doc["name"] = dst_name
            meta.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
            break
    return dst
