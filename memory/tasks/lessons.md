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

_No lessons recorded yet._
