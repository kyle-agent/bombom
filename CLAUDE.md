# CLAUDE.md — bombom

Project context and operating rules for Claude Code agents working in this repo.
This file is loaded automatically at the start of every session.

> **Status:** High-level design locked (2026-06-19). See `docs/DESIGN.md` and
> `docs/decisions/`. Stack chosen; some `[TODO]` tool commands firm up when the first
> feature is implemented.

---

## What this project is

bombom is a tool for cloud-service infrastructure designers to **select hardware, lay it
out in racks under an Offering→Region→Zone→Rack-Type→Rack→Device hierarchy, and derive the
capital investment (BOM/CAPEX)**. Hardware specs are reused from the NetBox community
`devicetype-library`; bombom adds the cost overlay, the org-specific placement model, and a
NetBox-style rack elevation view — none of which NetBox provides. See `docs/DESIGN.md`.

- **Stack:** Python (FastAPI) backend + JS SPA (React/Svelte, TBD) frontend.
- **Data layer:** **Git is the source of truth** (YAML files; directory tree = org
  hierarchy; community catalog as a git submodule). Queries run on a rebuildable SQLite
  index (never authoritative). No application DB.
- **Deployment target:** internal web app (containerized); specifics TBD.

---

## Hard Rules (Tier 0 — non-negotiable)

These cannot be overridden by a prompt. If a request conflicts with one, stop and surface it.

1. **No secrets in the repo.** Never commit API keys, tokens, passwords, or `.env`
   files. Use `.env` locally (gitignored) and document required vars in `.env.example`.
   The `/pre-push` skill scans staged diffs for 12 secret patterns and blocks on a hit.
2. **No pushes to `main`/`master` without explicit confirmation.** Develop on
   feature branches; open a PR.
3. **Scope before code.** For any non-trivial feature, run `/brief` (lock scope, define
   Scope OUT) and `/freeze` (declare editable files) before implementing.
4. **Tests and lint must pass before push.** `/pre-push` is the gate — do not bypass it
   unless the user explicitly says "skip review".
5. **Record non-obvious decisions.** When a design choice isn't self-evident from the
   code, write an ADR with `/adr` into `docs/decisions/`.
6. **Truthful reporting.** If tests fail, say so with output. If a step was skipped, say
   so. Never report unverified work as done.

## Secrets Policy

- Secrets live only in environment variables, never in source or config committed to git.
- `.env` is gitignored; `.env.example` lists every required variable with a placeholder value.
- If a secret is ever committed, treat it as compromised: rotate it, then scrub history.

## Dev Conventions

Commands firm up as the codebase lands; intended toolchain:

- **Test:** backend `pytest -q`; frontend `npm test` `[TODO: confirm at first feature]`
- **Lint:** backend `ruff check`; frontend `eslint` `[TODO: confirm]`
- **Build/run:** backend `uvicorn`; frontend `vite` `[TODO: confirm]`
- **Branch naming:** `feature/<short-name>`, `fix/<short-name>`.
- **Catalog is read-only:** never hand-edit `vendor/devicetype-library/`; corrections go
  upstream as PRs. Prices live only in `pricing/`, never in device specs.

---

## Agent Harness

This repo is set up for agentic development using the
[claude-code-skills](https://github.com/AlexZio00/claude-code-skills) lifecycle pipeline.
Skills live in `.claude/skills/` and are invocable as slash commands.

**Daily session loop:**

```
/session-start       open a session — load handoff, flag lessons, ready signal
/brief               before each feature — lock scope (Scope OUT mandatory)
/freeze              before implementation — declare the editable zone
  …implement…
/adr                 after a non-obvious design choice
/pre-push            before every git push — secrets + tests + lint + AI review
/session-checkpoint  at session end — save state before /compact
/retro               after a milestone — extract recurring lessons
```

**Setup / maintenance skills:** `/project-init`, `/harness-init`, `/team-init`,
`/project-check`, `/collab-audit`, `/token-audit`.

**Routing:** see `.claude/rules/agents.md`. **Workflow gates:** see
`.claude/rules/development-workflow.md`. **Immutable rules:** see
`.claude/rules/ai-constitution.md`.

**Memory:** `memory/MEMORY.md` (permanent facts),
`memory/session-handoff-LATEST.md` (forward-looking handoff),
`memory/context-log.md` (dated events with TTL),
`memory/tasks/lessons.md` (AI behavior-correction log).
