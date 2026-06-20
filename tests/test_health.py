"""Workspace health: GET /api/health aggregates validation errors, missing-meta, unpriced
placements, and candidate-pool gaps into one report. Read-only over disk."""

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.workspace import Workspace

_FILES = {
    "meta/fields.yaml": "fields:\n  - { key: serial, label: 시리얼, type: string, required: true,"
    " applies_to: placement, scope: 'category:server' }\n",
    "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n",
    "pricing/test.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n",
    # R01: dell priced+serial (clean) + arista unpriced; R02: dell with NO serial (meta error)
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R01.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.07, meta: { serial: S1 } }\n"
        "  - { device: arista-test-sw, position: 40, release: R26.07 }\n",
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R02.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.08 }\n",
    "candidates/pool.yaml": "candidates:\n  - { slug: arista-test-sw, added_at: '2026-06-20' }\n",
}


@pytest.fixture
def client(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    for sub, content in _FILES.items():
        p = root / sub
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    Workspace.open(root, db_path=db)
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False)


def test_health_aggregates_all_issue_kinds(client):
    d = client.get("/api/health?path=offerings/cloud-a").json()
    assert d["ok"] is False
    assert d["counts"]["errors"] >= 1
    assert any("serial" in e["message"] for e in d["errors"])      # R02 dell missing serial
    assert d["counts"]["unpriced"] == 1                            # arista placed in R01
    assert d["unpriced"][0]["device"] and d["unpriced"][0]["location"]
    assert d["counts"]["candidate_unpriced"] == 1                  # arista candidate, no price
    assert d["total"] == sum(d["counts"].values())


def test_health_clean_workspace_is_ok(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    rack = root / "offerings/c/regions/r/zones/z/rack-types/data/racks/R1.yaml"
    rack.parent.mkdir(parents=True)
    rack.write_text("rack_model: { slug: acme-rack42 }\nplacements:\n"
                    "  - { device: dell-poweredge-test1, position: 1, release: R1 }\n")
    (root / "pricing").mkdir()
    (root / "pricing/p.yaml").write_text(
        "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n")
    Workspace.open(root, db_path=db)
    client = TestClient(create_app(root, db_path=db), raise_server_exceptions=False)
    d = client.get("/api/health?path=offerings/c").json()
    assert d["ok"] is True and d["total"] == 0


def test_health_page_served(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "/api/health" in r.text
