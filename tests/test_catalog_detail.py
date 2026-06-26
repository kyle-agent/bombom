"""Device detail endpoint (full NetBox spec + summary) and candidate 부가정보 field CRUD."""

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
    (root / "seed.txt").write_text("x")
    _git("init", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "tester", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    return root, db


def _client(gitws):
    root, db = gitws
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False), root


def test_device_detail_full_spec_and_summary(gitws):
    client, _ = _client(gitws)
    r = client.get("/api/catalog/device/dell-poweredge-test1")
    assert r.status_code == 200, r.text
    d = r.json()
    # physical pulled straight from the synced spec
    assert d["u_height"] == 2 and d["is_full_depth"] is True
    assert d["weight"] == 17.63 and d["weight_unit"] == "kg"
    # components are exposed in full
    assert d["components"]["power_ports"][0]["maximum_draw"] == 750
    assert d["components"]["interfaces"][0]["type"] == "1000base-t"
    # derived summary for the lighter placement/tag views
    assert d["summary"]["max_power_w"] == 750
    assert {"type": "1000base-t", "count": 1} in d["summary"]["port_summary"]
    assert d["summary"]["counts"]["interfaces"] == 1


def test_device_detail_404(gitws):
    client, _ = _client(gitws)
    assert client.get("/api/catalog/device/nope-nope-nope").status_code == 404


def test_candidate_field_crud_round_trip(gitws):
    client, _ = _client(gitws)
    # none defined yet
    assert client.get("/api/meta/fields?applies_to=candidate").json() == []
    # add a candidate 부가정보 field
    r = client.post("/api/meta/fields", json={
        "key": "lead_time_weeks", "label": "리드타임(주)", "type": "int",
        "required": True, "applies_to": "candidate"})
    assert r.status_code == 200, r.text
    keys = [f["key"] for f in r.json()["fields"]]
    assert "lead_time_weeks" in keys
    # it now drives the candidate-fields endpoint live (ws.fields reloaded)
    cf = client.get("/api/candidate-fields").json()
    assert any(f["key"] == "lead_time_weeks" and f["required"] for f in cf)
    # duplicate rejected
    assert client.post("/api/meta/fields", json={
        "key": "lead_time_weeks", "applies_to": "candidate"}).status_code == 409
    # bad type rejected
    assert client.post("/api/meta/fields", json={
        "key": "x", "type": "bogus", "applies_to": "candidate"}).status_code == 422
    # remove it
    assert client.delete("/api/meta/fields/lead_time_weeks").status_code == 200
    assert client.get("/api/candidate-fields").json() == []


def test_candidate_field_delete_404(gitws):
    client, _ = _client(gitws)
    assert client.delete("/api/meta/fields/ghost").status_code == 404
