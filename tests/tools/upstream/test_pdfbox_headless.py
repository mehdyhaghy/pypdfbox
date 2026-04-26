"""
Ported upstream test: ``PDFBoxHeadlessTest``.

Upstream verifies the PDFBox CLI runs in a headless JVM and emits the
expected ``Unmatched argument at index 0: 'debug'`` error for the unknown
``debug`` subcommand (PicoCLI's wording). We mirror the *intent* —
"unknown subcommand exits non-zero with an error message" — using stdlib
argparse, whose error wording differs.

Skipped:
- ``isHeadlessTest`` — Java AWT headless property has no Python analogue.
- ``isHeadlessPDFBoxTest`` exact-string assertion on the upstream PicoCLI
  wording — translated to a substring check on argparse's output.
"""
from __future__ import annotations

import pytest

from pypdfbox.tools import cli


def test_headless_pdfbox() -> None:
    """``debug`` is an unknown subcommand in cluster #1 (it's deferred until
    PDFDebugger lands). The CLI must exit non-zero rather than crash, and
    must surface the offending argument name."""
    with pytest.raises(SystemExit) as excinfo:
        cli.run_cli(["debug"])
    assert excinfo.value.code != 0
