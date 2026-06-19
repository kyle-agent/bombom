"""Design-side models: the org hierarchy, racks, and placements (bombom's own data).

These are *our* files (not the community catalog), so validation is strict (extra fields are
rejected) to catch typos in hand/UI-written YAML. Cost never lives here — it is joined from
the pricing overlay at BOM time (ADR spec-cost-separation).
"""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

_BASE = ConfigDict(extra="forbid")


class CatalogRef(BaseModel):
    model_config = _BASE
    slug: str
    manufacturer: Optional[str] = None


class Placement(BaseModel):
    model_config = _BASE
    device: str                          # catalog device slug (manufacturer-prefixed, unique)
    position: int                        # bottom-most rack unit (U)
    release: str                         # release tag, e.g. "R26.07"
    qty: int = Field(default=1, ge=1)    # multiplies this line (default 1); see BRIEF risk note
    meta: dict[str, Any] = Field(default_factory=dict)   # instance-level designer fields


class CustomLineItem(BaseModel):
    model_config = _BASE
    name: str
    qty: int = Field(default=1, ge=1)
    unit_cost: int = Field(ge=0)         # KRW
    release: Optional[str] = None
    category: str = "other"


class RackDesign(BaseModel):
    model_config = _BASE
    rack_type: CatalogRef                 # the physical rack from the catalog
    role: Optional[str] = None            # our classification: control/data/storage/network
    placements: list[Placement] = Field(default_factory=list)
    custom_line_items: list[CustomLineItem] = Field(default_factory=list)

    @field_validator("rack_type", mode="before")
    @classmethod
    def _coerce_rack_type(cls, value: Union[str, dict, CatalogRef]):
        # Allow `rack_type: some-slug` shorthand in addition to `{slug: ...}`.
        if isinstance(value, str):
            return {"slug": value}
        return value
