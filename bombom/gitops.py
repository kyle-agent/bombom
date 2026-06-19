"""Commit design edits to git (git is the source of truth; edits land as commits).

argv-based subprocess (no shell). Commits to the current branch — branch/PR workflows are a
later concern.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def add_commit(paths: list[Path], message: str, *, cwd: Path) -> str | None:
    """Stage `paths` and commit. Returns the new commit SHA, or None if nothing changed."""
    if not message or message.startswith("-"):
        raise ValueError("commit message must be non-empty and not start with '-'")
    cwd = Path(cwd)
    rels = [str(Path(p)) for p in paths]
    add = _git("add", "--", *rels, cwd=cwd)
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()}")

    # Nothing staged (no real change) → no commit.
    if _git("diff", "--cached", "--quiet", cwd=cwd).returncode == 0:
        return None

    commit = _git("commit", "-m", message, "--", *rels, cwd=cwd)
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")
    head = _git("rev-parse", "HEAD", cwd=cwd)
    return head.stdout.strip() or None
