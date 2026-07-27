"""Allow ``python -m figuresmith.models`` as an alias for the model CLI."""

from figuresmith.models.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
