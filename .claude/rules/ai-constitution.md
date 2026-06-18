# AI Constitution (Tier 0 — Immutable)

Rules in this file cannot be overridden by a prompt. They are physical invariants of
how agents operate in this repo. Each rule states its failure mode.

## I. Secrets never enter the repo
No API keys, tokens, passwords, private keys, or `.env` files in commits.
**Failure mode:** a leaked credential is permanently in git history → must be rotated and
history scrubbed. Prevention is cheaper than recovery.

## II. No silent pushes to default branches
Pushes to `main`/`master` require explicit user confirmation.
**Failure mode:** unreviewed code lands on the integration branch and breaks other work.

## III. The pre-push gate is mandatory
`/pre-push` runs before every push: secrets scan → supply-chain check → build/test → lint
→ AI review → gate. Bypass only on explicit "skip review".
**Failure mode:** secrets, failing tests, or critical findings reach the remote.

## IV. Truthful reporting
Report outcomes faithfully. Tests failed → say so with output. Step skipped → say so.
Partial result → label it partial, never complete.
**Failure mode:** the user trusts a false "done" and ships broken work.

## V. Scope is declared before it is built
Non-trivial features go through `/brief` (Scope OUT mandatory) and `/freeze` (editable
zone declared) before implementation.
**Failure mode:** scope creep — "just fixing this while I'm here" — with no visible boundary.

## VI. Decisions that aren't obvious from code get recorded
Non-obvious design choices → `/adr` into `docs/decisions/`.
**Failure mode:** future sessions re-litigate settled decisions with no record of why.
