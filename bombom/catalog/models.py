"""Typed models for device / module / rack types.

Strict validation is done against the upstream JSON Schema (see validate.py); these models
give typed, attribute access for the rest of bombom. They are deliberately lenient
(`extra="allow"`) so that fields we don't model yet survive a round-trip through the index.
Cost/price never appears here — spec stays separate from cost (ADR spec-cost-separation).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# populate_by_name lets us construct from either the hyphenated YAML keys (via alias) or the
# python field names; protected_namespaces=() silences pydantic's `model_*` warning since we
# have a field literally named `model`.
_BASE = ConfigDict(extra="allow", populate_by_name=True, protected_namespaces=())


class Component(BaseModel):
    model_config = _BASE
    name: str
    label: Optional[str] = None
    type: Optional[str] = None


class PowerPort(Component):
    # Watts — the basis for power-capacity rollup later (BOM feature).
    maximum_draw: Optional[int] = None
    allocated_draw: Optional[int] = None


class _WithComponents(BaseModel):
    model_config = _BASE
    interfaces: list[Component] = Field(default_factory=list)
    console_ports: list[Component] = Field(default_factory=list, alias="console-ports")
    console_server_ports: list[Component] = Field(
        default_factory=list, alias="console-server-ports"
    )
    power_ports: list[PowerPort] = Field(default_factory=list, alias="power-ports")
    power_outlets: list[Component] = Field(default_factory=list, alias="power-outlets")
    front_ports: list[Component] = Field(default_factory=list, alias="front-ports")
    rear_ports: list[Component] = Field(default_factory=list, alias="rear-ports")
    module_bays: list[Component] = Field(default_factory=list, alias="module-bays")
    device_bays: list[Component] = Field(default_factory=list, alias="device-bays")


class DeviceTypeSpec(_WithComponents):
    manufacturer: str
    model: str
    slug: str
    u_height: float
    is_full_depth: bool = True
    part_number: Optional[str] = None
    weight: Optional[float] = None
    weight_unit: Optional[str] = None
    airflow: Optional[str] = None
    is_powered: bool = True

    @property
    def ident(self) -> str:
        return self.slug


class ModuleTypeSpec(_WithComponents):
    # Module types have no slug in the upstream schema — identity is manufacturer + model
    # (part_number when present).
    manufacturer: str
    model: str
    part_number: Optional[str] = None
    slug: Optional[str] = None
    weight: Optional[float] = None
    weight_unit: Optional[str] = None
    airflow: Optional[str] = None

    @property
    def ident(self) -> str:
        # Modules have no slug, and part_number is not unique (distinct models can share
        # one). model+part_number is unique across the whole library, so it's the dedup key.
        return f"{self.model}|{self.part_number or ''}"


class RackTypeSpec(BaseModel):
    model_config = _BASE
    manufacturer: str
    model: str
    slug: str
    u_height: float
    form_factor: Optional[str] = None
    width: Optional[int] = None
    starting_unit: Optional[int] = None
    weight: Optional[float] = None
    max_weight: Optional[float] = None
    weight_unit: Optional[str] = None
    airflow: Optional[str] = None

    @property
    def ident(self) -> str:
        return self.slug


SPEC_CLASSES: dict[str, type[BaseModel]] = {
    "device": DeviceTypeSpec,
    "module": ModuleTypeSpec,
    "rack": RackTypeSpec,
}


def build_spec(kind: str, data: dict) -> BaseModel:
    """Construct the typed model for a validated raw spec dict."""
    return SPEC_CLASSES[kind].model_validate(data)
