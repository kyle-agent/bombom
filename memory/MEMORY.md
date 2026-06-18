<!-- #always -->
# MEMORY — bombom

Permanent facts about this project. Updated by `/session-checkpoint` (on stale
detection) and `/retro`. Keep this small — it loads every session.

## Project

- **Name:** bombom
- **Status:** Bootstrapped harness; stack not yet decided. Run `/project-init` to lock
  stack, data layer, and deployment target.
- **Harness source:** [claude-code-skills](https://github.com/AlexZio00/claude-code-skills) lifecycle pipeline (13 skills in `.claude/skills/`).

## Architecture

`[TODO: record permanent architecture facts here as they are decided.]`

## Conventions

- Branch naming: `feature/<short-name>`, `fix/<short-name>`.
- All pushes go through `/pre-push`. Pushes to `main`/`master` need explicit confirmation.

<!-- #on-demand -->
## Reference

- Rules: `.claude/rules/` (ai-constitution, agents, development-workflow, output-style).
- Agents: `.claude/agents/` (orchestrator, code-reviewer, security-reviewer, verification).
- Decisions: `docs/decisions/`.
