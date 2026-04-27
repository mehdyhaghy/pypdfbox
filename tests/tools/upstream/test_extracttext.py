"""Ported from
``pdfbox-tools/src/test/java/org/apache/pdfbox/tools/TestExtractText.java``
(PDFBox 3.0.x).

Several upstream tests exercise behavior pypdfbox's CLI does not (yet)
implement and are explicitly skipped:

* ``testEmbeddedPDFs`` / ``testAddFileName`` / the ``testPDFBoxRepeatable*``
  family — depend on extracting text out of *embedded* PDFs in a
  ``/Names → /EmbeddedFiles`` tree. pypdfbox does not yet expose an
  enumerable ``PDDocumentNameDictionary``; the ``-addFileName`` and
  basic ``-console`` semantics are still covered against a hand-built
  fixture below.
* ``testRotationMagic`` — needs the ``AngleCollector`` /
  ``FilteredTextStripper`` cluster (``-rotationMagic``), which pypdfbox
  has chosen not to port. See ``CHANGES.md``.

The two scenarios we *can* faithfully reproduce — ``-console`` round-trip
and ``-addFileName`` prefix — are translated into pytest below using a
locally built single-page fixture (no upstream binary required).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.tools import cli


def _build_pdf(path: Path, label: str) -> Path:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        stream = COSStream()
        stream.set_data(
            f"BT /F0 12 Tf 100 700 Td ({label}) Tj ET".encode("latin-1")
        )
        page.set_contents(stream)
        doc.add_page(page)
        doc.save(path)
    finally:
        doc.close()
    return path


# upstream: testEmbeddedPDFs
def test_console_extraction_smoke(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Substitute for upstream ``testEmbeddedPDFs`` — verifies the
    ``-console`` happy-path emits the page text and reports exit code 0.
    The embedded-PDF specific assertions are skipped (see module
    docstring).
    """
    pdf = _build_pdf(tmp_path / "PDF1.pdf", "PDF1")
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-console"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PDF1" in out
    # Without ``-addFileName`` the file path must not appear.
    assert f"PDF file: {pdf}" not in out


# upstream: testAddFileName
def test_add_file_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_pdf(tmp_path / "PDF1.pdf", "PDF1")
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-console", "-addFileName"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "PDF1" in out
    assert f"PDF file: {pdf}" in out


# upstream: testPDFBoxRepeatableSubcommandAddFileNameOutfile
def test_outfile_overwrite(tmp_path: Path) -> None:
    """Substitute for upstream's ``-o <outfile>`` (no ``-append``)
    scenario — second invocation overwrites, only the latest file's
    content survives."""
    pdf1 = _build_pdf(tmp_path / "first.pdf", "Hello")
    pdf2 = _build_pdf(tmp_path / "second.pdf", "World")
    out = tmp_path / "outfile.txt"

    assert cli.run_cli(
        ["extracttext", "-i", str(pdf1), "-encoding", "UTF-8",
         "-addFileName", "-o", str(out)]
    ) == 0
    assert cli.run_cli(
        ["extracttext", "-i", str(pdf2), "-encoding", "UTF-8",
         "-addFileName", "-o", str(out)]
    ) == 0

    text = out.read_text(encoding="utf-8")
    assert "World" in text
    assert f"PDF file: {pdf2}" in text
    # First run was overwritten.
    assert "Hello" not in text
    assert f"PDF file: {pdf1}" not in text


# upstream: testPDFBoxRepeatableSubcommandAddFileNameOutfileAppend
def test_outfile_append(tmp_path: Path) -> None:
    pdf1 = _build_pdf(tmp_path / "first.pdf", "Hello")
    pdf2 = _build_pdf(tmp_path / "second.pdf", "World")
    out = tmp_path / "outfile.txt"

    assert cli.run_cli(
        ["extracttext", "-i", str(pdf1), "-encoding", "UTF-8",
         "-addFileName", "-o", str(out)]
    ) == 0
    assert cli.run_cli(
        ["extracttext", "-i", str(pdf2), "-encoding", "UTF-8",
         "-addFileName", "-o", str(out), "-append"]
    ) == 0

    text = out.read_text(encoding="utf-8")
    assert "Hello" in text
    assert "World" in text
    assert f"PDF file: {pdf1}" in text
    assert f"PDF file: {pdf2}" in text


def test_rotation_magic_skipped() -> None:
    """upstream: testRotationMagic — pypdfbox does not implement
    ``-rotationMagic``; recorded here as an explicit skip."""
    pytest.skip("rotationMagic deferred — needs FilteredTextStripper port")
