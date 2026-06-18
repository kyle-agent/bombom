# Agent Routing

How work is routed across agents in this repo. The orchestrator owns the plan; specialized
agents own their narrow checks. Created by the `/team-init` pattern (Solo tier — 3 agents).

## Routing table

| Trigger | Agent | Model | Role |
|---------|-------|-------|------|
| Multi-step task, plan tracking, drift risk | `orchestrator` | opus | Owns the plan, detects drift, enforces gates, corrects twice before escalating |
| Any code change before push | `code-reviewer` | sonnet | Correctness, reuse, simplicity; domain-aware review |
| Auth / API / infra / dangerous patterns / new deps | `security-reviewer` | opus | OWASP Top 10, secrets, injection, unsafe sinks |
| Task claims to be complete | `verification` | sonnet | Re-checks the work against the spec; "do not trust the report" |

## Principles

- **Do not trust the report.** Reviewers read the actual diff/code, not the implementer's
  summary of it.
- **Weakest link wins.** If `security-reviewer` returns Critical and another agent returns
  PASS on the same file, Critical wins — do not push.
- **Correct, don't escalate first.** On implementation drift, the orchestrator corrects up
  to twice before escalating to the user.
- **Create only what's missing.** New agents are added; existing agent files are never
  silently overwritten.

## Scaling up

This is the Solo (3-agent) tier. To add `brainstorming`, `writing-plans`,
`build-error-resolver` (Standard) or `subagent-dev`, `systematic-debugging`,
`database-reviewer` (Full), run `/team-init` again — it merges into this table.
