# 2026-06-19 — Device categorization: heuristic + manual override overlay

## Context
The 1차 selection screen must group model candidates by category (server / network /
storage / …). The community devicetype-library has **no category or role field** — NetBox
assigns role at the device *instance* level, defined by the operator, not on the type. So
categorization is bombom's responsibility.

## Decision
Classify device-types with **heuristic rules** (interface composition, u_height, module-bay
profiles, model-name cues) and allow **manual override**. Store the result in a **category
overlay** kept separate from the community spec — same separation principle as pricing
(ADR spec-cost-separation). The overlay is versioned in git.

## Alternatives considered
- **Manual mapping overlay only.** Accurate but ~5,800 device-types to maintain by hand —
  too much upkeep.
- **Designer tags on first use only.** Categories start empty, poor first-run experience.
  (Heuristic + override is the union: a good default that anyone can correct.)

## Consequences
- Classification is approximate; overrides accumulate in the overlay and win over heuristics.
- Heuristics need occasional tuning as new hardware classes appear; wrong guesses are cheap
  to correct and the correction persists.
- Keeps the community spec untouched (sync-safe).

## Override conditions
If upstream ever adds an authoritative category/role field, prefer it over the heuristic.
