"""P2/P3 tests: investment-target CSV, release summary, and dashboard aggregation.
Reuses the `library` catalog fixture (conftest). No git needed (read-only over disk)."""

import pytest
from starlette.testclient import TestClient

from bombom.api import create_app
from bombom.catalog import reindex
from bombom.dashboard import build_dashboard
from bombom.report import investment_csv, investment_rows, release_summary
from bombom.workspace import Workspace

# cloud-a: R01 (R26.07 — dell+serial priced, arista unpriced) · R02 (R26.08 — dell, no serial)
_RACKS = {
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R01.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.07, meta: { serial: S1 } }\n"
        "  - { device: arista-test-sw, position: 40, release: R26.07 }\n",
    "offerings/cloud-a/regions/kr-east/zones/az1/rack-types/data/racks/R02.yaml":
        "rack_model: { slug: acme-rack42 }\nplacements:\n"
        "  - { device: dell-poweredge-test1, position: 1, release: R26.08 }\n",
}
_OVERLAYS = {
    "pricing/test.yaml": "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n",
    "categories/overlay.yaml": "categories:\n  dell-poweredge-test1: server\n",
    "meta/fields.yaml": "fields:\n  - { key: serial, label: 시리얼, type: string,"
    " required: true, applies_to: placement, scope: 'category:server' }\n",
}


@pytest.fixture
def ws_root(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    root = tmp_path / "ws"
    for sub, content in {**_RACKS, **_OVERLAYS}.items():
        p = root / sub
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return Workspace.open(root, db_path=db), root


def test_investment_rows_filters_to_release(ws_root):
    ws, root = ws_root
    rows = investment_rows(ws, root, "R26.07")
    assert {r["name"] for r in rows} == {"PowerEdge TEST1", "TEST-SW"}   # only R26.07 (R01)
    assert all(r["region"] == "kr-east" and r["rack_type"] == "data" for r in rows)
    priced = {r["name"]: r["priced"] for r in rows}
    assert priced["PowerEdge TEST1"] is True and priced["TEST-SW"] is False   # arista unpriced
    dell = next(r for r in rows if r["name"] == "PowerEdge TEST1")
    assert dell["subtotal"] == 1_000_000


def test_investment_csv_header_and_total(ws_root):
    ws, root = ws_root
    csv_text = investment_csv(investment_rows(ws, root, "R26.07"), release="R26.07")
    assert csv_text.startswith("﻿")          # Excel UTF-8 BOM
    assert "장비" in csv_text and "소계(KRW)" in csv_text
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    assert any(ln.startswith('"",') or "합계" in ln for ln in lines)
    assert "1000000" in csv_text


def test_release_summary_increment_and_cumulative(ws_root):
    ws, root = ws_root
    summary = {s["release"]: s for s in release_summary(ws, root)}
    assert summary["R26.07"]["increment_capex"] == 1_000_000      # dell only (arista unpriced)
    assert summary["R26.07"]["cumulative_capex"] == 1_000_000
    assert summary["R26.08"]["increment_capex"] == 1_000_000
    assert summary["R26.08"]["cumulative_capex"] == 2_000_000     # running total


def test_dashboard_headline_rollups_counts(ws_root):
    ws, root = ws_root
    d = build_dashboard(ws, root)
    assert d["headline_capex"] == 2_000_000                       # cumulative (two priced dells)
    assert d["counts"]["unpriced"] == 1                           # arista
    assert d["counts"]["meta_missing"] == 1                       # R02 dell missing serial
    assert d["counts"]["racks"] == 2
    rt = {r["label"]: r["capex"] for r in d["by_level"]["rack_type"]}
    assert rt.get("data") == 2_000_000
    assert {r["label"] for r in d["by_category"]} >= {"server"}
    assert len(d["release_summary"]) == 2
    assert d["top_devices"][0]["name"] == "PowerEdge TEST1"       # highest spend


def _client(ws_root):
    ws, root = ws_root
    return TestClient(create_app(root, db_path=ws.catalog.db_path), raise_server_exceptions=False)


def test_api_dashboard(ws_root):
    client = _client(ws_root)
    r = client.get("/api/dashboard?path=offerings/cloud-a")
    assert r.status_code == 200, r.text
    assert r.json()["headline_capex"] == 2_000_000


def test_api_invest_csv_attachment(ws_root):
    client = _client(ws_root)
    r = client.get("/api/report/invest.csv?release=R26.07&path=offerings/cloud-a")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    assert "합계" in r.text and "1000000" in r.text


def test_invest_csv_rejects_unsafe_release(ws_root):
    client = _client(ws_root)
    r = client.get('/api/report/invest.csv?release=x"%0d%0aSet-Cookie:evil&path=offerings')
    assert r.status_code == 400          # header-injection guard on release


def test_dashboard_route_removed(ws_root):
    # /dashboard screen consolidated into 메인(/) + 투자 리포트(/summary); API endpoint remains
    client = _client(ws_root)
    assert client.get("/dashboard").status_code == 404
    assert client.get("/api/dashboard?path=offerings/cloud-a").status_code == 200


def test_api_placed_lists_all_with_total(ws_root):
    client = _client(ws_root)
    r = client.get("/api/placed?path=offerings/cloud-a")
    assert r.status_code == 200, r.text
    body = r.json()
    # R01: dell(priced)+arista(unpriced) @R26.07, R02: dell(priced) @R26.08 → 3 rows
    assert len(body["rows"]) == 3
    assert body["total_capex"] == 2_000_000          # two priced dells
    assert body["unpriced"] == 1                      # arista
    assert set(body["releases"]) == {"R26.07", "R26.08"}


def test_api_placed_release_filter(ws_root):
    client = _client(ws_root)
    body = client.get("/api/placed?path=offerings/cloud-a&release=R26.08").json()
    assert {r["release"] for r in body["rows"]} == {"R26.08"}
    assert body["total_capex"] == 1_000_000


def test_report_html_standalone(ws_root):
    client = _client(ws_root)
    r = client.get("/api/report.html?path=offerings/cloud-a")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "/*__BOMBOM_DATA__*/" in body and "/*__END__*/" in body   # data baked in
    assert "투자 보고서" in body
    assert "headline_capex" in body and "2000000" in body            # real numbers embedded
    assert "content-disposition" not in r.headers                    # inline by default


def test_report_html_download_and_release_guard(ws_root):
    client = _client(ws_root)
    dl = client.get("/api/report.html?path=offerings/cloud-a&release=R26.07&download=1")
    assert "attachment" in dl.headers["content-disposition"]
    assert "bombom-report-R26.07.html" in dl.headers["content-disposition"]
    bad = client.get('/api/report.html?release=x"%0d%0aevil')
    assert bad.status_code == 400                                    # header-injection guard


def test_placed_csv_all_and_per_release(ws_root):
    client = _client(ws_root)
    full = client.get("/api/placed.csv?path=offerings/cloud-a")
    assert full.status_code == 200
    assert "attachment" in full.headers["content-disposition"]
    assert "placed-all.csv" in full.headers["content-disposition"]
    assert "합계" in full.text
    one = client.get("/api/placed.csv?path=offerings/cloud-a&release=R26.08")
    assert "placed-R26.08.csv" in one.headers["content-disposition"]
    bad = client.get('/api/placed.csv?release=x"%0d%0aevil')
    assert bad.status_code == 400          # release header-injection guard


def test_placed_route_removed(ws_root):
    # /placed screen consolidated; /api/placed + /api/placed.csv endpoints remain
    client = _client(ws_root)
    assert client.get("/placed").status_code == 404
    assert client.get("/api/placed?path=offerings/cloud-a").status_code == 200
