"""Ref-to-ref design diff — what changed between two confirmed design sets (releases).

A *release* here means a confirmed collection of designs, sealed as an annotated git tag
(tag name = confirmation id). To show what a confirmation added / removed / replaced, we need
the two *full* design states, which only exist at their git refs — so this reads rack YAML at
each ref (or the working tree, the special ref ``WORKING``) and diffs by physical slot.

Identity of a unit = (rack file, bottom-U position): the same slot holding a different device
is a *replacement* (changed); a slot only on one side is added/removed. Prices come from the
current pricebook for both sides, so the CAPEX delta isolates the *design* change from price
drift (use the report/dashboard for absolute, as-of valuation).
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from ..design import RackDesign, load_racks, parse_hierarchy

WORKING = "WORKING"     # pseudo-ref: the current working tree (uncommitted draft)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _rack_files_at(root: Path, ref: str, subpath: str) -> list[str]:
    # A valid ref over an empty subpath returns rc 0 + no output; a bad ref returns non-zero.
    # Distinguish them so an unknown release surfaces as an error, not a giant spurious diff.
    res = _git("ls-tree", "-r", "--name-only", ref, "--", subpath, cwd=root)
    if res.returncode != 0:
        raise ValueError(f"알 수 없는 릴리즈/ref: {ref}")
    return [ln.strip() for ln in res.stdout.splitlines()
            if "/racks/" in ln and ln.strip().endswith((".yaml", ".yml"))]


def _collect(acc: dict, rel: str, hier: dict, design: RackDesign) -> None:
    rack_id = Path(rel).stem
    for pl in design.placements:
        acc[(rel, pl.position)] = {
            "rack": rack_id, "position": pl.position, "device": pl.device, "qty": pl.qty,
            "release": pl.release or "",
            "region": hier.get("region", ""), "zone": hier.get("zone", ""),
            "rack_type": hier.get("rack_type", ""),
        }


def _load_ref(root: Path, ref: str, subpath: str) -> dict:
    """{(rack_rel, position): unit} for a git ref, or the working tree when ref == WORKING."""
    placements: dict = {}
    root = Path(root)
    if ref == WORKING:
        for lr in load_racks(root / subpath).racks:
            rel = Path(lr.path).resolve().relative_to(root.resolve()).as_posix()
            _collect(placements, rel, lr.hierarchy, lr.design)
        return placements
    for rel in _rack_files_at(root, ref, subpath):
        res = _git("show", f"{ref}:{rel}", cwd=root)
        if res.returncode != 0:
            continue
        try:
            design = RackDesign.model_validate(yaml.safe_load(res.stdout) or {})
        except Exception:  # noqa: BLE001 — a rack that won't parse at a ref is skipped, not fatal
            continue
        _collect(placements, rel, parse_hierarchy(Path(rel)), design)
    return placements


def _loc(u: dict) -> dict:
    return {k: u[k] for k in ("region", "zone", "rack_type", "rack", "position")}


def compare_releases(ws, root: Path, base: str, head: str, *, subpath: str = "offerings",
                     valuation_date: Optional[date] = None) -> dict:
    as_of = valuation_date or date.today()

    def price(slug: str) -> Optional[int]:
        e = ws.pricebook.lookup(as_of, slug=slug)
        return e.unit_cost if e else None

    def line_capex(u: dict) -> int:
        return (price(u["device"]) or 0) * u["qty"]

    base_map = _load_ref(root, base, subpath)
    head_map = _load_ref(root, head, subpath)

    added, removed, changed = [], [], []
    for key, h in head_map.items():
        b = base_map.get(key)
        if b is None:
            added.append({**_loc(h), "device": h["device"], "qty": h["qty"],
                          "release": h["release"], "capex": line_capex(h)})
        elif b["device"] != h["device"] or b["qty"] != h["qty"]:
            changed.append({**_loc(h),
                            "from_device": b["device"], "from_qty": b["qty"],
                            "to_device": h["device"], "to_qty": h["qty"],
                            "from_capex": line_capex(b), "to_capex": line_capex(h),
                            "delta": line_capex(h) - line_capex(b)})
    for key, b in base_map.items():
        if key not in head_map:
            removed.append({**_loc(b), "device": b["device"], "qty": b["qty"],
                            "release": b["release"], "capex": line_capex(b)})

    def _sortkey(r):
        return (r.get("region", ""), r.get("zone", ""), r.get("rack", ""), r.get("position", 0))
    for rows in (added, removed, changed):
        rows.sort(key=_sortkey)

    base_capex = sum(line_capex(u) for u in base_map.values())
    head_capex = sum(line_capex(u) for u in head_map.values())
    return {
        "base": base, "head": head, "subpath": subpath, "valuation_date": as_of.isoformat(),
        "added": added, "removed": removed, "changed": changed,
        "base_capex": base_capex, "head_capex": head_capex, "capex_delta": head_capex - base_capex,
        "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
    }
