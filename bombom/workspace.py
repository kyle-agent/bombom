"""A workspace bundles the read-only catalog with the org overlays (pricing/category/meta)
loaded from a repo root. Reused by the BOM CLI, the API, and the static export.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bom import PriceBook
from .catalog import Catalog
from .overlay import CategoryBook, FieldDef, TypeMetaBook, load_fields


@dataclass
class Workspace:
    root: Path
    catalog: Catalog
    pricebook: PriceBook
    categories: CategoryBook
    fields: list[FieldDef]
    type_meta: TypeMetaBook

    @classmethod
    def open(cls, root: Path | str = ".", *, db_path: Path | None = None) -> "Workspace":
        root = Path(root)
        return cls(
            root=root,
            catalog=Catalog(db_path),
            pricebook=PriceBook.load(root / "pricing"),
            categories=CategoryBook.load(root / "categories" / "overlay.yaml"),
            fields=load_fields(root / "meta" / "fields.yaml"),
            type_meta=TypeMetaBook.load(root / "meta" / "devicetypes"),
        )
