<!-- #always -->
# MEMORY — bombom

Permanent facts about this project. Updated by `/session-checkpoint` (on stale
detection) and `/retro`. Keep this small — it loads every session.

## Project

- **Name:** bombom
- **Purpose:** Cloud-infra design + investment (BOM/CAPEX) tool. Designers pick HW, lay it
  out in racks, and derive capital cost. See `docs/DESIGN.md`.
- **Status:** High-level design locked (2026-06-19, 5 ADRs in `docs/decisions/`). No app
  code yet — next is `/brief` on the first feature.
- **Harness source:** [claude-code-skills](https://github.com/AlexZio00/claude-code-skills) lifecycle pipeline (13 skills in `.claude/skills/`).

## Architecture (locked decisions — see docs/decisions/)

- **Catalog:** reuse NetBox community `devicetype-library` (YAML) as read-only spec source;
  do NOT run NetBox. (ADR 2026-06-19-library-only-catalog)
- **Backend = git:** git is source of truth; SQLite index is a rebuildable cache; no app DB.
  (ADR git-as-backend)
- **Spec vs cost:** community spec and bombom price book kept separate, joined by
  `manufacturer+slug | part_number`. Prices never enter device YAML. (ADR spec-cost-separation)
- **Hierarchy:** Offering→Region→Zone→RackGroup→Rack→Device; directory tree mirrors it.
  (ADR org-hierarchy) — NetBox map: Offering=new, Region=Region, Zone=Site, RackGroup=Location.
- **Stack:** FastAPI backend (server-side rack elevation SVG, BOM engine) + JS SPA; form-based
  editing, commit-on-save; CAPEX-first. (ADR app-stack)

## Conventions

- Branch naming: `feature/<short-name>`, `fix/<short-name>`.
- All pushes go through `/pre-push`. Pushes to `main`/`master` need explicit confirmation.

<!-- #on-demand -->
## Reference

- Rules: `.claude/rules/` (ai-constitution, agents, development-workflow, output-style).
- Agents: `.claude/agents/` (orchestrator, code-reviewer, security-reviewer, verification).
- Decisions: `docs/decisions/`.
