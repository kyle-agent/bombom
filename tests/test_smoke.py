"""Whole-app smoke test: every page route and key list API must register and respond on a
minimal workspace. Guards against route-wiring regressions (a dropped decorator, a shadowed
handler) that unit tests scoped to one feature can miss."""

import subprocess

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex

_RACK = ("offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R01.yaml",
         "rack_model: { slug: acme-rack42 }\nplacements:\n"
         "  - { device: dell-poweredge-test1, position: 1, release: R26.07 }\n")


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def client(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    (root / _RACK[0]).parent.mkdir(parents=True)
    (root / _RACK[0]).write_text(_RACK[1])
    (root / "pricing").mkdir()
    (root / "pricing/test.yaml").write_text(
        "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n")
    _git("init", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "tester", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    return TestClient(create_app(root, db_path=db), raise_server_exceptions=False)


PAGE_ROUTES = ["/", "/edit", "/manage", "/candidates", "/placed", "/dashboard", "/diff", "/search"]
API_ROUTES = [
    "/api/hierarchy",
    "/api/candidates",
    "/api/candidate-fields",
    "/api/confirm",
    "/api/search?q=dell",
    "/api/dashboard?path=offerings/cloud-a",
    "/api/placed?path=offerings/cloud-a",
]


@pytest.mark.parametrize("route", PAGE_ROUTES)
def test_page_route_serves(client, route):
    r = client.get(route)
    assert r.status_code == 200, f"{route} → {r.status_code}"
    assert "text/html" in r.headers["content-type"]


@pytest.mark.parametrize("route", API_ROUTES)
def test_api_route_responds(client, route):
    r = client.get(route)
    assert r.status_code == 200, f"{route} → {r.status_code}: {r.text[:200]}"
