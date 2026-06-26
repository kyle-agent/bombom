"""Device meta / custom fields (ours) — NetBox-style custom fields kept out of the catalog.

- Definitions: `meta/fields.yaml` declare which extra fields exist, their type, whether they
  are required, where they apply (device_type vs placement), and the scope they apply to
  (all / category:<c> / role:<r>).
- Type-level values: `meta/devicetypes/<vendor>.yaml` (slug → {field: value}).
- Instance-level values: the placement's `meta:` block in the rack YAML.

`required_missing(...)` evaluates conditional requireds against a given category/role.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

FIELD_TYPES = ("string", "int", "enum", "bool", "date")


class FieldDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str = ""
    type: str = "string"
    options: list[str] = Field(default_factory=list)
    required: bool = False
    applies_to: str = "placement"        # "device_type" | "placement"
    scope: str = "all"                    # "all" | "category:<c>" | "role:<r>"

    def in_scope(self, *, category: Optional[str], role: Optional[str]) -> bool:
        if self.scope == "all":
            return True
        kind, _, value = self.scope.partition(":")
        if kind == "category":
            return category == value
        if kind == "role":
            return role == value
        return False


def load_fields(fields_path: Path) -> list[FieldDef]:
    fields_path = Path(fields_path)
    if not fields_path.exists():
        return []
    doc = yaml.safe_load(fields_path.read_text()) or {}
    return [FieldDef.model_validate(f) for f in doc.get("fields", [])]


def save_fields(fields_path: Path, defs: list[FieldDef]) -> Path:
    """Serialize the full field-def list back to meta/fields.yaml (round-trips every applies_to).

    Only non-default attributes are written so the file stays readable. Returns the path."""
    fields_path = Path(fields_path)
    fields_path.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for d in defs:
        row = {"key": d.key, "label": d.label or d.key, "type": d.type,
               "applies_to": d.applies_to, "scope": d.scope}
        if d.required:
            row["required"] = True
        if d.options:
            row["options"] = list(d.options)
        out.append(row)
    fields_path.write_text(yaml.safe_dump({"fields": out}, allow_unicode=True, sort_keys=False))
    return fields_path


class TypeMetaBook:
    """Type-level meta values (slug → {field: value}) from meta/devicetypes/*.yaml."""

    def __init__(self, values: dict[str, dict[str, Any]] | None = None, dir_: Path | None = None):
        self._values = values or {}
        self._dir = dir_

    @classmethod
    def load(cls, devicetypes_dir: Path) -> "TypeMetaBook":
        devicetypes_dir = Path(devicetypes_dir)
        values: dict[str, dict[str, Any]] = {}
        if devicetypes_dir.exists():
            for path in sorted(devicetypes_dir.glob("*.y*ml")):
                doc = yaml.safe_load(path.read_text()) or {}
                for entry in doc.get("entries", []):
                    slug = entry.get("slug")
                    if slug:
                        values.setdefault(slug, {}).update(
                            {k: v for k, v in entry.items() if k != "slug"}
                        )
        return cls(values, devicetypes_dir)

    def get(self, slug: str) -> dict[str, Any]:
        return dict(self._values.get(slug, {}))

    def set(self, slug: str, key: str, value: Any, *, vendor: str = "misc") -> None:
        self._values.setdefault(slug, {})[key] = value
        if self._dir is not None:
            self._dir.mkdir(parents=True, exist_ok=True)
            # reuse the file that already holds this slug (avoid split-slug across vendors)
            path = self._dir / f"{vendor}.yaml"
            for p in sorted(self._dir.glob("*.y*ml")):
                doc = yaml.safe_load(p.read_text()) or {}
                if any(e.get("slug") == slug for e in doc.get("entries", [])):
                    path = p
                    break
            existing = {}
            if path.exists():
                existing = yaml.safe_load(path.read_text()) or {}
            by_slug = {e["slug"]: e for e in existing.get("entries", []) if "slug" in e}
            by_slug.setdefault(slug, {"slug": slug})[key] = value
            path.write_text(
                yaml.safe_dump({"entries": list(by_slug.values())}, allow_unicode=True, sort_keys=False)
            )


def required_missing(
    fields: list[FieldDef],
    values: dict[str, Any],
    *,
    applies_to: str,
    category: Optional[str] = None,
    role: Optional[str] = None,
) -> list[str]:
    """Return the keys of required fields (for this applies_to + scope) with no value."""
    missing = []
    for f in fields:
        if f.applies_to != applies_to or not f.required:
            continue
        if not f.in_scope(category=category, role=role):
            continue
        if values.get(f.key) in (None, ""):
            missing.append(f.key)
    return missing
