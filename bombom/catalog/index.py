"""Build the SQLite query index from the library.

`reindex` is a full rebuild (DROP + CREATE + INSERT), which makes it idempotent: running it
again on unchanged files yields identical rows. The index is a rebuildable cache — deleting
it and rebuilding reproduces the same state from git (ADR git-as-backend).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .parse import Quarantined, parse_catalog
from .paths import CatalogPaths, default_index_db
from .validate import SchemaValidator

_DDL = """
CREATE TABLE specs (
    kind          TEXT NOT NULL,
    manufacturer  TEXT NOT NULL,
    model         TEXT NOT NULL,
    slug          TEXT,
    part_number   TEXT,
    ident         TEXT NOT NULL,
    u_height      REAL,
    weight        REAL,
    weight_unit   TEXT,
    airflow       TEXT,
    source_path   TEXT NOT NULL,
    data          TEXT NOT NULL,
    PRIMARY KEY (kind, manufacturer, ident)
);
CREATE INDEX idx_specs_kind ON specs(kind);
CREATE INDEX idx_specs_manufacturer ON specs(manufacturer COLLATE NOCASE);
CREATE INDEX idx_specs_slug ON specs(slug);
"""


@dataclass
class IndexSummary:
    counts: dict[str, int]
    quarantine: list[Quarantined]
    db_path: str


def reindex(
    db_path: Path | str | None = None,
    paths: CatalogPaths | None = None,
    vendors: list[str] | None = None,
    kinds: tuple[str, ...] = ("device", "module", "rack"),
) -> IndexSummary:
    paths = paths or CatalogPaths.default()
    db_path = Path(db_path or default_index_db())
    validator = SchemaValidator(paths.schema_dir)
    result = parse_catalog(paths, validator, vendors=vendors, kinds=kinds)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript("DROP TABLE IF EXISTS specs;" + _DDL)
        rows = []
        for rec in result.records:
            spec = rec.spec
            payload = json.dumps(
                spec.model_dump(by_alias=True, exclude_none=True),
                ensure_ascii=False,
                sort_keys=True,
            )
            rows.append(
                (
                    rec.kind,
                    spec.manufacturer,
                    spec.model,
                    getattr(spec, "slug", None),
                    getattr(spec, "part_number", None),
                    spec.ident,
                    getattr(spec, "u_height", None),
                    spec.weight,
                    spec.weight_unit,
                    spec.airflow,
                    rec.source_path,
                    payload,
                )
            )
        # INSERT OR REPLACE collapses any duplicate (kind, manufacturer, ident) — dedup.
        con.executemany(
            "INSERT OR REPLACE INTO specs "
            "(kind, manufacturer, model, slug, part_number, ident, u_height, weight, "
            " weight_unit, airflow, source_path, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.commit()
        counts = {
            kind: con.execute("SELECT COUNT(*) FROM specs WHERE kind = ?", (kind,)).fetchone()[0]
            for kind in kinds
        }
    finally:
        con.close()

    return IndexSummary(counts=counts, quarantine=result.quarantine, db_path=str(db_path))
