# Architecture Decision Records

Non-obvious design and architecture decisions live here, one file per decision, created
by the `/adr` skill.

## Why

Code shows *what* was built. An ADR records *why* — the forcing function, the
alternatives that were rejected, and the conditions under which the decision should be
revisited. This stops future sessions from re-litigating settled choices.

## Naming

`YYYY-MM-DD-<short-title>.md`

## What an ADR contains

- **Context** — the forcing function (what made this decision necessary).
- **Decision** — what was chosen.
- **Alternatives considered** — and why they were rejected. (Never fabricated; if none
  were seriously considered, say so.)
- **Consequences** — what this commits us to, good and bad.
- **Override conditions** — what would make us reverse this.

Write one with `/adr` after any decision that isn't self-evident from the code.

## Index (current)

**Foundational architecture**
- `2026-06-19-app-stack.md` — FastAPI backend + vanilla-JS pages, no build step.
- `2026-06-19-git-as-backend.md` — Git/YAML is the source of truth; SQLite index is a rebuildable cache.
- `2026-06-19-library-only-catalog.md` — hardware specs reused read-only from NetBox `devicetype-library`.
- `2026-06-19-org-hierarchy.md` — Offering→Region→Zone→Rack-Type→Rack directory tree IS the hierarchy.
- `2026-06-19-spec-cost-separation.md` — prices live in `pricing/`, never in device specs.
- `2026-06-19-rack-type-vs-rack-model.md` — org "rack-type" (purpose) vs catalog "rack model" (enclosure).
- `2026-06-19-quantity-from-placement.md` — quantities derive from placements, not stored counts.
- `2026-06-19-device-categorization.md` — server/network/storage/other category overlay.

**Feature / capability decisions**
- `2026-06-20-candidate-pool.md` — curated candidate pool + price/meta overlay (the 후보풀 model).
- `2026-06-20-confirm-workflow.md` — release/build confirmation → annotated git tag seal.
- `2026-06-20-clone.md` — rack / subtree / bulk clone.
- `2026-06-20-drawio-export.md` — rack elevations → draw.io.
- `2026-06-20-release-diff.md` — slot-level release comparison + per-ref valuation.
- `2026-06-26-device-detail-and-candidate-fields.md` — NetBox device detail endpoint + candidate
  부가정보 field management; original(read-only) vs our-overlay(editable) split.

> Earlier UI/IA-iteration ADRs (screen consolidation, overview-flow, layout-view, etc.) were
> retired once superseded by the final IA; they remain in git history if needed.
