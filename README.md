# bombom

**bombom** is a tool for cloud-infrastructure designers to select hardware, lay it out in racks
under an **Offering → Region → Zone → Rack-Type → Rack → Device** hierarchy, and derive the
capital investment (**BOM / CAPEX**). Hardware specs are reused read-only from the NetBox
community `devicetype-library`; bombom adds the price overlay, the org placement model, and a
NetBox-style rack elevation view.

- **Live demo (read-only):** https://kyle-agent.github.io/bombom/
- **Hand-off / getting started:** [`docs/HANDOFF.md`](docs/HANDOFF.md) — quick start, routes, API, code map
- **Design & rationale:** [`docs/DESIGN.md`](docs/DESIGN.md) · ADRs in [`docs/decisions/`](docs/decisions/)

Stack: Python + FastAPI backend (`bombom/`), dependency-free vanilla-HTML pages (`web/`),
Git/YAML as the source of truth, a rebuildable SQLite catalog index. See **Running the app** below.

---

This repo is also set up for AI-assisted development with [Claude Code](https://claude.com/claude-code)
(the [claude-code-skills](https://github.com/AlexZio00/claude-code-skills) lifecycle pipeline):
lifecycle skills, review agents, tiered rules, a session-start hook, and a memory layer. If your
team doesn't use Claude Code, the `.claude/`, `memory/`, and `BRIEF.md` paths can be ignored or removed.

## Dev harness (Claude Code) — what's installed

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

## Running the app

```
pip install -e ".[dev]"
bombom catalog sync && bombom catalog reindex   # once: init submodule + build index
bombom serve            # http://127.0.0.1:8000/  (read-only view)  ·  /edit  (editor)
bombom serve --root PATH # serve a specific workspace dir (default: cwd)
bombom export out.html  # self-contained static viewer (no server)
```

Editing in `/edit` writes the rack YAML and **commits to git** (`PUT /api/rack`).

## Try it locally (demo workspace)

One command seeds a realistic workspace so every page has data to click through:

```
make demo               # seed demo-workspace/ + start the server
# or, by hand:
python scripts/demo.py             # → ./demo-workspace (multi-zone, 2 release tags)
bombom serve --root demo-workspace # → http://127.0.0.1:8000/
```

The seed deliberately includes validation issues (U overlap, missing required serial,
unpriced placement, candidate gaps) so `/health` isn't empty, and tags two releases
(R25.01, R26.07) plus one uncommitted edit so `/diff` shows real deltas. Pages to visit:
`/manage` (+ `⬇ draw.io` export per AZ/Rack-Type) · `/candidates` · `/search` · `/health` ·
`/edit` · `/placed` · `/dashboard` · `/diff`. The hardware catalog stays shared (repo's
`.index/catalog.db`); only org/pricing data lives in the demo dir, which is gitignored.

## GitHub Pages (read-only viewer)

`.github/workflows/pages.yml` builds the static viewer (`bombom export`) and publishes it
to GitHub Pages on push. **One-time setup:** repo Settings → Pages → Source: *GitHub
Actions*. Pages is **view-only** (editing stays in `bombom serve` / PRs). Note Pages is
public — fine here since the data is public-OK; for sensitive cost data use private hosting.
