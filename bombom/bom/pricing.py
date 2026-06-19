"""Pricing overlay (ours) — KRW unit costs joined to the catalog by key.

Files live in `pricing/<vendor>.yaml`:

    entries:
      - slug: dell-poweredge-r760     # device/rack key (manufacturer-prefixed slug)
        unit_cost: 19500000           # KRW
        valid_from: 2025-01-01        # optional; point-in-time selection
        valid_to: 2025-12-31          # optional (open-ended if omitted)
        source: "vendor quote 2025Q1"
      - model: TEST-NIC               # module key (no slug upstream)
        part_number: TN-1
        unit_cost: 1200000

Never written into catalog or design files (ADR spec-cost-separation).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class PriceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_cost: int = Field(ge=0)         # KRW
    currency: str = "KRW"
    slug: Optional[str] = None
    model: Optional[str] = None
    part_number: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    source: Optional[str] = None

    @model_validator(mode="after")
    def _require_key(self):
        if not (self.slug or self.model or self.part_number):
            raise ValueError("price entry needs one of: slug, model, part_number")
        return self

    def covers(self, as_of: date) -> bool:
        if self.valid_from and as_of < self.valid_from:
            return False
        if self.valid_to and as_of > self.valid_to:
            return False
        return True


def _pick(entries: list[PriceEntry], as_of: date) -> Optional[PriceEntry]:
    # Most recent valid_from that brackets as_of wins; undated entries are the fallback.
    # Ties (equal valid_from) break on unit_cost so the result is deterministic, not file-order.
    covering = [e for e in entries if e.covers(as_of)]
    if not covering:
        return None
    return max(covering, key=lambda e: (e.valid_from is not None, e.valid_from or date.min, e.unit_cost))


class PriceBook:
    def __init__(self) -> None:
        self._by_slug: dict[str, list[PriceEntry]] = {}
        self._by_pn: dict[str, list[PriceEntry]] = {}
        self._by_model: dict[str, list[PriceEntry]] = {}
        self.issues: list[tuple[str, str]] = []          # (path, message) — never raised

    @classmethod
    def load(cls, pricing_dir: Path) -> "PriceBook":
        book = cls()
        pricing_dir = Path(pricing_dir)
        if not pricing_dir.exists():
            return book
        files = sorted([*pricing_dir.glob("*.yaml"), *pricing_dir.glob("*.yml")])
        for path in files:
            try:
                doc = yaml.safe_load(path.read_text()) or {}
            except yaml.YAMLError as exc:
                book.issues.append((str(path), f"YAML parse error: {exc}"))
                continue
            for raw in doc.get("entries", []):
                try:
                    entry = PriceEntry.model_validate(raw)
                except ValidationError as exc:
                    book.issues.append((str(path), f"invalid price entry: {exc.errors()[0]['msg']}"))
                    continue
                if entry.slug:
                    book._by_slug.setdefault(entry.slug, []).append(entry)
                if entry.part_number:
                    book._by_pn.setdefault(entry.part_number, []).append(entry)
                if entry.model:
                    book._by_model.setdefault(entry.model, []).append(entry)
        return book

    def lookup(
        self,
        as_of: date,
        *,
        slug: Optional[str] = None,
        part_number: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Optional[PriceEntry]:
        for table, key in ((self._by_slug, slug), (self._by_pn, part_number), (self._by_model, model)):
            if key and key in table:
                hit = _pick(table[key], as_of)
                if hit:
                    return hit
        return None
