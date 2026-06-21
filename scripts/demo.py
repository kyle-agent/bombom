#!/usr/bin/env python3
"""Seed a self-contained demo workspace so every page in the app has realistic data.

Run `python scripts/demo.py` then `bombom serve --root demo-workspace` and click through:

  /manage      offering/region/zone/rack-type tree (+ ⬇ draw.io export per AZ / Rack-Type)
  /candidates  candidate pool with prices + structured meta (one priced, one unpriced, one
               missing its required lead-time → shows the gaps /health reports)
  /search      find nodes / racks / placed devices by name
  /health      validation dashboard — this demo SEEDS issues on purpose (U overlap, missing
               required serial, unpriced placement, candidate gaps) so the page isn't empty
  /edit        place devices into a rack; ✅ confirm gate
  /placed      placed-device list + CAPEX total + release filter + CSV
  /dashboard   cumulative CAPEX rollup by hierarchy / category / release
  /diff        compare releases — the seed tags R25.01 and R26.07 and leaves one uncommitted
               working edit, so base→head and ↔ WORKING both show real deltas

The org/pricing data lives in the demo dir; the hardware catalog stays shared (the repo's
.index/catalog.db). Idempotent: the target dir is wiped and rebuilt each run.

All slugs below exist in the vendored devicetype-library catalog.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

OFF = "offerings/cloud-a/regions/{reg}/zones/{az}/rack-types/{rt}/racks/{rack}.yaml"


def _rack(slug: str) -> str:  # rack file header (physical rack model)
    return f"rack_model: {{ slug: {slug} }}\n"


# ── state A — the R25.01 baseline (committed, tagged R25.01) ──────────────────
# A small first build: one zone, two racks, early placements only.
STATE_A: dict[str, str] = {
    "offerings/cloud-a/offering.yaml": "name: 퍼블릭 클라우드 A\n",
    "categories/overlay.yaml": (
        "# slug → category (drives elevation color + meta scope). Unset falls back to a heuristic.\n"
        "categories:\n"
        "  dell-poweredge-r760: server\n"
        "  dell-poweredge-r660: server\n"
        "  dell-poweredge-r650: server\n"
        "  arista-dcs-7050cx3-32s: network\n"
    ),
    "pricing/dell.yaml": (
        "# 가격 오버레이(원화, 시안). 카탈로그/설계와 분리 보관. r650은 일부러 미가격.\n"
        "entries:\n"
        "  - { slug: dell-poweredge-r760, unit_cost: 19500000, valid_from: 2025-01-01, source: 시안 }\n"
        "  - { slug: dell-poweredge-r660, unit_cost: 15000000, source: 시안 }\n"
    ),
    "meta/fields.yaml": (
        "# 디바이스 메타(커스텀 필드) 정의 — NetBox Custom Fields에 해당.\n"
        "fields:\n"
        "  - { key: asset_class, label: 자산분류, type: enum, options: [compute, gpu, storage, network],\n"
        "      required: true, applies_to: device_type, scope: \"category:server\" }\n"
        "  - { key: serial, label: 시리얼, type: string, required: true,\n"
        "      applies_to: placement, scope: \"category:server\" }\n"
        "  - { key: owner, label: 담당팀, type: string, required: false, applies_to: placement, scope: all }\n"
        "  - { key: lead_time_weeks, label: 리드타임(주), type: number, required: true,\n"
        "      applies_to: candidate, scope: all }\n"
    ),
    "candidates/pool.yaml": (
        "# 후보풀: 가격/메타 입력 대상. 일부러 불완전하게 둬서 /health 갭을 보여준다.\n"
        "candidates:\n"
        "  - { slug: dell-poweredge-r760, added_at: '2026-06-20', meta: { lead_time_weeks: 8 } }\n"
        "  - { slug: dell-poweredge-r650, added_at: '2026-06-20', meta: { lead_time_weeks: 12 } }  # 미가격 후보\n"
        "  - { slug: dell-poweredge-r660, added_at: '2026-06-20' }  # 필수 lead_time 누락\n"
    ),
    OFF.format(reg="kr-east", az="az1", rt="data", rack="R01"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r760, position: 1, release: R25.01, meta: { serial: R760-A1, asset_class: compute, owner: infra } }\n"
        + "  - { device: dell-poweredge-r660, position: 3, release: R25.01, meta: { serial: R660-A1, asset_class: compute } }\n"
        + "  - { device: arista-dcs-7050cx3-32s, position: 42, release: R25.01 }\n"
    ),
    OFF.format(reg="kr-east", az="az1", rt="data", rack="R02"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r760, position: 1, release: R25.01, meta: { serial: R760-A2, asset_class: compute, owner: infra } }\n"
    ),
}

# ── state B — the R26.07 expansion (committed, tagged R26.07) ─────────────────
# New zone, GPU rack-type, a second region, more placements. Replaces R02 with extra
# R26.07 rows (one intentionally missing its required serial → /health warning).
STATE_B: dict[str, str] = {
    OFF.format(reg="kr-east", az="az1", rt="data", rack="R02"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r760, position: 1, release: R25.01, meta: { serial: R760-A2, asset_class: compute, owner: infra } }\n"
        + "  - { device: dell-poweredge-r760, position: 3, release: R26.07, meta: { owner: infra } }  # serial 누락(필수)\n"
        + "  - { device: dell-poweredge-r660, position: 5, release: R26.07, meta: { serial: R660-A2, asset_class: compute } }\n"
        + "custom_line_items:\n"
        + "  - { name: \"DAC 100G 3m\", qty: 8, unit_cost: 90000, release: R26.07, category: other }\n"
    ),
    # R03 deliberately broken for /health: unpriced device (r650) + U1 overlap (two devices at U1)
    OFF.format(reg="kr-east", az="az1", rt="data", rack="R03"): (
        "# 데모: 미가격 배치 + U 겹침(검증 오류) — /health 에서 확인\n"
        + _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r650, position: 10, release: R26.07, meta: { serial: R650-1, asset_class: compute } }  # 미가격\n"
        + "  - { device: dell-poweredge-r760, position: 1, release: R26.07, meta: { serial: DUP, asset_class: compute } }\n"
        + "  - { device: dell-poweredge-r660, position: 1, release: R26.07, meta: { serial: DUP2, asset_class: compute } }  # U1 겹침\n"
    ),
    OFF.format(reg="kr-east", az="az1", rt="gpu", rack="G01"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r760, position: 1, release: R26.07, meta: { serial: GPU-1, asset_class: gpu, owner: ml } }\n"
        + "  - { device: dell-poweredge-r760, position: 3, release: R26.07, meta: { serial: GPU-2, asset_class: gpu, owner: ml } }\n"
    ),
    OFF.format(reg="kr-east", az="az2", rt="data", rack="R10"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r660, position: 1, release: R26.07, meta: { serial: R660-B1, asset_class: compute } }\n"
        + "  - { device: dell-poweredge-r660, position: 3, release: R26.07, meta: { serial: R660-B2, asset_class: compute } }\n"
    ),
    OFF.format(reg="kr-west", az="az1", rt="network", rack="N01"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: arista-dcs-7050cx3-32s, position: 40, release: R26.07 }\n"
        + "  - { device: arista-dcs-7050cx3-32s, position: 42, release: R26.07 }\n"
    ),
    "offerings/cloud-a/regions/kr-east/region.yaml": "name: 서울 동부\n",
    "offerings/cloud-a/regions/kr-west/region.yaml": "name: 서울 서부\n",
}

# ── working edit — uncommitted, so /diff R26.07 ↔ WORKING is non-empty ────────
WORKING_EDIT: dict[str, str] = {
    OFF.format(reg="kr-east", az="az2", rt="data", rack="R10"): (
        _rack("vertiv-vr3300")
        + "placements:\n"
        + "  - { device: dell-poweredge-r660, position: 1, release: R26.07, meta: { serial: R660-B1, asset_class: compute } }\n"
        + "  - { device: dell-poweredge-r660, position: 3, release: R26.07, meta: { serial: R660-B2, asset_class: compute } }\n"
        + "  - { device: dell-poweredge-r760, position: 5, release: R26.08, meta: { serial: R760-B3, asset_class: compute } }  # 작업본 추가\n"
    ),
}


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def _git(root: Path, *args: str) -> None:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr}")


def seed(target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    # tagged history so /diff has two real releases to compare
    _write(target, STATE_A)
    _git(target, "init", "-q")
    _git(target, "config", "user.email", "demo@bombom.local")
    _git(target, "config", "user.name", "bombom demo")
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "R25.01 baseline")
    _git(target, "tag", "-a", "R25.01", "-m", "release R25.01 (baseline)")

    _write(target, STATE_B)
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "R26.07 expansion")
    _git(target, "tag", "-a", "R26.07", "-m", "release R26.07 (expansion)")

    # leave one uncommitted edit so WORKING differs from R26.07
    _write(target, WORKING_EDIT)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="seed a demo workspace for local testing")
    ap.add_argument("target", nargs="?", default="demo-workspace",
                    help="workspace dir to create (default: demo-workspace)")
    args = ap.parse_args(argv)

    target = Path(args.target).resolve()
    seed(target)
    rel = target.name
    print(f"✓ demo workspace seeded: {target}")
    print("  releases tagged: R25.01, R26.07  (+ one uncommitted WORKING edit)")
    print()
    print("Next:")
    print(f"  bombom serve --root {rel}        # → http://127.0.0.1:8000/")
    print("  open /manage /candidates /search /health /edit /placed /dashboard /diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
