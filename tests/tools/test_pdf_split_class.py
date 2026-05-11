"""Hand-written tests for :class:`pypdfbox.tools.pdf_split.PDFSplit`."""
from __future__ import annotations

from pathlib import Path

from pypdfbox.tools.pdf_split import PDFSplit


def test_pdf_split_construct() -> None:
    s = PDFSplit()
    assert s.split == -1
    assert s.start_page == -1
    assert s.end_page == -1
    assert s.output_prefix is None


def test_pdf_split_call_missing_infile() -> None:
    s = PDFSplit()
    try:
        s.call()
    except OSError as exc:
        assert "infile" in str(exc)


def test_pdf_split_main_parses(tmp_path: Path) -> None:
    rc = PDFSplit.main(["-i", str(tmp_path / "missing.pdf"), "-split", "2"])
    assert rc == 4  # OSError → exit code 4 via the OSError handler
