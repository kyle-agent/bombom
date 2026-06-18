#!/usr/bin/env bash
# SessionStart hook — surfaces forward-looking context at the top of each session.
# Output on stdout is injected into the session as additional context.
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

emit() { [ -f "$1" ] && { echo "=== $2 ==="; cat "$1"; echo; }; }

echo "## bombom — session context (auto-loaded)"
echo
emit "$ROOT/memory/session-handoff-LATEST.md" "Handoff (what to do next)"
emit "$ROOT/memory/tasks/lessons.md"           "Lessons (behavior corrections)"
echo "Run /session-start for the full ready signal, /session-checkpoint before /compact."
