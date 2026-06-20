"""Base-data hierarchy management: GET/POST /api/hierarchy + /manage. Throwaway git repo."""

import subprocess

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _count(cwd):
    return int(_git("rev-list", "--count", "HEAD", cwd=cwd).stdout.strip())


@pytest.fixture
def gitws(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    # seed one offering so region/zone tests have a parent
    (root / "offerings" / "cloud-a").mkdir(parents=True)
    (root / "offerings" / "cloud-a" / "offering.yaml").write_text("name: Cloud A\n")
    _git("init", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "tester", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    return root, db


def _client(gitws):
    root, db = gitws
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False), root


def test_create_offering_commits_and_lists(gitws):
    client, root = _client(gitws)
    before = _count(root)
    r = client.post("/api/hierarchy", json={"level": "offering", "offering": "cloud-b",
                                            "name": "Cloud B"})
    assert r.status_code == 200, r.text
    assert (root / "offerings/cloud-b/offering.yaml").exists()
    assert _count(root) == before + 1
    tree = client.get("/api/hierarchy").json()
    cb = next(o for o in tree if o["offering"] == "cloud-b")
    assert cb["name"] == "Cloud B"


def test_create_region_zone_rack_type_chain(gitws):
    client, root = _client(gitws)
    assert client.post("/api/hierarchy", json={"level": "region", "offering": "cloud-a",
                                               "region": "kr-east"}).status_code == 200
    assert client.post("/api/hierarchy", json={"level": "zone", "offering": "cloud-a",
                                               "region": "kr-east", "zone": "az1"}).status_code == 200
    r = client.post("/api/hierarchy", json={"level": "rack_type", "offering": "cloud-a",
                                            "region": "kr-east", "zone": "az1",
                                            "rack_type": "data", "name": "데이터"})
    assert r.status_code == 200, r.text
    assert (root / "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/rack-type.yaml").exists()
    tree = client.get("/api/hierarchy").json()
    rt = tree[0]["regions"][0]["zones"][0]["rack_types"][0]
    assert rt["rack_type"] == "data" and rt["name"] == "데이터"


def test_create_region_missing_parent_404(gitws):
    client, root = _client(gitws)
    r = client.post("/api/hierarchy", json={"level": "region", "offering": "ghost",
                                            "region": "kr-east"})
    assert r.status_code == 404


def test_duplicate_is_409(gitws):
    client, root = _client(gitws)
    body = {"level": "region", "offering": "cloud-a", "region": "kr-east"}
    assert client.post("/api/hierarchy", json=body).status_code == 200
    assert client.post("/api/hierarchy", json=body).status_code == 409


def test_missing_required_segment_400(gitws):
    client, root = _client(gitws)
    r = client.post("/api/hierarchy", json={"level": "zone", "offering": "cloud-a"})
    assert r.status_code == 400          # region/zone missing


def test_traversal_id_rejected(gitws):
    client, root = _client(gitws)
    before = _count(root)
    r = client.post("/api/hierarchy", json={"level": "offering", "offering": "../evil"})
    assert r.status_code == 422
    assert not (root.parent / "evil").exists()
    assert _count(root) == before


def test_manage_page_served(gitws):
    client, root = _client(gitws)
    r = client.get("/manage")
    assert r.status_code == 200 and "기준정보" in r.text
