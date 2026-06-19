# 2026-06-19 — Git as the backend (source of truth + rebuildable index)

## Context
bombom's data is document-shaped (YAML), read-heavy, low write-frequency, and has strong
versioning/audit/scenario requirements: point-in-time pricing, design versions,
investment provenance, and "what-if vendor swap" comparisons.

## Decision
Use **git as the canonical datastore**. All catalog mirror, pricing, and design data live
as plain-text YAML in the repo. Queries run against a **rebuildable** SQLite/in-memory
index that is never authoritative — `checkout` + reindex always reconstructs it.

## Alternatives considered
- **Relational DB (Postgres).** Would require building temporal tables to replicate what
  git history/tags/branches give for free; heavier ops; overkill for the write volume.
- **Dolt ("git for data" SQL DB).** Gives SQL + versioning, but adds a DB-engine
  dependency for data that is natively document-shaped. Kept as a future option if ad-hoc
  SQL querying becomes a primary need.

## Consequences
- Free: history (audit), tags (design versions), branches (cost scenarios), ref-diff
  (investment delta), PR review of price/design changes.
- Not free, must add: query index (rebuildable cache), referential-integrity validation
  (schema + cross-ref check in pre-commit/CI), and git access via a lib (pygit2/GitPython).
- No ACID/high-concurrency writes — acceptable; writes go through commits/PRs.

## Override conditions
Revisit if write concurrency or ad-hoc analytical querying outgrows file+index — migrate
the index to a real DB (git stays the source of truth) or adopt Dolt.
