from bombom.catalog.parse import parse_catalog
from bombom.catalog.validate import SchemaValidator


def test_parse_separates_valid_and_quarantine(library):
    validator = SchemaValidator(library.schema_dir)
    result = parse_catalog(library, validator)

    counts = result.counts()
    assert counts["device"] == 2  # Dell ok + Arista sw
    assert counts["module"] == 2  # TEST-NIC + TEST-NIC-VARIANT (share part_number)
    assert counts["rack"] == 1
    # badslug + missing u_height
    assert len(result.quarantine) == 2
    assert all(q.errors for q in result.quarantine)


def test_vendor_filter(library):
    validator = SchemaValidator(library.schema_dir)
    result = parse_catalog(library, validator, vendors=["arista"])
    assert len(result.records) == 1
    assert result.records[0].spec.manufacturer == "Arista"


def test_power_port_typed(library):
    validator = SchemaValidator(library.schema_dir)
    result = parse_catalog(library, validator, vendors=["dell"], kinds=("device",))
    dell = next(r.spec for r in result.records if r.spec.slug == "dell-poweredge-test1")
    assert dell.power_ports[0].maximum_draw == 750
    assert dell.u_height == 2
    # weight 17.63 must validate (Decimal-safe multipleOf), not get quarantined
    assert dell.weight == 17.63
