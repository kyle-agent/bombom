# 2026-06-19 — Org hierarchy: Offering→Region→Zone→RackGroup→Rack→Device

> **Update (2026-06-19):** the "Rack Group" level was renamed **Rack-Type** (purpose:
> control/data/storage/network) and the catalog physical-rack reference renamed
> **Rack Model** (`rack_model`). Directory `rack-groups/` → `rack-types/`. See
> ADR 2026-06-19-rack-type-vs-rack-model. The structure below is otherwise unchanged.

## Context
Our cloud org model differs from NetBox's. We need a placement hierarchy that matches how
designers think and that is reflected directly in git.

## Decision
Adopt the hierarchy **Offering → Region → Zone → Rack Group → Rack → Device**, and make
the **git directory tree mirror it exactly** (`offerings/<o>/regions/<r>/zones/<z>/
rack-groups/<g>/racks/<rack>.yaml`). Each rack file references a catalog `RackTypeSpec`
and lists mounted devices/modules at U positions, plus `custom_line_items`.

Mapping to NetBox: Offering = (new top tier), Region = Region, Zone = Site, Rack Group =
Location (formerly RackGroup), Rack = Rack, Device = Device. Only placement is
bombom-specific; the catalog (DeviceType/ModuleType/RackType) is reused as-is.

## Alternatives considered
- **Reuse NetBox's hierarchy as-is (Region/Site/Location).** Rejected — no Offering tier,
  and naming wouldn't match the team's mental model.
- **Flat designs with hierarchy as metadata fields.** Rejected — loses the
  "directory = hierarchy" property that makes git diffs/PRs scope cleanly per zone/rack.

## Consequences
- Per-zone / per-rack diffs and PRs are natural; the path encodes the full context.
- A rename/move of an org node is a directory move (git handles it, but tooling must
  update references).
- BOM rollups map onto subtrees (rack → group → zone → region → offering).

## Override conditions
Revisit if the hierarchy needs to vary by offering (non-uniform depth) — may require a
declared schema per offering rather than a fixed depth.
