# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

## Priority 1

Pick the first feature to build and run `/brief` to lock its scope. Strong candidate:
the **catalog sync + index** (devicetype-library submodule → parse → rebuildable SQLite
index), since the BOM engine, rack model, and UI all depend on it. Alternatively the
**BOM engine** against a hand-seeded catalog to validate the cost rollup early.

## Open decisions

- First feature target (catalog sync vs BOM engine vs rack model) — decide in `/brief`.
- Frontend framework: React vs Svelte (deferred; backend-first is fine).
- Deployment specifics (container/runtime) — TBD.

## Blockers

None.

## Context notes

High-level design is locked: see `docs/DESIGN.md` and 5 ADRs in `docs/decisions/`
(library-only catalog, git-as-backend, spec/cost separation, org hierarchy, app stack).
CLAUDE.md now reflects purpose + stack. No application code exists yet — `scope before
code` means `/brief` + `/freeze` before the first implementation.
