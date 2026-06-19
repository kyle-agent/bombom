# 2026-06-19 — Rack-Type (purpose) vs Rack Model (catalog), and how a rack is chosen

## Context
"Rack type" was overloaded: the hierarchy grouping under a Zone (control/data/storage/
network) and the physical rack enclosure from the catalog (vertiv-vr3300) were both called
"rack type". Designers also needed a clear answer to "how do I choose the physical rack?".

## Decision
- **Rack-Type = purpose** (control / data / storage / network). It is the **directory level**
  under a Zone: `…/zones/<z>/rack-types/<type>/racks/<rack>.yaml`. The purpose is derived
  from the directory, not stored as a field on the rack.
- **Rack Model = the physical rack enclosure** from the catalog (a `RackTypeSpec`, e.g.
  vertiv-vr3300). A rack file references it as `rack_model: { slug: … }`. Choosing a rack =
  picking a Rack Model from the catalog (65 rack types), which sets U-height etc.
- Hierarchy is **Offering → Region → Zone → Rack-Type → Rack → Device**.

## Alternatives considered
- Keep "rack type" for the catalog enclosure and call the grouping "Rack Group"/"Role".
  Rejected — the team's mental model names the grouping level "Rack-Type"; the collision is
  avoided by renaming the catalog reference to "Rack Model".
- Store purpose as a `role` field on each rack. Rejected — duplicates the directory level and
  invites drift; the directory is the single source.

## Consequences
- Design layer renamed: `RackDesign.rack_type` → `rack_model`; `role` removed (purpose from
  dir); loader marker `rack-groups`→`rack-types` (key `rack_type`). Catalog package
  (`RackTypeSpec`, `get_rack_type`, kind="rack") is unchanged — it still defines physical
  racks; "Rack Model" is just our name for a reference to one.
- A **Rack Model picker** exists: `GET /api/catalog/search?kind=rack`, surfaced in the editor;
  CLI `scaffold rack … --rack-model <slug>`.
- Meta `scope: role:<purpose>` and per-purpose rollups read the directory's rack-type.

## Override conditions
If a rack ever needs a purpose independent of its directory location, reintroduce an explicit
purpose field (and reconcile with the directory).
