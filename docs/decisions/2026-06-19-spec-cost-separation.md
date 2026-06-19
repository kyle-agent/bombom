# 2026-06-19 — Separate technical spec from cost; join by stable key

## Context
NetBox/devicetype-library has no cost field — cost is bombom's core value-add. The spec is
community-owned and changes on every upstream sync; cost is ours and changes on our own
schedule.

## Decision
Keep the community technical spec (read-only, synced) and the bombom cost overlay (ours,
time-versioned) in **separate files**, joined at BOM time by a stable key:
`manufacturer + slug`, falling back to `part_number`. Cost lives in `pricing/<vendor>.yaml`
as `PriceEntry` records with `unit_cost, currency, source, valid_from, valid_to`.

## Alternatives considered
- **Add a price field to the device YAML.** Rejected — every community update would
  conflict with or overwrite our prices; couples our data to a repo we don't own.
- **Single combined record per device.** Same coupling problem; loses clean sync.

## Consequences
- Community HW flows in untouched; our prices sit in a thin overlay on top.
- BOM valuation is point-in-time via `valid_from/valid_to` (business validity) plus git
  history (audit) — the two are independent on purpose.
- Requires a join step and handling of unmatched keys (missing price → flagged, not zero).

## Override conditions
None expected. If upstream ever adds authoritative pricing, reconsider — unlikely for a
community spec library.
