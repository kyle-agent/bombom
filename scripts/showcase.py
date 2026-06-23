#!/usr/bin/env python3
"""Seed a *filled* showcase workspace — densely-packed racks across several zones, two tagged
releases (for /diff), prices, candidates and meta — so the static full-app demo has realistic
data on every screen. Distinct from scripts/demo.py (which is intentionally sparse and seeds
validation errors for /health). All slugs exist in the vendored devicetype-library.

    python scripts/showcase.py demo-showcase     # then: bombom serve --root demo-showcase
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

# slug → U-height (from the catalog), category for the overlay
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

OFF = "offerings/cloud-a/regions/{reg}/zones/{az}/rack-types/{rt}/racks/{rack}.yaml"


def _pl(device: str, position: int, release: str, **meta) -> dict:
    d = {"device": device, "position": position, "release": release}
    if meta:
        d["meta"] = meta
    return d


def _yaml(rack_slug: str, placements: list[dict]) -> str:
    out = [f"rack_model: {{ slug: {rack_slug} }}", "placements:"]
    for p in placements:
        parts = [f"device: {p['device']}", f"position: {p['position']}", f"release: {p['release']}"]
        if p.get("meta"):
            m = ", ".join(f"{k}: {v}" for k, v in p["meta"].items())
            parts.append(f"meta: {{ {m} }}")
        out.append("  - { " + ", ".join(parts) + " }")
    return "\n".join(out) + "\n"


def _stack(devs: list[str], *, start: int, release: str, prefix: str,
           gaps: set[int] | None = None, top_u: int = 42) -> list[dict]:
    """Pack `devs` bottom-up from U`start`, skipping any U in `gaps`, never exceeding top_u."""
    gaps = gaps or set()
    pos = start
    pls: list[dict] = []
    n = 0
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


def _compute_rack(prefix: str, release: str) -> list[dict]:
    # 2 ToR switches at the top, ~17 servers packed from the bottom (mix 2U/1U)
    servers = [SERVER_2U] * 12 + [SERVER_1U] * 6
    pls = _stack(servers, start=1, release=release, prefix=prefix, top_u=38)
    pls += [_pl(SW_1U, 41, release), _pl(SW_1U_B, 42, release)]
    return pls


def _storage_rack(prefix: str, release: str) -> list[dict]:
    arrays = [STOR_2U] * 9 + [STOR_2U_B] * 6
    pls = _stack(arrays, start=1, release=release, prefix=prefix, top_u=34)
    pls += [_pl(SW_1U, 42, release)]
    return pls


def _gpu_rack(prefix: str, release: str) -> list[dict]:
    pls = _stack([GPU_3U] * 11, start=1, release=release, prefix=prefix, top_u=36)
    pls += [_pl(SW_1U, 41, release), _pl(SW_1U_B, 42, release)]
    return pls


def _network_rack(release: str) -> list[dict]:
    # a spine/leaf-style network rack: switches every other U, leaving airflow gaps
    devs = [SW_1U, SW_1U_B] * 8
    return _stack(devs, start=4, release=release, prefix="NET",
                  gaps={g for g in range(4, 43) if g % 3 == 0}, top_u=42)


CATS = (
    "categories:\n"
    f"  {SERVER_2U}: server\n  {SERVER_1U}: server\n  {SERVER_1U_B}: server\n  {GPU_3U}: server\n"
    f"  {SW_1U}: network\n  {SW_1U_B}: network\n"
    f"  {STOR_2U}: storage\n  {STOR_2U_B}: storage\n"
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


def _git(root: Path, *args: str) -> None:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr}")


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def seed(target: Path) -> Path:
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    R0, R1 = "R25.01", "R26.07"
    base: dict[str, str] = {
        "offerings/cloud-a/offering.yaml": "name: 퍼블릭 클라우드 A\n",
        "offerings/cloud-a/regions/kr-east/region.yaml": "name: 서울 동부\n",
        "offerings/cloud-a/regions/kr-west/region.yaml": "name: 서울 서부\n",
        "categories/overlay.yaml": CATS,
        "pricing/catalog.yaml": PRICES,
        "meta/fields.yaml": FIELDS,
        "candidates/pool.yaml": CANDIDATES,
    }
    # R25.01 baseline — kr-east/az1 fully built out
    for i in range(1, 5):
        base[OFF.format(reg="kr-east", az="az1", rt="compute", rack=f"R{i:02d}")] = \
            _yaml("vertiv-vr3300", _compute_rack(f"E1C{i}", R0))
    for i in range(1, 3):
        base[OFF.format(reg="kr-east", az="az1", rt="storage", rack=f"S{i:02d}")] = \
            _yaml("vertiv-vr3300", _storage_rack(f"E1S{i}", R0))
    base[OFF.format(reg="kr-east", az="az1", rt="network", rack="N01")] = \
        _yaml("vertiv-vr3300", _network_rack(R0))

    _write(target, base)
    _git(target, "init", "-q")
    _git(target, "config", "user.email", "demo@bombom.local")
    _git(target, "config", "user.name", "bombom demo")
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", f"{R0} baseline")
    _git(target, "tag", "-a", R0, "-m", f"release {R0}")

    # R26.07 expansion — az2 compute + kr-west gpu zone
    exp: dict[str, str] = {}
    for i in range(10, 13):
        exp[OFF.format(reg="kr-east", az="az2", rt="compute", rack=f"R{i}")] = \
            _yaml("vertiv-vr3300", _compute_rack(f"E2C{i}", R1))
    for i in range(1, 3):
        exp[OFF.format(reg="kr-west", az="az1", rt="gpu", rack=f"G{i:02d}")] = \
            _yaml("vertiv-vr3300", _gpu_rack(f"WG{i}", R1))
    exp[OFF.format(reg="kr-west", az="az1", rt="compute", rack="R20")] = \
        _yaml("vertiv-vr3300", _compute_rack("WC20", R1))
    _write(target, exp)
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", f"{R1} expansion")
    _git(target, "tag", "-a", R1, "-m", f"release {R1}")

    # sealed confirmation manifests so /diff lists the two releases as selectable refs
    confs = {
        "confirmations/rel-2025-01.yaml": (
            "id: rel-2025-01\nkind: release\nstatus: confirmed\n"
            "requester: designer\napprover: lead\n"
            f"created_at: '2025-01-05T09:00:00'\nconfirmed_at: '2025-01-06T10:00:00'\ntag: {R0}\n"
        ),
        "confirmations/rel-2026-07.yaml": (
            "id: rel-2026-07\nkind: release\nstatus: confirmed\n"
            "requester: designer\napprover: lead\n"
            f"created_at: '2026-07-01T09:00:00'\nconfirmed_at: '2026-07-02T10:00:00'\ntag: {R1}\n"
        ),
    }
    _write(target, confs)
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "seal R25.01 + R26.07 confirmations")
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="?", default="demo-showcase")
    args = ap.parse_args(argv)
    out = seed(Path(args.target))
    print(f"seeded filled showcase workspace at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
