import yaml

from bombom.catalog._yaml import DecimalSafeLoader
from bombom.catalog.validate import SchemaValidator


def _load(paths, kind, vendor, name):
    # Mirror the real parse path: Decimal-safe load so multipleOf validates exactly.
    return yaml.load((paths.types_dir(kind) / vendor / name).read_text(), Loader=DecimalSafeLoader)


def test_valid_device_passes(library):
    validator = SchemaValidator(library.schema_dir)
    data = _load(library, "device", "Dell", "ok.yaml")
    assert validator.errors("device", data) == []


def test_bad_slug_fails(library):
    validator = SchemaValidator(library.schema_dir)
    data = _load(library, "device", "Dell", "badslug.yaml")
    assert validator.errors("device", data)  # non-empty


def test_missing_required_fails(library):
    validator = SchemaValidator(library.schema_dir)
    data = _load(library, "device", "Dell", "missing.yaml")
    errors = validator.errors("device", data)
    assert any("u_height" in e for e in errors)


def test_module_and_rack_valid(library):
    validator = SchemaValidator(library.schema_dir)
    assert validator.errors("module", _load(library, "module", "Dell", "nic.yaml")) == []
    assert validator.errors("rack", _load(library, "rack", "ACME", "rack.yaml")) == []
