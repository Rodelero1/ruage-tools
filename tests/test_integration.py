"""Integration: generate the real config from the installed dat. Skipped when absent."""

import os
import tomllib

import pytest

# The user's own install, never committed (D8) and never shipped: point `RUAGE_DAT` at it.
DAT = os.environ.get(
    "RUAGE_DAT",
    "/opt/data/workspace/Age2HD/Age2HD/resources/_common/dat/empires2_x2_p1.dat",
)

pytestmark = pytest.mark.skipif(not os.path.exists(DAT), reason="game dat not present")


def test_generates_full_config_from_the_real_dat(tmp_path):
    from genconfig.build import build_config

    meta = build_config(DAT, tmp_path)

    for name in ("units", "techs", "effects", "civs"):
        path = tmp_path / "gamedata" / f"{name}.toml"
        assert path.exists(), name
        assert path.read_text().startswith("# GENERATED FILE"), name

    units = tomllib.loads((tmp_path / "gamedata" / "units.toml").read_text())
    assert len(units["unit"]) == 1166
    by_id = {u["id"]: u for u in units["unit"]}
    knight = by_id[38]
    assert knight["hp"] == 100 and knight["speed"] == 1.35
    assert knight["armours"] == [[4, 2], [8, 0], [3, 2]]

    effects = tomllib.loads((tmp_path / "gamedata" / "effects.toml").read_text())
    dba = {e["id"]: e for e in effects["effect"]}[195]
    assert dba["commands"] == [[5, 218, -1, 13, 1.2], [5, 123, -1, 13, 1.2]]

    manifest = tomllib.loads((tmp_path / "MANIFEST.toml").read_text())
    assert manifest["counts"]["units"] == 1166
    assert manifest["counts"]["civs"] == 32
    assert meta["source_sha256"] == manifest["source_sha256"]


def test_cli_writes_config_and_reports_counts(tmp_path, capsys):
    from genconfig.cli import main

    assert main([DAT, str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "units=1166" in out
    assert (tmp_path / "MANIFEST.toml").exists()
