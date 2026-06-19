"""Load rack design YAML from the org-hierarchy directory tree.

The directory tree IS the hierarchy:
    offerings/<o>/regions/<r>/zones/<z>/rack-types/<type>/racks/<rack>.yaml

`load_racks(root)` accepts any node in the tree (the whole `offerings/`, a single offering,
a zone, …) and returns every rack design beneath it, each tagged with the hierarchy parsed
from its path. Parse/schema errors become issues (path + reason) — never silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from .models import RackDesign

# Path segment markers → hierarchy level name.
# Rack-Type (control/data/storage/network) is the purpose grouping under a zone.
_MARKERS = {
    "offerings": "offering",
    "regions": "region",
    "zones": "zone",
    "rack-types": "rack_type",
}


@dataclass
class Issue:
    path: str
    level: str                       # "error" | "warn"
    message: str
    index: Optional[int] = None      # placement index (None = file/rack-level)


@dataclass
class LoadedRack:
    rack_id: str
    path: str
    hierarchy: dict[str, str]
    design: RackDesign


@dataclass
class LoadResult:
    racks: list[LoadedRack] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def parse_hierarchy(path: Path) -> dict[str, str]:
    """Derive {offering, region, zone, rack_group} from a rack file path."""
    parts = path.parts
    out: dict[str, str] = {}
    for i, part in enumerate(parts):
        level = _MARKERS.get(part)
        if level and i + 1 < len(parts):
            out[level] = parts[i + 1]
    return out


def _iter_rack_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.parent.name == "racks" and path.suffix in (".yaml", ".yml") and path.is_file():
            yield path


def load_racks(root: Path) -> LoadResult:
    result = LoadResult()
    root = Path(root)
    if not root.exists():
        result.issues.append(Issue(str(root), "error", "path does not exist"))
        return result

    found = False
    for path in _iter_rack_files(root):
        found = True
        try:
            raw = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            result.issues.append(Issue(str(path), "error", f"YAML parse error: {exc}"))
            continue
        try:
            design = RackDesign.model_validate(raw)
        except ValidationError as exc:
            result.issues.append(Issue(str(path), "error", f"schema error: {exc.errors()[0]['msg']}"))
            continue
        result.racks.append(
            LoadedRack(
                rack_id=path.stem,
                path=str(path),
                hierarchy=parse_hierarchy(path),
                design=design,
            )
        )

    if not found:
        result.issues.append(Issue(str(root), "warn", "no rack files (.../racks/*.yaml) found"))
    return result
