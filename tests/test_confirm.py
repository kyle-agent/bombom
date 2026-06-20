"""Confirm-workflow tests: gate → in-review → approve(tag). Runs against a throwaway git
repo so the real repo is never touched. Reuses the `library` catalog fixture (conftest)."""

import subprocess

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _count(cwd):
    return int(_git("rev-list", "--count", "HEAD", cwd=cwd).stdout.strip())


def _tags(cwd):
    return _git("tag", "--list", cwd=cwd).stdout.split()


# Three racks across two offerings:
#   cloud-a R01  — R26.07 clean (dell+serial priced; arista unpriced → warning, no required meta)
#   cloud-a R02  — R26.08 dirty (dell without required serial → error)
#   cloud-b R09  — R26.07 clean (dell+serial)  ← the "new build" subtree
_RACKS = {
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R01.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.07, meta: { serial: S1 } }\n"
        "  - { device: arista-test-sw, position: 40, release: R26.07 }\n",
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R02.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.08 }\n",
    "offerings/cloud-b/regions/kr-east/zones/az1/rack-types/data/racks/R09.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.07, meta: { serial: Sb } }\n",
}

_OVERLAYS = {
    "pricing/test.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n",
    "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n",
    "meta/fields.yaml": "fields:\n  - { key: serial, label: 시리얼, type: string,"
    " required: true, applies_to: placement, scope: 'category:server' }\n",
}


@pytest.fixture
def gitws(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    for sub, content in {**_RACKS, **_OVERLAYS}.items():
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


def test_request_clean_release_writes_manifest_and_commits(gitws):
    client, root = _client(gitws)
    before = _count(root)
    body = {"id": "R26.07", "kind": "release", "scope": {"release": "R26.07"},
            "requester": "designer@x"}
    r = client.post("/api/confirm/request", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["confirmation"]["status"] == "in-review"
    assert data["gate"]["ok"] is True
    assert (root / "confirmations/R26.07.yaml").exists()
    assert _count(root) == before + 1
    # arista has no price → a non-blocking warning is surfaced
    assert any("arista" in w["message"] for w in data["gate"]["warnings"])
    assert data["gate"]["capex"] == 2_000_000   # two dells priced 1,000,000 each


def test_request_missing_meta_blocks_no_write(gitws):
    client, root = _client(gitws)
    before = _count(root)
    body = {"id": "R26.08", "kind": "release", "scope": {"release": "R26.08"}}
    r = client.post("/api/confirm/request", json=body)
    assert r.status_code == 400, r.text
    gate = r.json()["detail"]["gate"]
    assert any("serial" in e["message"] for e in gate["errors"])
    assert not (root / "confirmations/R26.08.yaml").exists()
    assert _count(root) == before          # no commit


def test_approve_seals_with_tag(gitws):
    client, root = _client(gitws)
    client.post("/api/confirm/request",
                json={"id": "R26.07", "kind": "release", "scope": {"release": "R26.07"}})
    before = _count(root)
    r = client.post("/api/confirm/approve?id=R26.07", json={"approver": "boss@x"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["confirmation"]["status"] == "confirmed"
    assert data["tag"] == "R26.07"
    assert "R26.07" in _tags(root)
    assert _count(root) == before + 1


def test_build_kind_request_then_approve(gitws):
    client, root = _client(gitws)
    body = {"id": "cloud-b-init", "kind": "build",
            "scope": {"paths": ["offerings/cloud-b"]}}
    r = client.post("/api/confirm/request", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["gate"]["ok"] is True
    r2 = client.post("/api/confirm/approve?id=cloud-b-init", json={})
    assert r2.status_code == 200, r2.text
    assert r2.json()["confirmation"]["tag"] == "cloud-b-init"
    assert "cloud-b-init" in _tags(root)


def test_approve_unknown_is_409(gitws):
    client, root = _client(gitws)
    r = client.post("/api/confirm/approve?id=nope", json={})
    assert r.status_code == 409


def test_reapprove_blocked(gitws):
    client, root = _client(gitws)
    client.post("/api/confirm/request",
                json={"id": "R26.07", "kind": "release", "scope": {"release": "R26.07"}})
    client.post("/api/confirm/approve?id=R26.07", json={})
    again = client.post("/api/confirm/approve?id=R26.07", json={})
    assert again.status_code == 409          # already confirmed / tag immutable


def test_detail_and_list(gitws):
    client, root = _client(gitws)
    client.post("/api/confirm/request",
                json={"id": "R26.07", "kind": "release", "scope": {"release": "R26.07"}})
    d = client.get("/api/confirm/R26.07")
    assert d.status_code == 200
    gate = d.json()["gate"]
    assert len(gate["affected_racks"]) >= 1 and gate["capex"] > 0
    assert any("arista" in w["message"] for w in gate["warnings"])
    lst = client.get("/api/confirm").json()
    assert any(c["id"] == "R26.07" for c in lst)


def test_build_scope_path_traversal_blocked(gitws):
    client, root = _client(gitws)
    r = client.post("/api/confirm/request",
                    json={"id": "evil", "kind": "build", "scope": {"paths": ["../evil"]}})
    assert r.status_code in (400, 404)
    assert not (root / "confirmations/evil.yaml").exists()


def test_cross_release_error_does_not_block(gitws):
    # One rack, two releases: R26.09 is clean, R26.10 has a bad device slug. Confirming R26.09
    # must NOT be blocked by the unrelated R26.10 error (validate_rack scoping).
    client, root = _client(gitws)
    rack = root / ("offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R03.yaml")
    rack.write_text(
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.09, meta: { serial: S3 } }\n"
        "  - { device: nonexistent-device-xyz, position: 10, release: R26.10 }\n"
    )
    ok = client.post("/api/confirm/request",
                     json={"id": "R26.09", "kind": "release", "scope": {"release": "R26.09"}})
    assert ok.status_code == 200, ok.text
    assert any("R03" in p for p in ok.json()["gate"]["affected_racks"])
    bad = client.post("/api/confirm/request",
                      json={"id": "R26.10", "kind": "release", "scope": {"release": "R26.10"}})
    assert bad.status_code == 400          # the bad slug blocks its own release


def test_invalid_id_rejected(gitws):
    client, root = _client(gitws)
    r = client.post("/api/confirm/request",
                    json={"id": "../etc", "kind": "release", "scope": {"release": "R26.07"}})
    assert r.status_code == 422          # pydantic id validator
