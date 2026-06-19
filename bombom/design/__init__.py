"""Design layer: org hierarchy + rack/placement model (bombom's own data)."""

from .loader import Issue, LoadedRack, LoadResult, load_racks, parse_hierarchy
from .models import CatalogRef, CustomLineItem, Placement, RackDesign
from .validate import validate_rack

__all__ = [
    "Issue",
    "LoadedRack",
    "LoadResult",
    "load_racks",
    "parse_hierarchy",
    "CatalogRef",
    "CustomLineItem",
    "Placement",
    "RackDesign",
    "validate_rack",
]
