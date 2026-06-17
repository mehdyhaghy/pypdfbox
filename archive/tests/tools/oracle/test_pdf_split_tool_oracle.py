"""Live Apache PDFBox parity for the ``PDFSplit`` CLI tool
(``org.apache.pdfbox.tools.PDFSplit`` vs pypdfbox's
``pypdfbox.tools.pdf_split.PDFSplit``).

PDFSplit slices one input PDF into N output files written with the
``<outputPrefix>-<n>.pdf`` naming convention (``n`` is 1-based, ascending).
The split semantics are the load-bearing parity claim:

* **default** (no ``-split`` / ``-startPage`` / ``-endPage``): one page per
  output file — a 5-page input yields ``prefix-1..prefix-5``, one page each.
* **``-split K``**: ``K`` pages per output file — a 5-page input with
  ``-split 2`` yields ``prefix-1`` (pp.1-2), ``prefix-2`` (pp.3-4),
  ``prefix-3`` (p.5): page counts ``[2, 2, 1]``.
* **``-startPage S -endPage E``** (with no explicit ``-split``): a single
  output file holding pages ``S..E`` — a 5-page input with
  ``-startPage 2 -endPage 4`` yields one file ``prefix-1`` with 3 pages.

The differential harness drives the real upstream picocli CLI through
``PdfSplitToolProbe`` (emitting the produced file stems + per-file page counts
as JSON) and compares against pypdfbox's ``PDFSplit`` CLI driven over the same
input with the same args. The input PDF is built through pypdfbox so both sides
split byte-identical bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.pdf_split import PDFSplit
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_source(path: Path, page_count: int) -> None:
    """Build a ``page_count``-page Letter PDF (one "PAGE n" line per page)."""
    doc = PDDocument()
    try:
        for i in range(page_count):
            page = PDPage(PDRectangle.LETTER)
            doc.add_page(page)
            font = PDFontFactory.create_default_font()
            cs = PDPageContentStream(doc, page)
            cs.begin_text()
            cs.set_font(font, 12)
            cs.new_line_at_offset(72, 700)
            cs.show_text(f"PAGE {i + 1}")
            cs.end_text()
            cs.close()
        doc.save(str(path))
    finally:
        doc.close()


def _page_count(path: Path) -> int:
    result = Loader.load_pdf(str(path))
    doc = PDDocument(result) if isinstance(result, COSDocument) else result
    try:
        return doc.get_number_of_pages()
    finally:
        doc.close()


def _py_split(prefix: Path, infile: Path, *args: str) -> tuple[int, list[str], list[int]]:
    """Drive pypdfbox's PDFSplit CLI; return (exit, produced stems, page counts)."""
    argv = ["-i", str(infile), "-outputPrefix", str(prefix), *args]
    rc = PDFSplit.main(argv)
    stems: list[str] = []
    pages: list[int] = []
    n = 1
    while True:
        f = prefix.parent / f"{prefix.name}-{n}.pdf"
        if not f.is_file():
            break
        stems.append(f"{prefix.name}-{n}")
        pages.append(_page_count(f))
        n += 1
    return rc, stems, pages


@pytest.mark.parametrize(
    ("label", "extra"),
    [
        ("default", []),
        ("split2", ["-split", "2"]),
        ("split3", ["-split", "3"]),
        ("startend", ["-startPage", "2", "-endPage", "4"]),
        ("startonly", ["-startPage", "3"]),
    ],
    ids=["default", "split2", "split3", "startend", "startonly"],
)
@requires_oracle
def test_pdf_split_matches_pdfbox(
    tmp_path: Path, label: str, extra: list[str]
) -> None:
    """For each split scenario the upstream PDFSplit CLI and pypdfbox's PDFSplit
    CLI must produce the same number of output files, with the same
    ``<prefix>-<n>.pdf`` naming and the same per-file page counts."""
    src = tmp_path / "src.pdf"
    _build_source(src, 5)

    java_prefix = tmp_path / "j" / "out"
    java_prefix.parent.mkdir(parents=True, exist_ok=True)
    java_raw = run_probe_text(
        "PdfSplitToolProbe", str(java_prefix), str(src), *extra
    )
    java = json.loads(java_raw)
    assert java["exitCode"] == 0, f"upstream PDFSplit failed: {java_raw}"

    py_prefix = tmp_path / "p" / "out"
    py_prefix.parent.mkdir(parents=True, exist_ok=True)
    py_rc, py_stems, py_pages = _py_split(py_prefix, src, *extra)
    assert py_rc == 0

    # Same number of output files, same 1-based naming stems.
    assert py_stems == java["files"], (
        f"[{label}] output file naming divergence:\n"
        f"  pypdfbox: {py_stems}\n  PDFBox:   {java['files']}"
    )
    # Same per-file page counts (this is the split-semantics claim).
    assert py_pages == java["pages"], (
        f"[{label}] per-file page-count divergence:\n"
        f"  pypdfbox: {py_pages}\n  PDFBox:   {java['pages']}"
    )


def test_pdf_split_default_naming_regression(tmp_path: Path) -> None:
    """Oracle-independent pin: pypdfbox's default split of a 5-page PDF produces
    five single-page files named ``out-1.pdf`` .. ``out-5.pdf``."""
    src = tmp_path / "src.pdf"
    _build_source(src, 5)
    prefix = tmp_path / "out"
    rc, stems, pages = _py_split(prefix, src)
    assert rc == 0
    assert stems == ["out-1", "out-2", "out-3", "out-4", "out-5"]
    assert pages == [1, 1, 1, 1, 1]
