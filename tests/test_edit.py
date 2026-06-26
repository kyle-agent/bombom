"""Write-path tests: PUT /api/rack writes YAML + commits to git; rejects invalid; meta
persists. Runs against a throwaway git repo so the real repo is never touched."""

import subprocess

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.design import RackDesign, load_racks
from bombom.design.writer import rack_to_dict

RACKFILE = "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R02.yaml"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _count(cwd):
    return int(_git("rev-list", "--count", "HEAD", cwd=cwd).stdout.strip())


@pytest.fixture
def gitws(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    racks = root / "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks"
    racks.mkdir(parents=True)
    (racks / "R02.yaml").write_text(
        "rack_model: { slug: acme-rack42 }\n"
        "placements:\n  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n"
    )
    files = {
        "pricing/test.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n"
        "  - { slug: arista-test-sw, unit_cost: 2000000 }\n",
        "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n",
        "meta/fields.yaml": "fields:\n  - { key: serial, label: 시리얼, type: string,"
        " required: true, applies_to: placement, scope: 'category:server' }\n",
    }
    for sub, content in files.items():
        p = root / sub
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git("init", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "tester", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    return root, db


def _client(gitws):
    root, db = gitws
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False), root


def test_put_writes_yaml_and_commits(gitws):
    client, root = _client(gitws)
    before = _count(root)
    body = {"rack_model": {"slug": "acme-rack42"}, "placements": [
        {"device": "dell-poweredge-test1", "position": 1, "release": "R26.07", "meta": {"serial": "S1"}},
        {"device": "arista-test-sw", "position": 40, "release": "R26.07"},
    ]}
    r = client.put(f"/api/rack?path={RACKFILE}&message=add+switch", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["commit"]
    assert _count(root) == before + 1
    design = load_racks(root / RACKFILE).racks[0].design
    assert any(p.device == "arista-test-sw" for p in design.placements)


def test_put_rejects_overlap_no_write_no_commit(gitws):
    client, root = _client(gitws)
    before = _count(root)
    body = {"rack_model": {"slug": "acme-rack42"}, "placements": [
        {"device": "dell-poweredge-test1", "position": 1, "release": "R1"},
        {"device": "dell-poweredge-test1", "position": 2, "release": "R1"},  # 2U → overlaps U2
    ]}
    r = client.put(f"/api/rack?path={RACKFILE}&message=x", json=body)
    assert r.status_code == 400
    assert _count(root) == before                                   # no commit
    assert len(load_racks(root / RACKFILE).racks[0].design.placements) == 1  # file unchanged


def test_clone_rack_copies_placements_and_commits(gitws):
    client, root = _client(gitws)
    before = _count(root)
    r = client.post("/api/rack/clone", json={"source_path": RACKFILE, "rack": "R09"})
    assert r.status_code == 200, r.text
    assert _count(root) == before + 1
    dst = RACKFILE.replace("R02.yaml", "R09.yaml")
    src_pl = load_racks(root / RACKFILE).racks[0].design.placements
    dst_pl = load_racks(root / dst).racks[0].design.placements
    assert [p.device for p in dst_pl] == [p.device for p in src_pl]   # byte-for-byte copy
    assert r.json()["path"].endswith("R09.yaml")


def test_move_rack_reclassifies_and_commits(gitws):
    client, root = _client(gitws)
    before = _count(root)
    r = client.post("/api/rack/move", json={"source_path": RACKFILE, "rack_type": "compute"})
    assert r.status_code == 200, r.text
    assert _count(root) == before + 1
    # the rack left its old rack-type and now lives under the new one, contents intact
    assert not (root / RACKFILE).exists()
    dst = RACKFILE.replace("rack-types/data/", "rack-types/compute/")
    assert (root / dst).exists()
    pl = load_racks(root / dst).racks[0].design.placements
    assert [p.device for p in pl] == ["dell-poweredge-test1"]
    assert r.json()["path"].endswith("rack-types/compute/racks/R02.yaml")


def test_move_rack_conflict_409(gitws):
    client, root = _client(gitws)
    # seed an existing R02 under the target rack-type so the move collides
    dst = root / RACKFILE.replace("rack-types/data/", "rack-types/compute/")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("rack_model: { slug: acme-rack42 }\nplacements: []\n")
    before = _count(root)
    r = client.post("/api/rack/move", json={"source_path": RACKFILE, "rack_type": "compute"})
    assert r.status_code == 409
    assert (root / RACKFILE).exists()                                # source untouched
    assert _count(root) == before


def test_move_rack_rejects_unsafe_type(gitws):
    client, _ = _client(gitws)
    r = client.post("/api/rack/move", json={"source_path": RACKFILE, "rack_type": "../evil"})
    assert r.status_code == 422


def test_clone_rack_conflict_409(gitws):
    client, root = _client(gitws)
    before = _count(root)
    r = client.post("/api/rack/clone", json={"source_path": RACKFILE, "rack": "R02"})  # exists
    assert r.status_code == 409
    assert _count(root) == before                                    # no commit


def test_clone_rack_rejects_unsafe_id(gitws):
    client, _ = _client(gitws)
    r = client.post("/api/rack/clone", json={"source_path": RACKFILE, "rack": "../evil"})
    assert r.status_code == 422


def test_clone_bulk_makes_n_copies_one_commit(gitws):
    client, root = _client(gitws)
    before = _count(root)
    r = client.post("/api/rack/clone-bulk",
                    json={"source_path": RACKFILE, "racks": ["R10", "R11", "R12"]})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 3
    assert _count(root) == before + 1                        # single commit for the batch
    for name in ("R10", "R11", "R12"):
        dst = RACKFILE.replace("R02.yaml", f"{name}.yaml")
        assert load_racks(root / dst).racks[0].design.placements    # placements carried


def test_clone_bulk_conflict_is_all_or_nothing(gitws):
    client, root = _client(gitws)
    before = _count(root)
    # R02 already exists → whole batch aborts, no file written, no commit
    r = client.post("/api/rack/clone-bulk",
                    json={"source_path": RACKFILE, "racks": ["R20", "R02"]})
    assert r.status_code == 409
    assert _count(root) == before
    assert not (root / RACKFILE.replace("R02.yaml", "R20.yaml")).exists()


def test_clone_bulk_rejects_duplicate_ids(gitws):
    client, _ = _client(gitws)
    r = client.post("/api/rack/clone-bulk",
                    json={"source_path": RACKFILE, "racks": ["R30", "R30"]})
    assert r.status_code == 422


def test_get_then_meta_persist_clears_missing(gitws):
    client, root = _client(gitws)
    got = client.get(f"/api/rack?path={RACKFILE}").json()
    assert any("serial" in p["meta_missing"] for p in got["rack"]["placements"])
    body = {"rack_model": {"slug": "acme-rack42"}, "placements": [
        {"device": "dell-poweredge-test1", "position": 1, "release": "R26.07", "meta": {"serial": "S9"}},
    ]}
    out = client.put(f"/api/rack?path={RACKFILE}&message=meta", json=body).json()
    assert all(not p["meta_missing"] for p in out["rack"]["placements"])


def test_put_rejects_legacy_role_field(gitws):
    # The editor used to send a `role` field; it was removed in the rack_type/rack_model
    # refactor and RackDesign forbids extras. A stray `role` must be rejected (regression:
    # this broke every editor save with a 422 while the rack looked "saved" from POST /new).
    client, root = _client(gitws)
    body = {"rack_model": {"slug": "acme-rack42"}, "role": "data", "placements": []}
    r = client.put(f"/api/rack?path={RACKFILE}&message=x", json=body)
    assert r.status_code == 422
    assert any(e.get("loc", [])[-1] == "role" for e in r.json()["detail"])


def test_put_accepts_editor_payload_with_custom_items(gitws):
    # The canonical editor save shape (rack_model + placements + custom_line_items, NO role).
    client, root = _client(gitws)
    body = {
        "rack_model": {"slug": "acme-rack42"},
        "placements": [{"device": "arista-test-sw", "position": 1, "release": "R26.07",
                        "qty": 1, "meta": {}}],
        "custom_line_items": [{"name": "케이블", "qty": 2, "unit_cost": 5000,
                               "release": "R26.07", "category": "other"}],
    }
    r = client.put(f"/api/rack?path={RACKFILE}&message=editor+save", json=body)
    assert r.status_code == 200, r.text


def test_put_path_traversal_blocked(gitws):
    client, root = _client(gitws)
    r = client.put("/api/rack?path=../evil/racks/x.yaml&message=x",
                   json={"rack_model": {"slug": "acme-rack42"}, "placements": []})
    assert r.status_code == 400
    assert not (root.parent / "evil").exists()


def test_edit_route_serves_editor(gitws):
    client, _ = _client(gitws)
    r = client.get("/edit")
    assert r.status_code == 200 and "랙관리" in r.text


def test_new_rack_creates_file_and_commits(gitws):
    client, root = _client(gitws)
    before = _count(root)
    body = {"offering": "cloud-a", "region": "kr-east", "zone": "az1",
            "rack_type": "data", "rack": "R09", "rack_model": "acme-rack42"}
    r = client.post("/api/rack/new", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["commit"] and out["rack"] == "R09"
    target = root / out["path"]
    assert target.exists()
    assert _count(root) == before + 1
    d = load_racks(target).racks[0].design
    assert d.rack_model.slug == "acme-rack42" and d.placements == []


def test_new_rack_rejects_unknown_model(gitws):
    client, root = _client(gitws)
    before = _count(root)
    body = {"offering": "cloud-a", "region": "kr-east", "zone": "az1",
            "rack_type": "data", "rack": "R10", "rack_model": "does-not-exist"}
    r = client.post("/api/rack/new", json=body)
    assert r.status_code == 400
    assert _count(root) == before


def test_new_rack_rejects_duplicate(gitws):
    client, root = _client(gitws)
    body = {"offering": "cloud-a", "region": "kr-east", "zone": "az1",
            "rack_type": "data", "rack": "R02", "rack_model": "acme-rack42"}
    r = client.post("/api/rack/new", json=body)
    assert r.status_code == 409


def test_new_rack_rejects_traversal_id(gitws):
    client, root = _client(gitws)
    body = {"offering": "cloud-a", "region": "kr-east", "zone": "az1",
            "rack_type": "data", "rack": "../../../evil", "rack_model": "acme-rack42"}
    r = client.post("/api/rack/new", json=body)
    assert r.status_code == 422  # pydantic validation rejects the id
    assert not (root.parent / "evil.yaml").exists()


def test_writer_roundtrip(gitws):
    _, root = _client(gitws)
    d = load_racks(root / RACKFILE).racks[0].design
    d2 = RackDesign.model_validate(rack_to_dict(d))
    assert d2.rack_model.slug == d.rack_model.slug
    assert [p.device for p in d2.placements] == [p.device for p in d.placements]
