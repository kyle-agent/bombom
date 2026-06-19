import shutil

import pytest

from bombom.catalog.index import reindex
from bombom.catalog.query import Catalog, CatalogError


def test_reindex_and_get_device(library, tmp_path):
    db = tmp_path / "idx" / "catalog.db"
    summary = reindex(db_path=db, paths=library)
    assert summary.counts["device"] == 2

    catalog = Catalog(db)
    spec = catalog.get_device_type("dell-poweredge-test1")
    assert spec is not None
    assert spec.u_height == 2
    assert spec.power_ports[0].maximum_draw == 750

    # manufacturer + bare model slug also resolves
    assert catalog.get_device_type("poweredge-test1", manufacturer="Dell") is not None


def test_idempotent_reindex(library, tmp_path):
    db = tmp_path / "catalog.db"
    first = reindex(db_path=db, paths=library)
    second = reindex(db_path=db, paths=library)
    assert first.counts == second.counts


def test_rebuild_from_scratch_reproduces(library, tmp_path):
    db = tmp_path / "a" / "catalog.db"
    reindex(db_path=db, paths=library)
    before = Catalog(db).counts()

    shutil.rmtree(db.parent)  # drop the index entirely
    reindex(db_path=db, paths=library)
    assert Catalog(db).counts() == before


def test_list_by_vendor(library, tmp_path):
    db = tmp_path / "catalog.db"
    reindex(db_path=db, paths=library)
    catalog = Catalog(db)

    dell = catalog.list_by_vendor("dell")  # case-insensitive
    assert dell and all(r["manufacturer"] == "Dell" for r in dell)
    dell_devices = catalog.list_by_vendor("Dell", kind="device")
    assert all(r["kind"] == "device" for r in dell_devices)


def test_quarantine_surfaced_in_summary(library, tmp_path):
    db = tmp_path / "catalog.db"
    summary = reindex(db_path=db, paths=library)
    assert len(summary.quarantine) == 2


def test_module_and_rack_queries(library, tmp_path):
    db = tmp_path / "catalog.db"
    reindex(db_path=db, paths=library)
    catalog = Catalog(db)
    assert catalog.get_module_type("Dell", part_number="TN-1") is not None
    assert catalog.get_rack_type("acme-rack42").u_height == 42


def test_modules_sharing_part_number_not_collapsed(library, tmp_path):
    db = tmp_path / "catalog.db"
    summary = reindex(db_path=db, paths=library)
    # Both Dell modules share part_number TN-1 but are distinct models — both must survive.
    assert summary.counts["module"] == 2
    catalog = Catalog(db)
    assert catalog.get_module_type("Dell", model="TEST-NIC").model == "TEST-NIC"
    assert catalog.get_module_type("Dell", model="TEST-NIC-VARIANT").model == "TEST-NIC-VARIANT"
    # model + part_number must be an exact match, not "first row with this part_number"
    exact = catalog.get_module_type("Dell", model="TEST-NIC-VARIANT", part_number="TN-1")
    assert exact.model == "TEST-NIC-VARIANT"


def test_missing_index_raises(tmp_path):
    with pytest.raises(CatalogError):
        Catalog(tmp_path / "nope.db").counts()
