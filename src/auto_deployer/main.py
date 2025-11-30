"""Entry point for the auto-deployer CLI."""

from __future__ import annotations

import sys

from .cli import run_cli


def app_main() -> None:
    exit_code = run_cli()
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    app_main()
