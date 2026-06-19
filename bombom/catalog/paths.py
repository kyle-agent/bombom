"""Filesystem locations for the catalog. Override `library_dir` for tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Map our internal kind names to the devicetype-library top-level directories.
KIND_DIRS = {
    "device": "device-types",
    "module": "module-types",
    "rack": "rack-types",
}
KINDS = tuple(KIND_DIRS)


def repo_root() -> Path:
    # bombom/catalog/paths.py -> repo root is three levels up.
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CatalogPaths:
    """Where the vendored device-type library lives."""

    library_dir: Path

    @property
    def schema_dir(self) -> Path:
        return self.library_dir / "schema"

    def types_dir(self, kind: str) -> Path:
        return self.library_dir / KIND_DIRS[kind]

    @classmethod
    def default(cls) -> "CatalogPaths":
        return cls(repo_root() / "vendor" / "devicetype-library")


def default_index_db() -> Path:
    return repo_root() / ".index" / "catalog.db"
