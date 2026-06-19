"""Walk the library YAML, validate each spec, and split valid records from quarantine.

Invalid specs are never silently dropped: they go to a quarantine list (path + errors) that
the caller reports. Valid specs are turned into typed models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel

from ._yaml import DecimalSafeLoader, to_plain
from .models import build_spec
from .paths import CatalogPaths
from .validate import SchemaValidator


@dataclass
class SpecRecord:
    kind: str
    spec: BaseModel
    source_path: str


@dataclass
class Quarantined:
    kind: str
    source_path: str
    errors: list[str]


@dataclass
class ParseResult:
    records: list[SpecRecord] = field(default_factory=list)
    quarantine: list[Quarantined] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for rec in self.records:
            out[rec.kind] = out.get(rec.kind, 0) + 1
        return out


def _norm(name: str) -> str:
    """Normalize a vendor name for case/space-insensitive matching."""
    return name.strip().lower().replace(" ", "")


def iter_yaml(directory: Path):
    if not directory.exists():
        return
    matches: list[Path] = []
    for pattern in ("*.yaml", "*.yml"):
        matches.extend(directory.rglob(pattern))
    for path in sorted(matches):
        if path.is_file():
            yield path


def parse_catalog(
    paths: CatalogPaths,
    validator: SchemaValidator,
    vendors: list[str] | None = None,
    kinds: tuple[str, ...] = ("device", "module", "rack"),
) -> ParseResult:
    result = ParseResult()
    vendor_set = {_norm(v) for v in vendors} if vendors else None

    for kind in kinds:
        base = paths.types_dir(kind)
        for path in iter_yaml(base):
            vendor_dir = path.relative_to(base).parts[0]
            if vendor_set is not None and _norm(vendor_dir) not in vendor_set:
                continue
            try:
                # Decimal-safe load so multipleOf validation matches upstream exactly.
                data = yaml.load(path.read_text(), Loader=DecimalSafeLoader)
            except yaml.YAMLError as exc:
                result.quarantine.append(Quarantined(kind, str(path), [f"YAML parse error: {exc}"]))
                continue

            errors = validator.errors(kind, data)
            if errors:
                result.quarantine.append(Quarantined(kind, str(path), errors))
                continue

            try:
                spec = build_spec(kind, to_plain(data))
            except Exception as exc:  # model construction guard — should be rare post-validation
                result.quarantine.append(Quarantined(kind, str(path), [f"model error: {exc}"]))
                continue

            result.records.append(SpecRecord(kind, spec, str(path)))

    return result
