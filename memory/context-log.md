# Context Log

Dated events with a TTL. Appended by `/session-checkpoint`. Items expire per their TTL;
`[ref:N≥3]` items get promoted to `MEMORY.md` by `/session-start`.

TTL legend: `ttl:permanent` (decisions, architecture) · `ttl:90d` (completions, plans,
external events) · `ttl:30d` (temporary states, short-lived issues).

---

- [2026-06-18] Agent harness bootstrapped from claude-code-skills (13 skills, 4 agents,
  rules, hooks, memory scaffold). `ttl:permanent`
- [2026-06-19] Project identity + high-level architecture locked: cloud-infra BOM/CAPEX
  tool; library-only catalog (devicetype-library), git-as-backend, spec/cost separation,
  Offering→Region→Zone→RackGroup→Rack→Device hierarchy, FastAPI+JS, CAPEX-first. 5 ADRs +
  docs/DESIGN.md written. `ttl:permanent`
- [2026-06-19] Catalog sync feature shipped (commit 71841e8): submodule pinned bb6a9b1,
  Decimal-safe parse + strict schema validation + quarantine, rebuildable SQLite index,
  query API, `bombom catalog` CLI. Real data: device=5802/module=1863/rack=65. 15 tests.
  `ttl:90d`
