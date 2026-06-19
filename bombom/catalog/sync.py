"""Sync the vendored device-type library to its pinned commit and report what's there.

This updates the submodule to the commit pinned in this repo (the gitlink) — it does not
move the pin. Bumping the pin to pull in newer community hardware is a deliberate, manual
step (documented in docs/DESIGN.md): fetch + checkout the new SHA inside the submodule, then
commit the updated gitlink here.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .parse import _norm, iter_yaml
from .paths import CatalogPaths, repo_root

SUBMODULE_PATH = "vendor/devicetype-library"


@dataclass
class SyncResult:
    pinned_sha: str
    counts: dict[str, int]


def _git(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd or repo_root(), capture_output=True, text=True
    )


def sync(vendors: list[str] | None = None, init: bool = True) -> SyncResult:
    if init:
        result = _git("submodule", "update", "--init", "--", SUBMODULE_PATH)
        if result.returncode != 0:
            raise RuntimeError(f"submodule update failed: {result.stderr.strip()}")

    paths = CatalogPaths.default()
    rev = _git("rev-parse", "HEAD", cwd=repo_root() / SUBMODULE_PATH)
    if rev.returncode != 0 or not rev.stdout.strip():
        raise RuntimeError(
            f"could not read pinned commit of {SUBMODULE_PATH} "
            f"(is the submodule initialized?): {rev.stderr.strip()}"
        )
    sha = rev.stdout.strip()

    vendor_set = {_norm(v) for v in vendors} if vendors else None
    counts: dict[str, int] = {}
    for kind in ("device", "module", "rack"):
        base = paths.types_dir(kind)
        n = 0
        for path in iter_yaml(base):
            if vendor_set is not None:
                vendor_dir = path.relative_to(base).parts[0]
                if _norm(vendor_dir) not in vendor_set:
                    continue
            n += 1
        counts[kind] = n

    return SyncResult(pinned_sha=sha, counts=counts)
