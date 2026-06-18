# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

## Priority 1

Decide the project stack and fill in the `[TODO]` sections of `CLAUDE.md`. Run
`/project-init` (it interviews you and generates CLAUDE.md, ROADMAP, `.gitignore`, and
`.env.example` tailored to the chosen stack).

## Open decisions

- What is bombom? (purpose, audience)
- Stack / data layer / deployment target — all undecided.

## Blockers

None.

## Context notes

The agent harness is installed and ready: 13 skills in `.claude/skills/`, 4 agents in
`.claude/agents/`, rules in `.claude/rules/`, and lifecycle hooks in
`.claude/settings.json`. Start each session with `/session-start`.
