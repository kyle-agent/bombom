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
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from ..bom import PriceBook
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


def _pricebook_at_ref(ws, root: Path, ref: str) -> "PriceBook":
    """The pricebook as it stood at a ref. WORKING uses the live pricebook; a tag reads its
    pricing/*.yaml out of git into a temp dir and loads it. Empty pricebook if pricing is absent."""
    if ref == WORKING:
        return ws.pricebook
    res = _git("ls-tree", "-r", "--name-only", ref, "--", "pricing", cwd=root)
    if res.returncode != 0:
        return PriceBook()
    files = [ln.strip() for ln in res.stdout.splitlines() if ln.strip().endswith((".yaml", ".yml"))]
    with tempfile.TemporaryDirectory() as td:
        pdir = Path(td) / "pricing"
        pdir.mkdir()
        for f in files:
            blob = _git("show", f"{ref}:{f}", cwd=root)
            if blob.returncode == 0:
                (pdir / Path(f).name).write_text(blob.stdout)
        return PriceBook.load(pdir)


def compare_releases(ws, root: Path, base: str, head: str, *, subpath: str = "offerings",
                     valuation_date: Optional[date] = None, priced_at_ref: bool = False) -> dict:
    """Slot-level diff of two refs. By default both sides are priced with the CURRENT pricebook
    (isolates the design change). With ``priced_at_ref`` each side is valued at its own ref's
    pricing, so the CAPEX delta also reflects price drift."""
    as_of = valuation_date or date.today()
    base_book = _pricebook_at_ref(ws, root, base) if priced_at_ref else ws.pricebook
    head_book = _pricebook_at_ref(ws, root, head) if priced_at_ref else ws.pricebook

    def capex(book, u: dict) -> int:
        e = book.lookup(as_of, slug=u["device"])
        return (e.unit_cost if e else 0) * u["qty"]

    base_map = _load_ref(root, base, subpath)
    head_map = _load_ref(root, head, subpath)

    added, removed, changed = [], [], []
    for key, h in head_map.items():
        b = base_map.get(key)
        if b is None:
            added.append({**_loc(h), "device": h["device"], "qty": h["qty"],
                          "release": h["release"], "capex": capex(head_book, h)})
        elif b["device"] != h["device"] or b["qty"] != h["qty"]:
            changed.append({**_loc(h),
                            "from_device": b["device"], "from_qty": b["qty"],
                            "to_device": h["device"], "to_qty": h["qty"],
                            "from_capex": capex(base_book, b), "to_capex": capex(head_book, h),
                            "delta": capex(head_book, h) - capex(base_book, b)})
    for key, b in base_map.items():
        if key not in head_map:
            removed.append({**_loc(b), "device": b["device"], "qty": b["qty"],
                            "release": b["release"], "capex": capex(base_book, b)})

    def _sortkey(r):
        return (r.get("region", ""), r.get("zone", ""), r.get("rack", ""), r.get("position", 0))
    for rows in (added, removed, changed):
        rows.sort(key=_sortkey)

    base_capex = sum(capex(base_book, u) for u in base_map.values())
    head_capex = sum(capex(head_book, u) for u in head_map.values())
    return {
        "base": base, "head": head, "subpath": subpath, "valuation_date": as_of.isoformat(),
        "priced_at_ref": priced_at_ref,
        "added": added, "removed": removed, "changed": changed,
        "base_capex": base_capex, "head_capex": head_capex, "capex_delta": head_capex - base_capex,
        "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
    }
