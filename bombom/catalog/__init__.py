"""Catalog subsystem: sync, parse, validate, and index the device-type library.

Git is the source of truth (the devicetype-library submodule + this repo). The SQLite
index built here is a rebuildable cache — never authoritative. See docs/DESIGN.md and
docs/decisions/2026-06-19-git-as-backend.md.
"""

from .models import DeviceTypeSpec, ModuleTypeSpec, RackTypeSpec
from .paths import CatalogPaths
from .index import reindex, IndexSummary
from .query import Catalog, CatalogError
from .sync import sync

__all__ = [
    "DeviceTypeSpec",
    "ModuleTypeSpec",
    "RackTypeSpec",
    "CatalogPaths",
    "reindex",
    "IndexSummary",
    "Catalog",
    "CatalogError",
    "sync",
]
