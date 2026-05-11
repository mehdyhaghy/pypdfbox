"""Hand-written tests for :class:`pypdfbox.tools.pdf_merger.PDFMerger`."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.tools.pdf_merger import PDFMerger


def test_pdf_merger_construct() -> None:
    m = PDFMerger()
    assert m.infiles == []
    assert m.outfile is None


def test_pdf_merger_call_requires_outfile(tmp_path: Path) -> None:
    m = PDFMerger()
    m.infiles = [tmp_path / "missing.pdf"]
    assert m.call() == 4  # OSError → exit code 4


def test_pdf_merger_main_parses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Inputs are absent so call() returns 4 — we just check argv plumbing.
    rc = PDFMerger.main([
        "-i", str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf"),
        "-o", str(tmp_path / "out.pdf"),
    ])
    assert rc == 4
