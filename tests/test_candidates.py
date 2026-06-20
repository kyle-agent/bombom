"""Device candidate pool: add/list/price/note/remove + live price refresh. Throwaway git repo."""

import subprocess

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def gitws(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    root.mkdir()
    (root / "seed.txt").write_text("x")          # so the repo has an initial commit
    _git("init", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "tester", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    return root, db


def _client(gitws):
    root, db = gitws
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False), root


def test_add_lists_unpriced_then_price_makes_it_priced(gitws):
    client, root = _client(gitws)
    # add a real catalog device as a candidate — starts unpriced
    r = client.post("/api/candidates", json={"slug": "dell-poweredge-test1", "note": "표준 노드"})
    assert r.status_code == 200, r.text
    row = r.json()["candidate"]
    assert row["in_catalog"] and row["priced"] is False and row["note"] == "표준 노드"
    assert (root / "candidates/pool.yaml").exists()

    lst = client.get("/api/candidates").json()
    assert [c["slug"] for c in lst] == ["dell-poweredge-test1"]

    # enter a price from the candidate screen → priced, and visible immediately (live refresh)
    up = client.put("/api/candidates/dell-poweredge-test1", json={"unit_cost": 1500000})
    assert up.status_code == 200, up.text
    assert up.json()["candidate"]["priced"] is True
    assert up.json()["candidate"]["unit_cost"] == 1500000
    assert (root / "pricing/manual.yaml").exists()
    again = client.get("/api/candidates").json()[0]
    assert again["unit_cost"] == 1500000          # reflected without a restart


def test_add_unknown_device_404(gitws):
    client, root = _client(gitws)
    r = client.post("/api/candidates", json={"slug": "nope-not-real"})
    assert r.status_code == 404
    assert not (root / "candidates/pool.yaml").exists()


def test_duplicate_candidate_409(gitws):
    client, root = _client(gitws)
    client.post("/api/candidates", json={"slug": "arista-test-sw"})
    dup = client.post("/api/candidates", json={"slug": "arista-test-sw"})
    assert dup.status_code == 409


def test_update_note_only(gitws):
    client, root = _client(gitws)
    client.post("/api/candidates", json={"slug": "arista-test-sw"})
    r = client.put("/api/candidates/arista-test-sw", json={"note": "스파인"})
    assert r.status_code == 200 and r.json()["candidate"]["note"] == "스파인"


def test_update_non_candidate_404(gitws):
    client, root = _client(gitws)
    r = client.put("/api/candidates/dell-poweredge-test1", json={"unit_cost": 100})
    assert r.status_code == 404          # not in the pool


def test_remove_candidate(gitws):
    client, root = _client(gitws)
    client.post("/api/candidates", json={"slug": "arista-test-sw"})
    d = client.delete("/api/candidates/arista-test-sw")
    assert d.status_code == 200
    assert client.get("/api/candidates").json() == []
    gone = client.delete("/api/candidates/arista-test-sw")
    assert gone.status_code == 404


def test_negative_price_rejected(gitws):
    client, root = _client(gitws)
    client.post("/api/candidates", json={"slug": "arista-test-sw"})
    r = client.put("/api/candidates/arista-test-sw", json={"unit_cost": -5})
    assert r.status_code == 422          # ge=0


def test_unsafe_slug_422(gitws):
    client, root = _client(gitws)
    r = client.post("/api/candidates", json={"slug": "../evil"})
    assert r.status_code == 422


def test_candidates_page_served(gitws):
    client, root = _client(gitws)
    r = client.get("/candidates")
    assert r.status_code == 200 and "후보" in r.text
