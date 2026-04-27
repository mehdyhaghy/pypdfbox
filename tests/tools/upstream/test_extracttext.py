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

The ``-console`` round-trip, ``-addFileName`` prefix, and
``-rotationMagic`` paths are translated into pytest below using
locally-built fixtures (no upstream binary required).
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


def _build_mixed_rotation_pdf(path: Path) -> Path:
    """Single-page PDF carrying ``Horizontal Text`` at 0 degrees and
    ``Vertical Text`` at 90 degrees, mirroring the upstream
    ``AngledExample.pdf`` fixture (which we cannot ship).
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        stream = COSStream()
        # Two text objects: one upright, one rotated 90 degrees.
        body = (
            b"BT /F0 12 Tf 1 0 0 1 100 700 Tm (Horizontal Text) Tj ET\n"
            b"BT /F0 12 Tf 0 1 -1 0 200 500 Tm (Vertical Text) Tj ET\n"
        )
        stream.set_data(body)
        page.set_contents(stream)
        doc.add_page(page)
        doc.save(path)
    finally:
        doc.close()
    return path


# upstream: testRotationMagic
def test_rotation_magic(tmp_path: Path) -> None:
    """``-rotationMagic`` should pull both upright and rotated text out of
    a page that mixes orientations. Mirrors upstream's ``testRotationMagic``
    using a hand-built fixture in place of ``AngledExample.pdf``.
    """
    pdf = _build_mixed_rotation_pdf(tmp_path / "angled.pdf")
    out = tmp_path / "outfile.txt"
    rc = cli.run_cli(
        ["extracttext", "-rotationMagic", "-i", str(pdf), "-o", str(out)]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Horizontal Text" in text
    assert "Vertical Text" in text
