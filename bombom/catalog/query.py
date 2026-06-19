"""Read-only query API over the catalog index. The surface the BOM engine, rack model, and
UI build on. Join key is the slug (device/rack); modules join on manufacturer + model.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from .models import DeviceTypeSpec, ModuleTypeSpec, RackTypeSpec
from .paths import default_index_db


class CatalogError(RuntimeError):
    pass


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


class Catalog:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = str(db_path or default_index_db())

    def _connect(self) -> sqlite3.Connection:
        if not os.path.exists(self.db_path):
            raise CatalogError(
                f"catalog index not found at {self.db_path} — run `bombom catalog reindex` first"
            )
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def get_device_type(self, slug: str, *, manufacturer: str | None = None) -> DeviceTypeSpec | None:
        # slug is the globally-unique key. `manufacturer` is keyword-only so a positional
        # (manufacturer, slug) mix-up fails loudly instead of silently returning None.
        # Accept either the full library slug ("dell-poweredge-r760") or a bare model slug
        # plus a manufacturer; try the vendor-qualified form first when a manufacturer is given.
        candidates = []
        if manufacturer:
            candidates.append(f"{_slugify(manufacturer)}-{slug}")
        candidates.append(slug)
        with self._connect() as con:
            for candidate in candidates:
                row = con.execute(
                    "SELECT data FROM specs WHERE kind = 'device' AND slug = ?", (candidate,)
                ).fetchone()
                if row:
                    return DeviceTypeSpec.model_validate(json.loads(row["data"]))
        return None

    def get_rack_type(self, slug: str) -> RackTypeSpec | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT data FROM specs WHERE kind = 'rack' AND slug = ?", (slug,)
            ).fetchone()
        return RackTypeSpec.model_validate(json.loads(row["data"])) if row else None

    def get_module_type(
        self, manufacturer: str, model: str | None = None, part_number: str | None = None
    ) -> ModuleTypeSpec | None:
        if model is None and part_number is None:
            raise ValueError("get_module_type requires model or part_number")
        # AND the supplied fields so model+part_number is an exact match. ORDER BY model
        # makes a part_number-only lookup deterministic when several modules share one.
        clauses = ["kind = 'module'", "manufacturer = ? COLLATE NOCASE"]
        params: list = [manufacturer]
        if model is not None:
            clauses.append("model = ?")
            params.append(model)
        if part_number is not None:
            clauses.append("part_number = ?")
            params.append(part_number)
        sql = "SELECT data FROM specs WHERE " + " AND ".join(clauses) + " ORDER BY model"
        with self._connect() as con:
            row = con.execute(sql, params).fetchone()
        return ModuleTypeSpec.model_validate(json.loads(row["data"])) if row else None

    def list_by_vendor(self, manufacturer: str, kind: str | None = None) -> list[dict]:
        sql = (
            "SELECT kind, manufacturer, model, slug, part_number "
            "FROM specs WHERE manufacturer = ? COLLATE NOCASE"
        )
        params: list = [manufacturer]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY kind, model"
        with self._connect() as con:
            return [dict(r) for r in con.execute(sql, params).fetchall()]

    def counts(self) -> dict[str, int]:
        with self._connect() as con:
            return {
                row["kind"]: row["n"]
                for row in con.execute("SELECT kind, COUNT(*) AS n FROM specs GROUP BY kind")
            }
