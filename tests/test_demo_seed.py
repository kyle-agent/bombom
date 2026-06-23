"""The demo seeder must produce a workspace that loads — so `python scripts/demo.py` keeps
working as a local-testing entry point and doesn't rot when the data model changes."""

import importlib.util
from pathlib import Path

import pytest

from bombom.design import load_racks
from bombom.release import list_tags

_DEMO = Path(__file__).resolve().parent.parent / "scripts" / "demo.py"


def _load_seeder():
    spec = importlib.util.spec_from_file_location("demo_seed", _DEMO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def seeded(tmp_path):
    target = tmp_path / "ws"
    _load_seeder().seed(target)
    return target


def test_seed_loads_expected_racks(seeded):
    res = load_racks(seeded)
    assert {r.rack_id for r in res.racks} == {"R01", "R02", "R03", "G01", "R10", "N01"}
    assert res.issues == []  # loader-level (parse/schema) issues, not design validation


def test_seed_tags_two_releases(seeded):
    # order-insensitive: list_tags sorts by -creatordate, so two tags created in the same run
    # tiebreak unpredictably depending on whether they cross a clock-second boundary.
    assert sorted(list_tags(seeded)) == ["R25.01", "R26.07"]


def test_seed_leaves_working_edit(seeded):
    """WORKING differs from the R26.07 tag — keeps /diff non-empty for the demo."""
    import subprocess

    out = subprocess.run(["git", "status", "--porcelain"], cwd=seeded,
                         capture_output=True, text=True).stdout
    assert out.strip(), "expected an uncommitted working edit"


def test_seed_is_idempotent(tmp_path):
    mod = _load_seeder()
    target = tmp_path / "ws"
    mod.seed(target)
    mod.seed(target)  # second run wipes + rebuilds, must not raise
    assert sorted(list_tags(target)) == ["R25.01", "R26.07"]
