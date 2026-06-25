"""Interactive rack-layout view: /api/layout returns every rack under a path with its SVG +
hierarchy, and the device SVG carries data-* attrs for the click-detail panel."""

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.workspace import Workspace

_RT = "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks"
_FILES = {
    "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n  arista-test-sw: network\n",
    "pricing/p.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n",
    f"{_RT}/R01.yaml": "rack_model: { slug: acme-rack42 }\nplacements:\n"
    "  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n"
    "  - { device: arista-test-sw, position: 42, release: R26.07 }\n",
    f"{_RT}/R02.yaml": "rack_model: { slug: acme-rack42 }\nplacements:\n"
    "  - { device: dell-poweredge-test1, position: 3, release: R26.08 }\n",
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


def test_layout_returns_all_racks_with_svg(client):
    r = client.get("/api/layout?path=offerings/cloud-a")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 2
    ids = {rk["rack_id"] for rk in d["racks"]}
    assert ids == {"R01", "R02"}
    for rk in d["racks"]:
        assert rk["svg"].startswith("<svg")
        assert rk["rack_u"] == 42
        assert rk["hierarchy"]["zone"] == "az1"


def test_svg_devices_carry_click_detail_attrs(client):
    svg = client.get("/api/layout?path=offerings/cloud-a").json()["racks"][0]["svg"]
    assert 'class="dev"' in svg
    assert 'data-device="' in svg
    assert 'data-pos="' in svg
    assert 'data-cat="' in svg


def test_layout_missing_path_is_404(client):
    assert client.get("/api/layout?path=offerings/nope").status_code == 404


def test_layout_route_removed(client):
    # the standalone /layout screen was folded into 존 화면(/place); the API endpoint remains
    assert client.get("/layout").status_code == 404
    assert client.get("/api/layout?path=offerings/cloud-a").status_code == 200
