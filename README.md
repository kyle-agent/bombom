# bombom

> Status: bootstrapped for agentic development. Stack not yet decided — run
> `/project-init` to lock it in.

This repo is set up for AI-assisted development with [Claude Code](https://claude.com/claude-code),
using the [claude-code-skills](https://github.com/AlexZio00/claude-code-skills) lifecycle
pipeline. Agents have a full harness: lifecycle skills, review agents, tiered rules, a
session-start hook, and a memory layer.

## What's installed

| Path | What it is |
|------|------------|
| `.claude/skills/` | 13 lifecycle skills (slash commands) — `/brief`, `/freeze`, `/adr`, `/pre-push`, `/session-start`, `/session-checkpoint`, `/retro`, `/project-init`, `/harness-init`, `/team-init`, `/project-check`, `/collab-audit`, `/token-audit` |
| `.claude/agents/` | `orchestrator`, `code-reviewer`, `security-reviewer`, `verification` |
| `.claude/rules/` | `ai-constitution.md` (Tier 0, immutable), `agents.md`, `development-workflow.md`, `output-style.md` |
| `.claude/hooks/` | `session-start.sh` — surfaces the handoff + lessons at session start |
| `.claude/settings.json` | wires the SessionStart hook |
| `memory/` | `MEMORY.md`, `session-handoff-LATEST.md`, `context-log.md`, `tasks/lessons.md` |
| `docs/decisions/` | Architecture Decision Records (`/adr`) |
| `CLAUDE.md` | project context + Hard Rules, loaded every session |

## Daily loop

```
/session-start       load handoff, flag lessons, ready signal
/brief               lock scope before a feature (Scope OUT mandatory)
/freeze              declare the editable zone before implementing
  …implement…
/adr                 record non-obvious design decisions
/pre-push            secrets + tests + lint + AI review gate
/session-checkpoint  save state before /compact
/retro               after a milestone — extract lessons
```

## Next step

Run `/project-init` to decide the stack and fill in the `[TODO]` sections of `CLAUDE.md`,
`.gitignore`, and `.env.example`.
