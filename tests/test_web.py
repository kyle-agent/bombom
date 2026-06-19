"""Tests for scaffold, category/meta overlays, SVG render, export, and the API.
Reuses the catalog `library` fixture to build a small index, then lays out a tmp workspace."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from bombom import scaffold
from bombom.api import create_app
from bombom.bom import compute_bom
from bombom.catalog import Catalog, reindex
from bombom.design import load_racks
from bombom.export import build_data, write_export
from bombom.overlay import CategoryBook, FieldDef, required_missing
from bombom.render import rack_elevation_svg
from bombom.workspace import Workspace


@pytest.fixture
def catalog(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    return Catalog(db), db


@pytest.fixture
def ws_root(tmp_path, catalog):
    """A tmp workspace: hierarchy + pricing + categories + meta fields."""
    root = tmp_path / "wsroot"
    racks = root / "offerings/cloud-a/regions/kr-east/zones/az1/rack-groups/row-3/racks"
    racks.mkdir(parents=True)
    (racks / "R02.yaml").write_text(
        "rack_type: { slug: acme-rack42 }\n"
        "role: data\n"
        "placements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.07, meta: { serial: S1 } }\n"
        "  - { device: dell-poweredge-test1, position: 5, release: R26.07 }\n"   # serial missing
        "  - { device: arista-test-sw, position: 40, release: R25.01 }\n"
    )
    (root / "pricing").mkdir()
    (root / "pricing/test.yaml").write_text(
        "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n"
        "  - { slug: arista-test-sw, unit_cost: 2000000 }\n"
    )
    (root / "categories").mkdir()
    (root / "categories/overlay.yaml").write_text(
        "categories:\n  dell-poweredge-test1: server\n  arista-test-sw: network\n"
    )
    (root / "meta").mkdir()
    (root / "meta/fields.yaml").write_text(
        "fields:\n"
        "  - { key: serial, label: 시리얼, type: string, required: true,"
        " applies_to: placement, scope: 'category:server' }\n"
    )
    return root, catalog[1]


# ---- scaffold ----
def test_scaffold_creates_loadable_rack(tmp_path):
    scaffold.scaffold_offering(tmp_path, "demo")
    scaffold.scaffold_region(tmp_path, "demo", "r1")
    scaffold.scaffold_zone(tmp_path, "demo", "r1", "z1")
    scaffold.scaffold_rack_group(tmp_path, "demo", "r1", "z1", "g1")
    p = scaffold.scaffold_rack(tmp_path, "demo", "r1", "z1", "g1", "R1", rack_type_slug="acme-rack42")
    assert p.exists()
    loaded = load_racks(tmp_path / "offerings/demo")
    assert len(loaded.racks) == 1 and loaded.racks[0].rack_id == "R1"


def test_clone_subtree(tmp_path):
    scaffold.scaffold_zone(tmp_path, "demo", "r1", "az1")
    src = tmp_path / "offerings/demo/regions/r1/zones/az1"
    dst = scaffold.clone_subtree(src, "az2")
    assert (dst / "zone.yaml").exists()


# ---- category overlay ----
def test_category_set_and_heuristic(tmp_path):
    book = CategoryBook.load(tmp_path / "categories/overlay.yaml")
    assert book.get("whatever-switch") == "network"          # heuristic
    book.set("acme-thing", "storage")
    assert CategoryBook.load(tmp_path / "categories/overlay.yaml").get("acme-thing") == "storage"


# ---- meta required (conditional) ----
def test_required_missing_scoped():
    fields = [FieldDef(key="serial", required=True, applies_to="placement", scope="category:server")]
    assert required_missing(fields, {}, applies_to="placement", category="server") == ["serial"]
    assert required_missing(fields, {}, applies_to="placement", category="network") == []
    assert required_missing(fields, {"serial": "x"}, applies_to="placement", category="server") == []


def test_engine_flags_missing_meta(ws_root):
    root, db = ws_root
    ws = Workspace.open(root, db_path=db)
    r = compute_bom(root / "offerings/cloud-a", catalog=ws.catalog, pricebook=ws.pricebook,
                    categories=ws.categories, fields=ws.fields, type_meta=ws.type_meta)
    assert any("메타 필수 누락: serial" in i.message for i in r.issues)
    # the priced server still totals (2× test1 + arista)
    assert r.total_capex == 4_000_000


# ---- svg ----
def test_svg_render(ws_root):
    root, db = ws_root
    cat = Catalog(db)
    design = load_racks(root / "offerings/cloud-a").racks[0].design
    svg = rack_elevation_svg(design, cat, categories=CategoryBook.load(root / "categories/overlay.yaml"))
    assert svg.startswith("<svg") and "PowerEdge" in svg


# ---- export ----
def test_build_and_write_export(ws_root, tmp_path):
    root, db = ws_root
    ws = Workspace.open(root, db_path=db)
    payload = build_data(ws, root / "offerings/cloud-a", is_mock=False)
    assert payload["bom"]["total_capex"] == 4_000_000
    assert payload["tree"]["offering"] == "cloud-a"
    assert "R02" in payload["racks"]
    template = Path("web/viewer.html")
    out = write_export(payload, tmp_path / "out.html", template=template)
    text = out.read_text()
    assert "total_capex" in text and "/*__BOMBOM_DATA__*/" in text


# ---- api ----
def test_api_endpoints(ws_root):
    root, db = ws_root
    client = TestClient(create_app(root, db_path=db))
    assert client.get("/api/tree?path=offerings/cloud-a").json()["offering"] == "cloud-a"
    bom = client.get("/api/bom?path=offerings/cloud-a").json()
    assert bom["total_capex"] == 4_000_000
    hits = client.get("/api/catalog/search?q=poweredge").json()
    assert any(h["slug"] == "dell-poweredge-test1" for h in hits)
    svg = client.get(
        "/api/rack/elevation.svg"
        "?path=offerings/cloud-a/regions/kr-east/zones/az1/rack-groups/row-3/racks/R02.yaml")
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml"
