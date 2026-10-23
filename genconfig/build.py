"""Build config/gamedata/*.toml from a dat file.

Pure orchestration: records -> render -> write -> manifest. No formatting logic here;
that lives in emit.py, and record extraction in records.py, both unit-tested.
"""

import datetime
import hashlib
import os

from . import emit, records
from .dat_source import load_dat

KINDS = ("units", "techs", "effects", "civs")


def build_config(dat_path, out_dir, generated=None):
    """Generate the four gamedata files plus MANIFEST.toml. Returns the manifest meta."""
    with open(dat_path, "rb") as fh:
        raw = fh.read()

    meta = {
        "source": os.path.basename(dat_path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "generated": generated or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    dat = load_dat(dat_path)
    civ = dat.civilizations[1]  # civ 0 is Gaia

    unit_recs = [r for r in (records.unit_record(u) for u in civ.units) if r]
    tech_recs = [records.tech_record(i, t) for i, t in enumerate(dat.techs)]
    effect_recs = [records.effect_record(i, e) for i, e in enumerate(dat.tech_effects)]
    civ_recs = [records.civ_record(i, c) for i, c in enumerate(dat.civilizations)]

    payloads = {
        "units": emit.render_units(
            unit_recs,
            {**meta, "civ": 1, "civ_name": records.dname(getattr(civ, "_name_aoe2_swgb", None))},
        ),
        "techs": emit.render_techs(tech_recs, meta),
        "effects": emit.render_effects(effect_recs, meta),
        "civs": emit.render_civs(civ_recs, meta),
    }

    gamedata = os.path.join(out_dir, "gamedata")
    os.makedirs(gamedata, exist_ok=True)

    files = {}
    for kind in KINDS:
        text = payloads[kind]
        path = os.path.join(gamedata, f"{kind}.toml")
        with open(path, "w") as fh:
            fh.write(text)
        blob = text.encode("utf-8")
        files[kind] = {
            "path": f"gamedata/{kind}.toml",
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }

    counts = {
        "units": len(unit_recs),
        "techs": len(tech_recs),
        "effects": len(effect_recs),
        "civs": len(civ_recs),
    }
    with open(os.path.join(out_dir, "MANIFEST.toml"), "w") as fh:
        fh.write(emit.render_manifest(meta, counts, files))

    meta["counts"] = counts
    return meta
