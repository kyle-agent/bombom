"""Test fixtures: a tiny library built from real upstream schema + handwritten specs.

We copy the real schema (six small JSON files from the submodule) so validation is exercised
against the genuine upstream schema, and drop a handful of valid/invalid specs into temp
type directories.
"""

from __future__ import annotations

import shutil

import pytest

from bombom.catalog.paths import CatalogPaths

_REAL = CatalogPaths.default()

VALID_DEVICE = """\
manufacturer: Dell
model: PowerEdge TEST1
slug: dell-poweredge-test1
u_height: 2
is_full_depth: true
weight: 17.63
weight_unit: kg
power-ports:
  - name: PSU1
    type: iec-60320-c14
    maximum_draw: 750
interfaces:
  - name: eth0
    type: 1000base-t
"""

# Invalid: slug violates the schema pattern ^[-a-z0-9_]+$ (spaces, uppercase, '!').
INVALID_DEVICE_BADSLUG = """\
manufacturer: Dell
model: Bad Slug
slug: Dell Bad Slug!
u_height: 1
is_full_depth: true
"""

# Invalid: missing required u_height.
INVALID_DEVICE_MISSING = """\
manufacturer: Dell
model: No Height
slug: dell-no-height
is_full_depth: true
"""

VALID_DEVICE_ARISTA = """\
manufacturer: Arista
model: TEST-SW
slug: arista-test-sw
u_height: 1
is_full_depth: false
"""

VALID_MODULE = """\
manufacturer: Dell
model: TEST-NIC
part_number: TN-1
interfaces:
  - name: p1
    type: 10gbase-x-sfpp
"""

# Distinct module that shares Dell's part_number TN-1 (different model) — must NOT collapse.
VALID_MODULE_SHARED_PN = """\
manufacturer: Dell
model: TEST-NIC-VARIANT
part_number: TN-1
interfaces:
  - name: p1
    type: 10gbase-x-sfpp
"""

VALID_RACK = """\
manufacturer: ACME
model: RACK42
slug: acme-rack42
form_factor: 4-post-cabinet
width: 19
u_height: 42
starting_unit: 1
"""


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    shutil.copytree(_REAL.schema_dir, lib / "schema")

    def write(kind_dir: str, vendor: str, name: str, content: str) -> None:
        target = lib / kind_dir / vendor
        target.mkdir(parents=True, exist_ok=True)
        (target / name).write_text(content)

    write("device-types", "Dell", "ok.yaml", VALID_DEVICE)
    write("device-types", "Dell", "badslug.yaml", INVALID_DEVICE_BADSLUG)
    write("device-types", "Dell", "missing.yaml", INVALID_DEVICE_MISSING)
    write("device-types", "Arista", "sw.yaml", VALID_DEVICE_ARISTA)
    write("module-types", "Dell", "nic.yaml", VALID_MODULE)
    write("module-types", "Dell", "nic-variant.yaml", VALID_MODULE_SHARED_PN)
    write("rack-types", "ACME", "rack.yaml", VALID_RACK)

    return CatalogPaths(lib)
