"""Ref-to-ref release diff: GET /api/release/diff compares two confirmed design sets (git
tags) — or the working tree — and reports added / removed / replaced devices + CAPEX delta.
Runs against a throwaway git repo with two tagged states."""

import subprocess

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex

RACK = "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R02.yaml"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _write_rack(root, placements_yaml):
    p = root / RACK
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("rack_model: { slug: acme-rack42 }\nplacements:\n" + placements_yaml)


@pytest.fixture
def gitws(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    root.mkdir()
    (root / "pricing").mkdir()
    (root / "pricing/test.yaml").write_text(
        "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n"
        "  - { slug: arista-test-sw, unit_cost: 2000000 }\n")
    # REL1: dell @1, arista @20
    _write_rack(root, "  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n"
                      "  - { device: arista-test-sw, position: 20, release: R26.07 }\n")
    _git("init", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "tester", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "rel1", cwd=root)
    _git("tag", "REL1", cwd=root)
    # REL2: dell→arista @1 (replace), @20 removed, dell @40 added
    _write_rack(root, "  - { device: arista-test-sw, position: 1, release: R26.08 }\n"
                      "  - { device: dell-poweredge-test1, position: 40, release: R26.08 }\n")
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "rel2", cwd=root)
    _git("tag", "REL2", cwd=root)
    return root, db


def _client(gitws):
    root, db = gitws
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False), root


def test_diff_added_removed_replaced(gitws):
    client, _ = _client(gitws)
    d = client.get("/api/release/diff?base=REL1&head=REL2&path=offerings").json()
    assert d["counts"] == {"added": 1, "removed": 1, "changed": 1}
    assert d["added"][0]["device"] == "dell-poweredge-test1" and d["added"][0]["position"] == 40
    assert d["removed"][0]["device"] == "arista-test-sw" and d["removed"][0]["position"] == 20
    chg = d["changed"][0]
    assert chg["position"] == 1
    assert chg["from_device"] == "dell-poweredge-test1" and chg["to_device"] == "arista-test-sw"
    assert chg["delta"] == 1_000_000          # 2,000,000 - 1,000,000
    # concrete totals: base = dell@1 (1M) + arista@20 (2M); head = arista@1 (2M) + dell@40 (1M)
    assert d["base_capex"] == 3_000_000 and d["head_capex"] == 3_000_000
    assert d["capex_delta"] == 0
    # the delta must decompose into added − removed + changed-deltas
    decomposed = (sum(r["capex"] for r in d["added"]) - sum(r["capex"] for r in d["removed"])
                  + sum(r["delta"] for r in d["changed"]))
    assert d["capex_delta"] == decomposed


def test_diff_against_working_tree(gitws):
    client, root = _client(gitws)
    # working tree currently == REL2 content → diff vs REL2 is empty
    d = client.get("/api/release/diff?base=REL2&head=WORKING&path=offerings").json()
    assert d["counts"] == {"added": 0, "removed": 0, "changed": 0}
    # now make an UNCOMMITTED working-tree change and confirm WORKING reflects it
    _write_rack(root, "  - { device: arista-test-sw, position: 1, release: R26.08 }\n"
                      "  - { device: dell-poweredge-test1, position: 40, release: R26.08 }\n"
                      "  - { device: dell-poweredge-test1, position: 60, release: R26.09 }\n")
    d2 = client.get("/api/release/diff?base=REL2&head=WORKING&path=offerings").json()
    assert d2["counts"] == {"added": 1, "removed": 0, "changed": 0}
    assert d2["added"][0]["position"] == 60


def test_diff_rejects_unsafe_ref(gitws):
    client, _ = _client(gitws)
    bad = client.get("/api/release/diff?base=REL1&head=../../etc&path=offerings")
    assert bad.status_code == 400


def test_diff_unknown_ref_404(gitws):
    client, _ = _client(gitws)
    # syntactically valid but nonexistent tag → 404, not a giant spurious diff
    r = client.get("/api/release/diff?base=REL1&head=NOPE99&path=offerings")
    assert r.status_code == 404


def test_diff_same_ref_is_empty(gitws):
    client, _ = _client(gitws)
    d = client.get("/api/release/diff?base=REL1&head=REL1&path=offerings").json()
    assert d["counts"] == {"added": 0, "removed": 0, "changed": 0}
    assert d["capex_delta"] == 0


def test_diff_priced_at_ref_reflects_price_drift(gitws):
    client, root = _client(gitws)
    # New sealed state REL3: same racks as REL2 but dell repriced 1,000,000 → 3,000,000.
    (root / "pricing/test.yaml").write_text(
        "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 3000000 }\n"
        "  - { slug: arista-test-sw, unit_cost: 2000000 }\n")
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "reprice", cwd=root)
    _git("tag", "REL3", cwd=root)
    d = client.get("/api/release/diff?base=REL1&head=REL3&path=offerings&priced_at_ref=1").json()
    assert d["priced_at_ref"] is True
    # base REL1 @ REL1 prices: dell(1M)+arista(2M)=3M; head REL3 @ REL3 prices: arista(2M)+dell(3M)=5M
    assert d["base_capex"] == 3_000_000 and d["head_capex"] == 5_000_000
    assert d["capex_delta"] == 2_000_000
    decomposed = (sum(r["capex"] for r in d["added"]) - sum(r["capex"] for r in d["removed"])
                  + sum(r["delta"] for r in d["changed"]))
    assert d["capex_delta"] == decomposed


def test_diff_page_served(gitws):
    client, _ = _client(gitws)
    r = client.get("/diff")
    assert r.status_code == 200
    assert "변경 비교" in r.text and "/api/release/diff" in r.text
