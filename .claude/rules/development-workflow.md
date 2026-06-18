# Development Workflow — Review Gate Pipeline

The path every change takes from idea to remote. Gates are sequential; a failed gate stops
the pipeline.

```
/session-start
      │
      ▼
  /brief ──── lock scope (Scope IN / Scope OUT / Exit Criteria)
      │
      ▼
  /freeze ─── declare editable files; everything else is read-only
      │
      ▼
  implement ─ orchestrator tracks plan, corrects drift
      │
      ▼
  /adr ────── record non-obvious design decisions (as they happen)
      │
      ▼
  /pre-push ─ GATE: secrets → supply chain → build/test → lint → AI review → verdict
      │            (Critical/High findings block; secrets block; main/master needs confirm)
      ▼
  git push (only when all gates pass)
      │
      ▼
  /session-checkpoint ── save handoff before /compact
      │
      ▼
  /retro (after a milestone) ── extract recurring lessons → memory/tasks/lessons.md
```

## Gate rules

- **Secrets gate:** any hardcoded credential in the staged diff blocks the push.
- **Test gate:** language-aware; runs only what changed. Failures block.
- **Lint gate:** direct linter first, AI quick-validator second.
- **Review gate:** Critical/High block. Medium → fix if < 5 min, else annotate
  `// TODO(security):`. Low → report only.
- **Branch gate:** pushes to `main`/`master` require explicit confirmation.

## When to skip a gate

Only when the user explicitly says "skip review" / "force push". The bypass is logged with
a warning, never silent.
