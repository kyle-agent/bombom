# Context Log

Dated events with a TTL. Appended by `/session-checkpoint`. Items expire per their TTL;
`[ref:N≥3]` items get promoted to `MEMORY.md` by `/session-start`.

TTL legend: `ttl:permanent` (decisions, architecture) · `ttl:90d` (completions, plans,
external events) · `ttl:30d` (temporary states, short-lived issues).

---

- [2026-06-18] Agent harness bootstrapped from claude-code-skills (13 skills, 4 agents,
  rules, hooks, memory scaffold). `ttl:permanent`
