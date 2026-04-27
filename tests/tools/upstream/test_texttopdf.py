"""Ported from upstream — except upstream PDFBox 3.0 has no
``TextToPDFTest.java``. The ``texttopdf`` CLI was historically tested only
through Apache PDFBox's example-jar smoke runs and a single integration
matcher in ``PDFBoxAppTest`` (which we already cover via our
``test_cli.py``).

We keep this module so the test directory layout matches every other
``tests/tools/upstream/`` package — the round-trip integration that
upstream's ``main`` test would exercise lives in
``tests/tools/test_texttopdf.py``.

If upstream ever adds a dedicated ``TextToPDFTest.java``, port the
JUnit cases here using the matrix in ``CLAUDE.md`` §"Test Porting
Conventions".
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text import PDFTextStripper
from pypdfbox.tools import cli


def test_round_trip_smoke(tmp_path: Path) -> None:
    """Apache PDFBox's ``PDFBoxAppTest`` smoke-runs the ``texttopdf``
    subcommand against a small fixture and asserts the output is a
    readable PDF with the original text. We mirror that here."""
    src = tmp_path / "in.txt"
    src.write_text("Apache PDFBox\n", encoding="utf-8")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(["texttopdf", "-i", str(src), "-o", str(out)])

    assert rc == 0
    assert out.is_file()
    with PDDocument.load(out) as doc:
        assert doc.get_number_of_pages() >= 1
        stripper = PDFTextStripper()
        assert "Apache PDFBox" in stripper.get_text(doc)
