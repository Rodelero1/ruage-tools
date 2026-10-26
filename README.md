# ruage-tools — the importer

The content-pack generator for [ruage](https://github.com/Rodelero1/ruage), a from-scratch
deterministic reimplementation of Age of Empires II HD 5.7.

This repository is where **every Age of Empires II-specific fact lives** (D17's layering rule): the
`.dat` format, packed attack values, resource ids, effect kinds, the dat's numbering and the
translation of all of it into the engine's own schema. The engine never reads a `.dat`; it reads the
TOML this writes.

It is **GPL-3.0-or-later**, because it imports the GPL-3.0 [`GenieDatParser`][genie] to read the
format. That is exactly why it is not in the engine's repository (D12): the engine stays
MIT/Apache-2.0 while it reads TOML, and linking a GPL reader into it would be a deliberate licence
change rather than an accident of layout.

**No game data is ever committed here** (D8): not the `.dat`, not the generated TOML, not sprites.
The tool reads the user's own legally purchased install, in place, and writes the pack next to it.

## What it does

```bash
# writes <engine>/config/gamedata/{units,techs,effects,civs}.toml + MANIFEST.toml
uv run python -m genconfig /path/to/Age2HD/resources/_common/dat/empires2_x2_p1.dat \
                           /path/to/ruage/config
```

The generated files are outputs, never hand-edited. Anything a human needs to change goes in the
engine's `config/overrides.toml`, which survives regeneration.

| Module | Role |
|---|---|
| `genconfig/dat_source.py` | the only module that touches `GenieDatParser` |
| `genconfig/records.py` | dat object → plain record (a stub can stand in) |
| `genconfig/emit.py` | record → TOML formatting, no I/O |
| `genconfig/build.py` | orchestration: read, convert, write, hash |
| `prior_art/watch.py` | upstream watch for the projects we learn from (no code borrowed) |

## Tests

The suite is the project's rule (D7): every piece of shipped tooling was written after a test that
was watched failing. Two of the tests need a real checkout or install and skip without them:

```bash
# unit tests only: no install, no engine checkout needed
uv run --with pytest pytest -q

# cross-file checks against the engine's content pack
RUAGE_CONFIG=/path/to/ruage/config uv run --with pytest pytest -q

# the full generator run against a real install
RUAGE_DAT=/path/to/Age2HD/resources/_common/dat/empires2_x2_p1.dat \
RUAGE_CONFIG=/path/to/ruage/config uv run --with pytest pytest -q
```

`pytest` is not a declared dependency (the tooling must not pull a test runner into an engine
checkout), hence `--with pytest`.

## Licensing

- **This repository**: GPL-3.0-or-later (`LICENSE`), from [GenieDatParser][genie].
- **What it produces**: TOML derived from the user's own data. It is not distributed here.
- **The engine**: MIT OR Apache-2.0. Its licence never reaches this one, and vice versa; the
  boundary is the TOML files, not a feeling (D12/D13).

[genie]: https://github.com/OpenAgeCP/GenieDatParser
