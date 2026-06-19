"""Release ↔ git (lightweight).

A release is a text tag on placements (e.g. R26.07). To bind a release to git's own version
system, we list/create git tags. Full ref-to-ref BOM diff is out of scope for now — release
delta is computed from placement tags by the BOM engine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def list_tags(cwd: Path | None = None) -> list[str]:
    res = _git("tag", "--list", "--sort=-creatordate", cwd=cwd)
    if res.returncode != 0:
        return []
    return [t for t in res.stdout.splitlines() if t.strip()]


def tag_release(name: str, *, message: str | None = None, cwd: Path | None = None) -> str:
    """Create an annotated git tag marking the current state as a release."""
    args = ["tag", "-a", name, "-m", message or f"bombom release {name}"]
    res = _git(*args, cwd=cwd)
    if res.returncode != 0:
        raise RuntimeError(f"git tag failed: {res.stderr.strip()}")
    return name
