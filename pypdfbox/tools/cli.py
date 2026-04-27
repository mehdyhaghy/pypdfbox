"""
Top-level ``pypdfbox`` CLI dispatcher. Mirrors upstream's
``org.apache.pdfbox.tools.PDFBox`` (which uses PicoCLI). We use the stdlib
``argparse`` so the CLI ships zero extra dependencies.

Subcommand wiring lives in this module; each subcommand registers itself
through a ``build_parser(subparsers)`` callable, keeping the dispatcher
free of business logic.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import (
    decrypt,
    encrypt,
    extracttext,
    imagetopdf,
    info,
    merge,
    pdfdebugger,
    split,
    version,
)

# Order matters only for ``--help`` rendering; argparse dispatches by name.
_SUBCOMMANDS = (
    info,
    merge,
    split,
    version,
    decrypt,
    encrypt,
    extracttext,
    imagetopdf,
    pdfdebugger,
)


def _build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pypdfbox",
        description="Command-line tools for pypdfbox — Python-native port of "
        "Apache PDFBox.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
        required=True,
        title="commands",
    )
    for module in _SUBCOMMANDS:
        module.build_parser(subparsers)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` (default: ``sys.argv[1:]``) and dispatch to the
    chosen subcommand. Returns the subcommand's exit code."""
    parser = _build_root_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:  # pragma: no cover — argparse rejects this path
        parser.print_help()
        return 2
    try:
        return int(func(args))
    except OSError as exc:
        # I/O failure code matches upstream's PicoCLI tools (exit 4).
        print(f"{args.command}: I/O error: {exc}", flush=True)
        return 4


def main() -> None:
    """Console-script entry point. Calls ``sys.exit`` with the dispatched
    return code so shells see the subcommand's exit status."""
    sys.exit(run_cli())


if __name__ == "__main__":  # pragma: no cover — module-as-script
    main()
