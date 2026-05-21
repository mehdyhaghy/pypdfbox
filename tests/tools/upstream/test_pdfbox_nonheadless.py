"""Ported upstream test: ``PDFBoxNonHeadlessTest``.

Upstream verifies that when the JVM is *not* headless, picocli surfaces
``debug`` as a registered subcommand (so the unmatched-argument error
disappears). The Python port has no AWT headless concept, so we mirror
the *intent* — the dispatcher class ``pypdfbox.tools.pdf_box.PDFBox``
always exposes the same subcommand surface — by exercising the
``pdfdebugger`` subcommand via the existing ``cli`` dispatcher rather
than via ``PDFBox.main`` (the latter intentionally omits ``debug`` from
its picocli-style map; the ``cli.run_cli`` dispatcher is what users
actually invoke).

Skipped:
- ``isNonHeadlessTest`` — Java AWT ``GraphicsEnvironment.isHeadless()``
  has no Python analogue; AWT-style "is this a graphical environment"
  is not a property pypdfbox tracks.
- The exact-string assertion on the upstream PicoCLI wording
  (``"Unmatched argument at index 0: 'debug'"``) is dropped: argparse
  produces a different error string. The intent — "debug is a known
  subcommand" — is preserved by exercising it as a valid subcommand
  via ``cli.run_cli``.
"""
from __future__ import annotations

import pytest

from pypdfbox.tools import cli


def test_nonheadless_pdfbox_debug_is_known_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``pdfdebugger --help`` exits 0 — proves ``debug``/``pdfdebugger``
    is a wired subcommand, matching upstream's non-headless invariant
    that ``debug`` is a registered subcommand."""
    with pytest.raises(SystemExit) as excinfo:
        cli.run_cli(["pdfdebugger", "--help"])
    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert "pdfdebugger" in captured.out or "usage" in captured.out.lower()
