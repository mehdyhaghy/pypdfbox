"""Ported from
``pdfbox-tools/src/test/java/org/apache/pdfbox/tools/TestExtractText.java``
(PDFBox 3.0.x).

The ``-console`` round-trip, embedded-PDF extraction, ``-addFileName``
prefix, and ``-rotationMagic`` paths are translated into pytest below
using locally-built fixtures (no upstream binary required).
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDEmbeddedFile,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
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


def _build_pdf_bytes(label: str) -> bytes:
    return _build_pdf_bytes_with_labels([label])


def _build_pdf_bytes_with_labels(labels: list[str]) -> bytes:
    doc = PDDocument()
    try:
        for label in labels:
            page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
            stream = COSStream()
            stream.set_data(
                f"BT /F0 12 Tf 100 700 Td ({label}) Tj ET".encode("latin-1")
            )
            page.set_contents(stream)
            doc.add_page(page)
        out = BytesIO()
        doc.save(out)
        return out.getvalue()
    finally:
        doc.close()


def _build_pdf_with_embedded_files(
    path: Path,
    *,
    label: str,
    embedded: dict[str, tuple[bytes, str]],
) -> Path:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        stream = COSStream()
        stream.set_data(
            f"BT /F0 12 Tf 100 700 Td ({label}) Tj ET".encode("latin-1")
        )
        page.set_contents(stream)
        doc.add_page(page)

        names = PDDocumentNameDictionary()
        embedded_tree = PDEmbeddedFilesNameTreeNode()
        specs: dict[str, PDComplexFileSpecification] = {}
        for filename, (data, subtype) in embedded.items():
            spec = PDComplexFileSpecification()
            spec.set_file(filename)
            embedded_file = PDEmbeddedFile(doc, data)
            embedded_file.set_subtype(subtype)
            spec.set_embedded_file(embedded_file)
            specs[filename] = spec
        embedded_tree.set_names(specs)
        names.set_embedded_files(embedded_tree)
        doc.get_document_catalog().set_names(names)

        doc.save(path)
    finally:
        doc.close()
    return path


def _build_pdf_with_embedded_files_and_labels(
    path: Path,
    *,
    labels: list[str],
    embedded: dict[str, tuple[bytes, str]],
) -> Path:
    doc = PDDocument()
    try:
        for label in labels:
            page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
            stream = COSStream()
            stream.set_data(
                f"BT /F0 12 Tf 100 700 Td ({label}) Tj ET".encode("latin-1")
            )
            page.set_contents(stream)
            doc.add_page(page)

        names = PDDocumentNameDictionary()
        embedded_tree = PDEmbeddedFilesNameTreeNode()
        specs: dict[str, PDComplexFileSpecification] = {}
        for filename, (data, subtype) in embedded.items():
            spec = PDComplexFileSpecification()
            spec.set_file(filename)
            embedded_file = PDEmbeddedFile(doc, data)
            embedded_file.set_subtype(subtype)
            spec.set_embedded_file(embedded_file)
            specs[filename] = spec
        embedded_tree.set_names(specs)
        names.set_embedded_files(embedded_tree)
        doc.get_document_catalog().set_names(names)

        doc.save(path)
    finally:
        doc.close()
    return path


# upstream: testEmbeddedPDFs
def test_embedded_pdfs_extracted_to_console(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    child = _build_pdf_bytes("PDF2")
    pdf = _build_pdf_with_embedded_files(
        tmp_path / "PDF1.pdf",
        label="PDF1",
        embedded={"PDF2.pdf": (child, "application/pdf")},
    )

    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-console"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "PDF1" in out
    assert "PDF2" in out
    # Without ``-addFileName`` the file path must not appear.
    assert f"PDF file: {pdf}" not in out


# upstream: testAddFileName
def test_add_file_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    child = _build_pdf_bytes("PDF2")
    pdf = _build_pdf_with_embedded_files(
        tmp_path / "PDF1.pdf",
        label="PDF1",
        embedded={"PDF2.pdf": (child, "application/pdf")},
    )

    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-console", "-addFileName"]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "PDF1" in out
    assert "PDF2" in out
    assert f"PDF file: {pdf}" in out


def test_embedded_pdf_subtype_match_is_exact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_child = _build_pdf_bytes("PDF2")
    text_child = b"PDF3 should not be extracted"
    wrong_case_child = _build_pdf_bytes("PDF4")
    pdf = _build_pdf_with_embedded_files(
        tmp_path / "PDF1.pdf",
        label="PDF1",
        embedded={
            "PDF2.pdf": (pdf_child, "application/pdf"),
            "notes.txt": (text_child, "text/plain"),
            "case.pdf": (wrong_case_child, "Application/PDF"),
        },
    )

    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-console"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "PDF1" in out
    assert "PDF2" in out
    assert "PDF3" not in out
    assert "PDF4" not in out


def test_parent_page_range_does_not_limit_embedded_pdfs(tmp_path: Path) -> None:
    child = _build_pdf_bytes_with_labels(["Child1", "Child2"])
    pdf = _build_pdf_with_embedded_files_and_labels(
        tmp_path / "parent.pdf",
        labels=["Parent1", "Parent2"],
        embedded={"child.pdf": (child, "application/pdf")},
    )
    out = tmp_path / "out.txt"

    rc = cli.run_cli(
        [
            "extracttext",
            "-i",
            str(pdf),
            "-o",
            str(out),
            "-startPage",
            "2",
            "-endPage",
            "2",
        ]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Parent1" not in text
    assert "Parent2" in text
    assert "Child1" in text
    assert "Child2" in text


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
