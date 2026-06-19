"""BOM engine + design tests. Reuses the catalog `library` fixture (conftest) to build a
small real index, then lays out designs/pricing in tmp dirs and rolls them up."""

from pathlib import Path

import pytest

from bombom.bom import PriceBook, compute_bom
from bombom.catalog import Catalog, reindex
from bombom.design import parse_hierarchy


@pytest.fixture
def catalog(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    reindex(db_path=db, paths=library)
    return Catalog(db)


def _rack(tmp_path, rack_id, body):
    d = tmp_path / "offerings/cloud-a/regions/kr-east/zones/az1/rack-groups/row-3/racks"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rack_id}.yaml").write_text(body)
    return tmp_path / "offerings/cloud-a"


def _pricing(tmp_path, body):
    p = tmp_path / "pricing"
    p.mkdir(exist_ok=True)
    (p / "test.yaml").write_text(body)
    return p


GOOD_RACK = """\
rack_type: { slug: acme-rack42 }
role: data
placements:
  - { device: dell-poweredge-test1, position: 1, release: R25.01 }
  - { device: dell-poweredge-test1, position: 5, release: R26.07 }
  - { device: arista-test-sw, position: 40, release: R26.07 }
custom_line_items:
  - { name: "DAC 100G", qty: 4, unit_cost: 10000, release: R26.07 }
"""

PRICING = """\
entries:
  - { slug: dell-poweredge-test1, unit_cost: 1000000 }
  - { slug: arista-test-sw, unit_cost: 2000000 }
"""


def test_total_capex_matches_hand_sum(catalog, tmp_path):
    root = _rack(tmp_path, "R02", GOOD_RACK)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    # 2×1,000,000 + 1×2,000,000 + 4×10,000 = 4,040,000
    assert r.total_capex == 4_040_000
    assert not [i for i in r.issues if i.level == "error"]


def test_release_delta(catalog, tmp_path):
    root = _rack(tmp_path, "R02", GOOD_RACK)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book, release="R26.07")
    # R26.07: test1@5 (1,000,000) + arista (2,000,000) + DAC (40,000) = 3,040,000
    assert r.release_delta == 3_040_000
    assert r.by_release["R25.01"] == 1_000_000


def test_power_rollup(catalog, tmp_path):
    root = _rack(tmp_path, "R02", GOOD_RACK)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert r.power_w == 1500  # two test1 @ 750W each; arista has no power port


def test_unpriced_flagged_not_silent_zero(catalog, tmp_path):
    root = _rack(tmp_path, "R02", GOOD_RACK)
    book = PriceBook.load(_pricing(tmp_path, "entries:\n  - { slug: dell-poweredge-test1, unit_cost: 1000000 }\n"))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    names = {li.name for li in r.unpriced}
    assert "TEST-SW" in names
    # arista excluded from total; 2×1,000,000 + DAC 40,000
    assert r.total_capex == 2_040_000


def test_bad_slug_reported_and_excluded(catalog, tmp_path):
    body = """\
rack_type: { slug: acme-rack42 }
placements:
  - { device: dell-poweredge-test1, position: 1, release: R26.07 }
  - { device: does-not-exist, position: 10, release: R26.07 }
"""
    root = _rack(tmp_path, "R02", body)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert any("does-not-exist" in i.message for i in r.issues if i.level == "error")
    assert r.total_capex == 1_000_000  # only the valid device


def test_overlap_excludes_only_second(catalog, tmp_path):
    body = """\
rack_type: { slug: acme-rack42 }
placements:
  - { device: dell-poweredge-test1, position: 1, release: R26.07 }
  - { device: dell-poweredge-test1, position: 2, release: R26.07 }
"""
    root = _rack(tmp_path, "R02", body)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert any("overlap" in i.message for i in r.issues if i.level == "error")
    assert r.total_capex == 1_000_000  # first kept, overlapping second dropped


def test_exceeds_rack_height(catalog, tmp_path):
    body = """\
rack_type: { slug: acme-rack42 }
placements:
  - { device: dell-poweredge-test1, position: 42, release: R26.07 }
"""
    root = _rack(tmp_path, "R02", body)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert any("exceeds" in i.message for i in r.issues if i.level == "error")
    assert r.total_capex == 0


def test_valuation_date_picks_point_in_time(catalog, tmp_path):
    body = """\
rack_type: { slug: acme-rack42 }
placements:
  - { device: dell-poweredge-test1, position: 1, release: R26.07 }
"""
    root = _rack(tmp_path, "R02", body)
    pricing = """\
entries:
  - { slug: dell-poweredge-test1, unit_cost: 1000000, valid_from: 2025-01-01 }
  - { slug: dell-poweredge-test1, unit_cost: 800000,  valid_from: 2026-01-01 }
"""
    book = PriceBook.load(_pricing(tmp_path, pricing))
    from datetime import date
    assert compute_bom(root, catalog=catalog, pricebook=book, valuation_date=date(2025, 6, 1)).total_capex == 1_000_000
    assert compute_bom(root, catalog=catalog, pricebook=book, valuation_date=date(2026, 6, 1)).total_capex == 800_000


def test_qty_multiplier(catalog, tmp_path):
    body = """\
rack_type: { slug: acme-rack42 }
placements:
  - { device: dell-poweredge-test1, position: 1, release: R26.07, qty: 3 }
"""
    root = _rack(tmp_path, "R02", body)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert r.total_capex == 3_000_000
    assert r.power_w == 2250  # 3 × 750


def test_breakdowns_present(catalog, tmp_path):
    root = _rack(tmp_path, "R02", GOOD_RACK)
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert r.by_rack["R02"] == 4_040_000
    assert set(r.by_category) & {"server", "network", "other"}


def test_parse_hierarchy():
    h = parse_hierarchy(Path("offerings/cloud-a/regions/kr-east/zones/az1/rack-groups/row-3/racks/R02.yaml"))
    assert h == {"offering": "cloud-a", "region": "kr-east", "zone": "az1", "rack_group": "row-3"}


def test_schema_error_reported(catalog, tmp_path):
    root = _rack(tmp_path, "R02", "rack_type: { slug: acme-rack42 }\nplacements:\n  - { device: x, position: 1, release: R1, bogus: 9 }\n")
    book = PriceBook.load(_pricing(tmp_path, PRICING))
    r = compute_bom(root, catalog=catalog, pricebook=book)
    assert any(i.level == "error" for i in r.issues)
