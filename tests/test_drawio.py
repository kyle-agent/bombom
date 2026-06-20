"""draw.io export: rack elevations as editable mxGraph XML. Whole subtree (AZ / Rack-Type)
lands on one canvas; geometry/colors mirror the SVG renderer."""

import xml.etree.ElementTree as ET

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.workspace import Workspace

_RT = "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks"
_FILES = {
    "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n"
    "  arista-test-sw: network\n",
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


def test_drawio_is_wellformed_mxgraph(client):
    r = client.get("/api/rack/elevation.drawio?path=offerings/cloud-a")
    assert r.status_code == 200
    root = ET.fromstring(r.text)            # parses → well-formed XML
    assert root.tag == "mxfile"
    cells = root.findall(".//mxCell")
    assert any(c.get("style", "").startswith("rounded=1") for c in cells)


def test_whole_subtree_on_one_canvas(client):
    """Both racks under the rack-type appear, laid out at different x (left→right)."""
    xml = client.get("/api/rack/elevation.drawio?path=offerings/cloud-a").text
    root = ET.fromstring(xml)
    frames = [c for c in root.findall(".//mxCell") if "container=1" in (c.get("style") or "")]
    assert len(frames) == 2                                   # R01 + R02
    xs = {c.find("mxGeometry").get("x") for c in frames}
    assert len(xs) == 2                                       # distinct columns

    # devices are children of their frame and carry model + U label
    devs = [c for c in root.findall(".//mxCell")
            if (c.get("parent") or "").startswith("rack") and c.get("vertex") == "1"]
    assert any("PowerEdge TEST1" in (c.get("value") or "") for c in devs)
    assert any("U1 ·" in (c.get("value") or "") for c in devs)


def test_download_sets_attachment_header(client):
    r = client.get("/api/rack/elevation.drawio?path=offerings/cloud-a&download=1")
    assert r.status_code == 200
    assert ".drawio" in r.headers.get("content-disposition", "")


def test_single_rack_path_also_works(client):
    xml = client.get(f"/api/rack/elevation.drawio?path={_RT}/R01.yaml").text
    root = ET.fromstring(xml)
    frames = [c for c in root.findall(".//mxCell") if "container=1" in (c.get("style") or "")]
    assert len(frames) == 1


def test_missing_path_is_404(client):
    r = client.get("/api/rack/elevation.drawio?path=offerings/nope")
    assert r.status_code == 404
