"""
``pypdfbox version`` — print version banner.

Mirrors upstream ``org.apache.pdfbox.tools.Version``. Upstream prints just
the PDFBox version; we additionally surface the Python interpreter version
and the (currently empty) third-party dependency list to make bug reports
self-describing.
"""
from __future__ import annotations

import argparse
import platform
import sys
from importlib import metadata


def _project_version() -> str:
    """Return the installed pypdfbox version string. Falls back to the
    placeholder ``"0.0.0+unknown"`` when the distribution is not installed
    (e.g. running directly out of a source checkout without ``pip install
    -e .``)."""
    try:
        return metadata.version("pypdfbox")
    except metadata.PackageNotFoundError:
        return "0.0.0+unknown"


def _dependency_versions() -> list[tuple[str, str]]:
    """Return ``(name, version)`` for each *runtime* dependency declared in
    pyproject.toml. As of cluster #1 the runtime dep list is empty; this
    helper still works once cryptography / others land."""
    rows: list[tuple[str, str]] = []
    try:
        dist = metadata.distribution("pypdfbox")
    except metadata.PackageNotFoundError:
        return rows
    for raw in dist.requires or []:
        # Strip any extras / version specifier — keep just the name.
        name = raw.split(";", 1)[0].strip()
        for separator in ("[", "(", "<", ">", "=", "!", "~", " "):
            if separator in name:
                name = name.split(separator, 1)[0].strip()
        if not name:
            continue
        try:
            rows.append((name, metadata.version(name)))
        except metadata.PackageNotFoundError:
            rows.append((name, "<not installed>"))
    return rows


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``version`` subparser. Takes no arguments."""
    p = subparsers.add_parser(
        "version",
        help="print pypdfbox + Python + dependency versions",
        description="Print pypdfbox version, the Python interpreter version, "
        "and the version of every declared runtime dependency.",
    )
    p.set_defaults(func=run)


def run(_args: argparse.Namespace) -> int:
    print(f"pypdfbox {_project_version()}")
    print(f"Python {sys.version.split()[0]} ({platform.python_implementation()})")
    deps = _dependency_versions()
    if deps:
        print("Dependencies:")
        for name, version in deps:
            print(f"  {name} {version}")
    else:
        print("Dependencies: (none)")
    return 0
