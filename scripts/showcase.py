#!/usr/bin/env python3
"""Seed a demo workspace whose org structure is: 4 offerings (Enterprise, Samsung, PPP,
Sovereign), each with regions kr-east1 & kr-west1, and only Samsung/kr-west1 holding zones
(zone1, zone2) with densely-filled racks + two tagged releases (for /diff). Empty offerings/
regions exist (marker YAMLs) so the structure shows on the main dashboard. All slugs exist in
the vendored devicetype-library.

    python scripts/showcase.py demo-showcase     # then: bombom serve --root demo-showcase
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

SERVER_2U = "dell-poweredge-r760"
SERVER_1U = "dell-poweredge-r660"
SERVER_1U_B = "dell-poweredge-r650"
GPU_3U = "dell-poweredge-r940"
SW_1U = "arista-dcs-7050cx3-32s"
SW_1U_B = "arista-ccs-720dp-24s-2f"
STOR_2U = "dell-powervault-me4024"
STOR_2U_B = "dell-md1400"
U = {SERVER_2U: 2, SERVER_1U: 1, SERVER_1U_B: 1, GPU_3U: 3,
     SW_1U: 1, SW_1U_B: 1, STOR_2U: 2, STOR_2U_B: 2}

OFFERINGS = ["Enterprise", "Samsung", "PPP", "Sovereign"]
REGIONS = ["kr-east1", "kr-west1"]
RACK = "offerings/{off}/regions/{reg}/zones/{zone}/rack-types/{rt}/racks/{rack}.yaml"


def _pl(device, position, release, **meta):
    d = {"device": device, "position": position, "release": release}
    if meta:
        d["meta"] = meta
    return d


def _yaml(rack_slug, placements):
    out = [f"rack_model: {{ slug: {rack_slug} }}", "placements:"]
    for p in placements:
        parts = [f"device: {p['device']}", f"position: {p['position']}", f"release: {p['release']}"]
        if p.get("meta"):
            parts.append("meta: { " + ", ".join(f"{k}: {v}" for k, v in p["meta"].items()) + " }")
        out.append("  - { " + ", ".join(parts) + " }")
    return "\n".join(out) + "\n"


def _stack(devs, *, start, release, prefix, gaps=None, top_u=42):
    gaps = gaps or set()
    pos, pls, n = start, [], 0
    for dev in devs:
        h = U[dev]
        while pos in gaps:
            pos += 1
        if pos + h - 1 > top_u:
            break
        n += 1
        meta = {}
        if dev in (SERVER_2U, SERVER_1U, SERVER_1U_B, GPU_3U):
            meta = {"serial": f"{prefix}-{n:02d}", "asset_class": "compute", "owner": "infra"}
        pls.append(_pl(dev, pos, release, **meta))
        pos += h
    return pls


def _compute_rack(prefix, release):
    pls = _stack([SERVER_2U] * 12 + [SERVER_1U] * 6, start=1, release=release, prefix=prefix, top_u=38)
    return pls + [_pl(SW_1U, 41, release), _pl(SW_1U_B, 42, release)]


def _storage_rack(prefix, release):
    pls = _stack([STOR_2U] * 9 + [STOR_2U_B] * 6, start=1, release=release, prefix=prefix, top_u=34)
    return pls + [_pl(SW_1U, 42, release)]


def _gpu_rack(prefix, release):
    pls = _stack([GPU_3U] * 11, start=1, release=release, prefix=prefix, top_u=36)
    return pls + [_pl(SW_1U, 41, release), _pl(SW_1U_B, 42, release)]


def _network_rack(release):
    return _stack([SW_1U, SW_1U_B] * 8, start=4, release=release, prefix="NET",
                  gaps={g for g in range(4, 43) if g % 3 == 0}, top_u=42)


CATS = (
    "categories:\n"
    f"  {SERVER_2U}: server\n  {SERVER_1U}: server\n  {SERVER_1U_B}: server\n  {GPU_3U}: server\n"
    f"  {SW_1U}: network\n  {SW_1U_B}: network\n  {STOR_2U}: storage\n  {STOR_2U_B}: storage\n"
)
PRICES = (
    "entries:\n"
    f"  - {{ slug: {SERVER_2U}, unit_cost: 19500000, valid_from: 2025-01-01, source: 시안 }}\n"
    f"  - {{ slug: {SERVER_1U}, unit_cost: 15000000, source: 시안 }}\n"
    f"  - {{ slug: {SERVER_1U_B}, unit_cost: 13500000, source: 시안 }}\n"
    f"  - {{ slug: {GPU_3U}, unit_cost: 78000000, source: 시안 }}\n"
    f"  - {{ slug: {SW_1U}, unit_cost: 9800000, source: 시안 }}\n"
    f"  - {{ slug: {SW_1U_B}, unit_cost: 7200000, source: 시안 }}\n"
    f"  - {{ slug: {STOR_2U}, unit_cost: 24000000, source: 시안 }}\n"
    f"  - {{ slug: {STOR_2U_B}, unit_cost: 16500000, source: 시안 }}\n"
)
FIELDS = (
    "fields:\n"
    "  - { key: asset_class, label: 자산분류, type: enum, options: [compute, gpu, storage, network],\n"
    "      required: true, applies_to: device_type, scope: \"category:server\" }\n"
    "  - { key: serial, label: 시리얼, type: string, required: true,\n"
    "      applies_to: placement, scope: \"category:server\" }\n"
    "  - { key: owner, label: 담당팀, type: string, required: false, applies_to: placement, scope: all }\n"
    "  - { key: lead_time_weeks, label: 리드타임(주), type: number, required: true,\n"
    "      applies_to: candidate, scope: all }\n"
)
CANDIDATES = (
    "candidates:\n"
    f"  - {{ slug: {SERVER_2U}, added_at: '2026-06-20', meta: {{ lead_time_weeks: 8 }} }}\n"
    f"  - {{ slug: {SERVER_1U}, added_at: '2026-06-20', meta: {{ lead_time_weeks: 6 }} }}\n"
    f"  - {{ slug: {GPU_3U}, added_at: '2026-06-20', meta: {{ lead_time_weeks: 16 }} }}\n"
    f"  - {{ slug: {STOR_2U}, added_at: '2026-06-20', meta: {{ lead_time_weeks: 10 }} }}\n"
    f"  - {{ slug: {SW_1U}, added_at: '2026-06-20', meta: {{ lead_time_weeks: 5 }} }}\n"
    f"  - {{ slug: {SERVER_1U_B}, added_at: '2026-06-20' }}  # 필수 lead_time 누락 → /health 갭\n"
)


def _git(root, *args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr}")


def _write(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def _zrack(off, reg, zone, rt, rack):
    return RACK.format(off=off, reg=reg, zone=zone, rt=rt, rack=rack)


def seed(target):
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    R0, R1 = "R25.01", "R26.07"

    # marker YAMLs so empty offerings/regions show in the hierarchy / 메인 대시보드
    base = {
        "categories/overlay.yaml": CATS, "pricing/catalog.yaml": PRICES,
        "meta/fields.yaml": FIELDS, "candidates/pool.yaml": CANDIDATES,
    }
    for off in OFFERINGS:
        base[f"offerings/{off}/offering.yaml"] = f"name: {off}\n"
        for reg in REGIONS:
            base[f"offerings/{off}/regions/{reg}/region.yaml"] = f"name: {reg}\n"

    # R25.01 baseline — Samsung/kr-west1/zone1
    z1 = ("Samsung", "kr-west1", "zone1")
    for i in range(1, 4):
        base[_zrack(*z1, "compute", f"R{i:02d}")] = _yaml("vertiv-vr3300", _compute_rack(f"S1C{i}", R0))
    base[_zrack(*z1, "storage", "S01")] = _yaml("vertiv-vr3300", _storage_rack("S1S1", R0))
    base[_zrack(*z1, "network", "N01")] = _yaml("vertiv-vr3300", _network_rack(R0))

    _write(target, base)
    _git(target, "init", "-q")
    _git(target, "config", "user.email", "demo@bombom.local")
    _git(target, "config", "user.name", "bombom demo")
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", f"{R0} baseline")
    _git(target, "tag", "-a", R0, "-m", f"release {R0}")

    # R26.07 expansion — Samsung/kr-west1/zone2
    z2 = ("Samsung", "kr-west1", "zone2")
    exp = {}
    for i in range(10, 13):
        exp[_zrack(*z2, "compute", f"R{i}")] = _yaml("vertiv-vr3300", _compute_rack(f"S2C{i}", R1))
    exp[_zrack(*z2, "gpu", "G01")] = _yaml("vertiv-vr3300", _gpu_rack("S2G1", R1))
    _write(target, exp)
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", f"{R1} expansion")
    _git(target, "tag", "-a", R1, "-m", f"release {R1}")

    confs = {
        "confirmations/rel-2025-01.yaml": ("id: rel-2025-01\nkind: release\nstatus: confirmed\n"
            "requester: designer\napprover: lead\n"
            f"created_at: '2025-01-05T09:00:00'\nconfirmed_at: '2025-01-06T10:00:00'\ntag: {R0}\n"),
        "confirmations/rel-2026-07.yaml": ("id: rel-2026-07\nkind: release\nstatus: confirmed\n"
            "requester: designer\napprover: lead\n"
            f"created_at: '2026-07-01T09:00:00'\nconfirmed_at: '2026-07-02T10:00:00'\ntag: {R1}\n"),
    }
    _write(target, confs)
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "seal R25.01 + R26.07 confirmations")
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="?", default="demo-showcase")
    out = seed(Path(ap.parse_args(argv).target))
    print(f"seeded showcase (4 offerings; racks under Samsung/kr-west1/zone1+zone2) at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
