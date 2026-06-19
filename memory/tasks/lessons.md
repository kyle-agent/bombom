# Lessons — AI Behavior Correction Log

Repeated AI mistakes recorded as correction rules (Boris Cherny pattern). Written by
`/retro` and `/session-checkpoint`; surfaced at session start by `/session-start`.
This is behavior correction — technical facts go in `MEMORY.md`.

Each lesson:

```
### [YYYY-MM-DD] {lesson title}
> conf: 0.5 · seen: YYYY-MM-DD · obs: 1

When X happens, do Y instead of Z.
Source: /retro — {milestone name}
```

`conf` rises with re-observation (3/6/9 → max 0.9) and drops 0.1 on a corrected
violation (min 0.3). `conf < 0.4 AND seen > 90d ago` → archive.

---

### [2026-06-19] Mirror upstream validation semantics exactly when reusing a community schema
> conf: 0.5 · seen: 2026-06-19 · obs: 1

When validating community data against its own schema (e.g. JSON Schema `multipleOf`), load
values the same way upstream does — devicetype-library parses floats as `decimal.Decimal`, so
plain-float loading wrongly rejected valid hardware on a binary-float artifact. Check the
upstream loader/test harness before assuming a validation failure is a real data error.
Source: catalog sync

### [2026-06-19] Derive index/dedup keys from the real dataset, not from assumptions
> conf: 0.5 · seen: 2026-06-19 · obs: 1

`part_number` looked unique but wasn't — distinct modules shared one, so an index keyed on it
silently collapsed 24 entries. Before keying a dedup/PK on a field, scan the full corpus for
collisions and add a regression test for the colliding case.
Source: catalog sync
