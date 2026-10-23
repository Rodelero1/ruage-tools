"""Allow `python -m genconfig <dat> <out>`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
