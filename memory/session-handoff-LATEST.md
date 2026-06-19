# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

## Priority 1

Build the **price overlay + BOM engine** (next feature; run `/brief` first). The catalog
query API (`bombom.catalog.Catalog`) is the read side; add `pricing/<vendor>.yaml`
(PriceEntry: key→unit_cost/currency/source/valid_from/valid_to), join by
`manufacturer+slug` (device/rack) or `model`/`part_number` (module), and compute a CAPEX
rollup. Keep price strictly separate from the catalog (ADR spec-cost-separation).

Alternative next feature: the **org hierarchy + rack model** (Offering→…→Rack YAML +
placement), which the rack-elevation UI later renders.

## Open decisions

- Which feature next: BOM engine vs rack model. (BOM validates cost early; rack model
  unblocks the UI.)
- Frontend framework: React vs Svelte (deferred until UI work).

## Blockers

None.

## Context notes

Catalog sync is DONE and pushed (commit 71841e8). All BRIEF.md exit criteria verified
against real data: `device=5802, module=1863, rack=65`, idempotent + reproducible.
- Entry points: `from bombom.catalog import Catalog, reindex, sync`; CLI `bombom catalog …`.
- Dev: `python -m venv .venv && pip install -e .`; tests `pytest -q` (15 pass);
  lint `ruff check bombom tests`.
- The devicetype-library is a submodule pinned at bb6a9b1 — run `bombom catalog sync` after
  a fresh clone (`git submodule update --init`), then `bombom catalog reindex` (~47s full).
- Index `.index/` is a gitignored rebuildable cache; git is the source of truth.
