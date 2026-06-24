"""Overview aggregation powers the main page (offering→region→zone summary) and the
group-by report. Counts/CAPEX must reconcile with the BOM and split correctly per level."""

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.overview import build_overview
from bombom.workspace import Workspace

_RT = "offerings/cloud-a/regions/kr-east/zones/{z}/rack-types/{rt}/racks/{r}.yaml"
_FILES = {
    "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n  arista-test-sw: network\n",
    "pricing/p.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n"
    "  - { slug: arista-test-sw, unit_cost: 500000 }\n",
    _RT.format(z="az1", rt="compute", r="R01"): "rack_model: { slug: acme-rack42 }\nplacements:\n"
    "  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n"
    "  - { device: dell-poweredge-test1, position: 3, release: R26.07 }\n"
    "  - { device: arista-test-sw, position: 42, release: R26.07 }\n",
    _RT.format(z="az2", rt="compute", r="R10"): "rack_model: { slug: acme-rack42 }\nplacements:\n"
    "  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n",
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
    return Workspace.open(root, db_path=db), root


def test_overview_totals_and_split(ws_root):
    ws, root = ws_root
    ov = build_overview(ws, root)
    t = ov["totals"]
    assert t["racks"] == 2
    assert t["devices"] == 4               # 3 in R01 + 1 in R10
    assert t["servers"] == 3               # the switch is network, not server
    assert t["capex"] == 3 * 1_000_000 + 1 * 500_000

    zones = {z["zone"]: z for o in ov["tree"] for r in o["regions"] for z in r["zones"]}
    assert set(zones) == {"az1", "az2"}
    assert zones["az1"]["servers"] == 2 and zones["az1"]["devices"] == 3
    assert zones["az2"]["servers"] == 1
    assert zones["az1"]["path"] == "offerings/cloud-a/regions/kr-east/zones/az1"


def test_overview_groups_present(ws_root):
    ws, root = ws_root
    ov = build_overview(ws, root)
    assert set(ov["groups"]) == {"offering", "region", "zone", "rack_type"}
    # rack_type rollup: one compute group spanning both racks
    rt = {g["label"]: g for g in ov["groups"]["rack_type"]}
    assert rt["compute"]["racks"] == 2 and rt["compute"]["servers"] == 3


def test_overview_endpoint(ws_root):
    ws, root = ws_root
    client = TestClient(create_app(root, db_path=ws.catalog.db_path),
                        raise_server_exceptions=False)
    r = client.get("/api/overview?path=offerings/cloud-a")
    assert r.status_code == 200
    assert r.json()["totals"]["devices"] == 4


@pytest.mark.parametrize("route", ["/home", "/zone", "/summary"])
def test_flow_pages_served(ws_root, route):
    ws, root = ws_root
    client = TestClient(create_app(root, db_path=ws.catalog.db_path),
                        raise_server_exceptions=False)
    assert client.get(route).status_code == 200
