# 2026-06-19 — Quantity is derived from rack placement, not from selection

## Context
The designer works in two steps: select model types, then place them in racks. Quantity
feeds the rack elevation, the device list, and the BOM. We need one unambiguous source of
truth for "how many of X".

## Decision
Quantity is derived **solely from rack placements** (step 2). Step-1 selection is a
shortlist with no quantity attached. The device list, elevation, and BOM all read the count
of placed instances. Bulk placement (place N / fill contiguous U / repeat across racks) is
provided so placing many units isn't tedious.

## Alternatives considered
- **Hybrid: optional target quantity at selection + actual from placement.** Useful for
  capacity planning ("planned 40, placed 38"), but adds a plan-vs-actual reconciliation
  surface. Deferred — can be layered on later without changing the placement model.
- **Fix quantity at selection, distribute at placement.** Rejected: creates plan/actual
  drift and lets a BOM include gear that isn't physically placed.

## Consequences
- The BOM and device list always equal physical reality — you cannot cost an unplaced unit.
- Cannot represent "planned but not yet placed" demand (acceptable for MVP).
- Requires an efficient bulk-placement UX so large counts are practical.

## Override conditions
If demand/capacity planning becomes a goal, add a planning-target layer above placement
(the hybrid) — placement stays the source of truth for actuals.
