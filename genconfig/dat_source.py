"""Locate and load the third-party dat reader. Kept thin so it stays swappable."""

import os
import sys

DEFAULT_SRC = "/opt/data/tools/src/GenieDatParser/src"


def load_dat(path):
    """Parse a Genie .dat file and return the parser's DatFile object."""
    src = os.environ.get("GENIE_PARSER_SRC", DEFAULT_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)
    from sections.datfile_sections import DatFile  # noqa: E402  (path set above)

    return DatFile.from_file(path)
