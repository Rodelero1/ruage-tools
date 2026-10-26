"""Cross-file consistency: the hand-written economy config against the generated data.

Neither file alone can catch this class of bug. `economy.toml` names unit ids by hand; if the
dat is regenerated and an id shifts, or if somebody points a task at the base villager by
mistake, the engine would gather at the wrong rate forever and no unit test would notice.
"""

import os
import tomllib
from pathlib import Path

import pytest

# This tooling lives in its own repository (D12), so the engine's content pack - the thing these
# cross-checks are about - has to be pointed at: `RUAGE_CONFIG=/path/to/ruage/config`.
# Without it there is nothing to cross-check and the tests skip rather than pass vacuously.
CONFIG = Path(os.environ.get("RUAGE_CONFIG", Path.home() / "ruage" / "config"))
ECONOMY = CONFIG / "economy.toml"
UNITS = CONFIG / "gamedata" / "units.toml"

# Tasks whose work_rate is not a gather rate. Building and repairing use the same 0..1 field
# for something else entirely (build: 1.0, repair: 12.5 hp/s candidate).
NON_GATHER = {"build", "repair"}


def _units():
    if not UNITS.exists():
        pytest.skip(f"{UNITS} is not present: set RUAGE_CONFIG to an engine checkout with generated data")
    doc = tomllib.loads(UNITS.read_text())
    return {u["id"]: u for u in doc["unit"]}


def test_gather_variants_resolve_to_real_villager_variants():
    units = _units()
    if not ECONOMY.exists():
        pytest.skip(f"{ECONOMY} is not present: set RUAGE_CONFIG")
    variants = tomllib.loads(ECONOMY.read_text())["gather"]["variant"]

    assert variants, "the gather variant table must not be empty"
    assert 83 not in variants.values(), (
        "VMBAS (83) is the base villager and its work_rate is the BUILD task's 1.0; "
        "using it as a gather rate makes gathering 2.5x too fast"
    )

    for task, unit_id in variants.items():
        assert unit_id in units, f"{task} -> {unit_id} is not a unit in the generated data"
        unit = units[unit_id]
        assert unit["name"].startswith("VM"), (
            f"{task} -> {unit_id} ({unit['name']}) is not a villager variant"
        )
        if task in NON_GATHER:
            continue
        assert 0.0 < unit["work_rate"] < 1.0, (
            f"{task} -> {unit['name']} has work_rate {unit['work_rate']}, which is not a "
            "gather rate"
        )
        assert unit["drop_sites"], f"{task} -> {unit['name']} lists no drop site"


def _sole(units, name):
    """The one unit called `name`. 180 units are called RESERVED and 56 have no name at all, so
    a name->id dict silently picks a winner; assert uniqueness instead."""
    matches = [u for u in units.values() if u["name"] == name]
    assert len(matches) == 1, f"expected exactly one unit named {name}, got {len(matches)}"
    return matches[0]


def test_drop_sites_are_present_for_the_named_buildings():
    units = _units()
    assert _sole(units, "SMIL")["drop_sites"] == []
    lumberjack = units[123]
    assert 562 in lumberjack["drop_sites"], "the lumberjack must drop at the lumber camp (562)"
    miner = units[124]
    assert 584 in miner["drop_sites"], "the miner must drop at the mining camp (584)"
