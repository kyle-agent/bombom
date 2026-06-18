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
