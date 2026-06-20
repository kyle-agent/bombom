"""Workspace-wide search: GET /api/search finds nodes, racks, and placed devices. Reuses the
report fixture's two-rack workspace (cloud-a / kr-east / data / R01,R02)."""

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.workspace import Workspace

_FILES = {
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R01.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n"
        "  - { device: arista-test-sw, position: 40, release: R26.07 }\n",
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R02.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.08 }\n",
    "pricing/test.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n",
}


@pytest.fixture
def ws_root(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    for sub, content in _FILES.items():
        p = root / sub
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    Workspace.open(root, db_path=db)
    return root, db


def _client(ws_root):
    root, db = ws_root
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False)


def test_search_device_by_model_name(ws_root):
    client = _client(ws_root)
    d = client.get("/api/search?q=poweredge").json()
    devs = [h for h in d["results"] if h["kind"] == "device"]
    assert devs and all(h["path"].endswith(".yaml") for h in devs)
    assert any(h["device"] == "dell-poweredge-test1" for h in devs)


def test_search_rack_by_id(ws_root):
    client = _client(ws_root)
    d = client.get("/api/search?q=R02").json()
    racks = [h for h in d["results"] if h["kind"] == "rack"]
    assert racks and racks[0]["rack"] == "R02"
    assert racks[0]["path"].endswith("R02.yaml")        # links to the viewer


def test_search_node_by_name(ws_root):
    client = _client(ws_root)
    d = client.get("/api/search?q=kr-east").json()
    assert any(h["kind"] == "region" and h["ident"] == "kr-east" for h in d["results"])


def test_search_empty_query_returns_nothing(ws_root):
    client = _client(ws_root)
    d = client.get("/api/search?q=%20").json()
    assert d["count"] == 0 and d["results"] == []


def test_search_page_served(ws_root):
    client = _client(ws_root)
    r = client.get("/search")
    assert r.status_code == 200
    assert "/api/search" in r.text
