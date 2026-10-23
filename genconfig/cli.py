"""Command line entry point: python -m genconfig <dat> <out_dir>."""

import sys

from .build import build_config


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: python -m genconfig <dat_path> <out_dir>", file=sys.stderr)
        return 2

    dat_path, out_dir = argv
    meta = build_config(dat_path, out_dir)
    counts = meta["counts"]
    print(
        f"units={counts['units']} techs={counts['techs']} "
        f"effects={counts['effects']} civs={counts['civs']}"
    )
    print(f"source_sha256={meta['source_sha256']}")
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
