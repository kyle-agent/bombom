"""Strict validation against the upstream devicetype-library JSON Schema.

The library's schema files reference each other by URN ``$id`` (e.g.
``urn:devicetype-library:components``); we load all of them into a referencing registry so
the cross-references resolve. If a kind has no published schema, we fall back to minimal
required-field checks rather than skipping validation entirely.
"""

from __future__ import annotations

import decimal
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

KIND_SCHEMA_URI = {
    "device": "urn:devicetype-library:device-type",
    "module": "urn:devicetype-library:module-type",
    "rack": "urn:devicetype-library:rack-type",
}

# Used only when a schema for a kind is absent (defensive — all three ship a schema today).
_REQUIRED_MIN = {
    "device": ["manufacturer", "model", "slug", "u_height"],
    "module": ["manufacturer", "model"],
    "rack": ["manufacturer", "model", "slug", "u_height"],
}


class SchemaValidator:
    def __init__(self, schema_dir: Path):
        resources: list[tuple[str, Resource]] = []
        for path in sorted(Path(schema_dir).glob("*.json")):
            # parse_float=Decimal so multipleOf divisors (0.01, 0.5) are exact.
            contents = json.loads(path.read_text(), parse_float=decimal.Decimal)
            uri = contents.get("$id")
            if uri:
                resources.append((uri, Resource.from_contents(contents)))
        if not resources:
            raise FileNotFoundError(f"no schema files with $id found in {schema_dir}")
        self.registry = Registry().with_resources(resources)
        loaded = {uri for uri, _ in resources}
        self._validators: dict[str, Draft202012Validator] = {
            kind: Draft202012Validator({"$ref": uri}, registry=self.registry)
            for kind, uri in KIND_SCHEMA_URI.items()
            if uri in loaded
        }

    def has_schema(self, kind: str) -> bool:
        return kind in self._validators

    def errors(self, kind: str, data) -> list[str]:
        """Return a list of human-readable validation errors ([] means valid)."""
        validator = self._validators.get(kind)
        if validator is None:
            return _minimal_errors(kind, data)
        out = []
        # Stringify path elements before sorting: paths mix property names (str) and array
        # indices (int), which are not orderable against each other in Python 3.
        for err in sorted(validator.iter_errors(data), key=lambda e: [str(p) for p in e.path]):
            loc = "/".join(str(p) for p in err.path) or "<root>"
            out.append(f"{loc}: {err.message}")
        return out


def _minimal_errors(kind: str, data) -> list[str]:
    if not isinstance(data, dict):
        return ["<root>: expected a mapping"]
    return [
        f"<root>: missing required field '{field}'"
        for field in _REQUIRED_MIN.get(kind, [])
        if field not in data
    ]
