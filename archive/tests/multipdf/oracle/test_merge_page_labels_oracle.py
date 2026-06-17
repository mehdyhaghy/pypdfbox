"""Live PDFBox differential parity for ``PDFMergerUtility`` page-label merge
(``pypdfbox.multipdf.pdf_merger_utility._merge_page_labels``).

The companion ``test_merge_oracle.py`` pins the merged AcroForm / outline /
named-destination structure; ``test_merge_split_oracle.py`` pins page count and
geometry. Neither exercises ``/PageLabels`` merging. This module fills that gap.

``PDFMergerUtility`` concatenates the source ``/PageLabels`` number trees: each
source range key is re-based by the *running destination page count* so the
merged sequence reads as one continuous document. A merge that forgot the offset
would restart the second document's labels at its own page-0 key (e.g. roman ``i``
landing on page 3 of the merged file), and a merge that dropped labels entirely
would fall back to bare decimals. Both regressions surface as a per-page label
divergence here.

The inputs are built through pypdfbox with ``/PageLabels`` written directly via
COS so the two sources are byte-identical on both sides of the comparison. The
Java side runs ``MergePageLabelsProbe`` (``PDFMergerUtility.mergeDocuments`` then
reload + ``PDPageLabels.getLabelsByPageIndices``); the pypdfbox side runs the
same merge through ``PDFMergerUtility.merge_documents`` and reads the same labels
back. Both merged outputs must also pass ``qpdf --check``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_NUMS = COSName.get_pdf_name("Nums")
_S = COSName.get_pdf_name("S")
_P = COSName.get_pdf_name("P")
_ST = COSName.get_pdf_name("St")


# ----------------------------------------------------------------- builders


def _label_range(style: str, prefix: str | None = None, start: int | None = None):
    """A ``/PageLabels`` range dictionary: ``{ /S <style> [/P prefix] [/St n] }``."""
    d = COSDictionary()
    d.set_item(_S, COSName.get_pdf_name(style))
    if prefix is not None:
        d.set_string(_P, prefix)
    if start is not None:
        d.set_item(_ST, COSInteger.get(start))
    return d


def _set_page_labels(doc: PDDocument, ranges: list[tuple[int, COSDictionary]]) -> None:
    """Write a flat ``/Nums`` page-label tree into ``doc``'s catalog."""
    nums = COSArray()
    for start_page, range_dict in ranges:
        nums.add(COSInteger.get(start_page))
        nums.add(range_dict)
    labels = COSDictionary()
    labels.set_item(_NUMS, nums)
    doc.get_document_catalog().get_cos_object().set_item(_PAGE_LABELS, labels)


def _blank_pages(doc: PDDocument, count: int) -> None:
    for _ in range(count):
        doc.add_page(PDPage(PDRectangle.LETTER))


def _build_source_set(out_dir: Path) -> list[Path]:
    """Two controlled source PDFs, each carrying ``/PageLabels``:

    * ``a.pdf`` — 3 pages. Range[0] roman-lower (``i, ii, iii``).
    * ``b.pdf`` — 2 pages. Range[0] decimal with prefix ``A-`` starting at 5
      (``A-5, A-6``).

    Expected merged labels (PDFBox re-bases b's keys by a's page count = 3):
      page 0 ``i``, 1 ``ii``, 2 ``iii``, 3 ``A-5``, 4 ``A-6``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    a = out_dir / "a.pdf"
    doc = PDDocument()
    _blank_pages(doc, 3)
    _set_page_labels(doc, [(0, _label_range("r"))])
    doc.save(str(a))
    doc.close()

    b = out_dir / "b.pdf"
    doc = PDDocument()
    _blank_pages(doc, 2)
    _set_page_labels(doc, [(0, _label_range("D", prefix="A-", start=5))])
    doc.save(str(b))
    doc.close()

    return [a, b]


# ------------------------------------------------------------- fact readers


def _qpdf_check(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _unescape(s: str) -> str:
    return (
        s.replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def _parse_probe(text: str) -> tuple[int, list[str]]:
    """Parse ``MergePageLabelsProbe`` stdout into ``(page_count, labels)``."""
    pages = 0
    labels: list[str] = []
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "pages":
            pages = int(rest)
        elif head == "label":
            _idx, _, body = rest.partition(" ")
            labels.append(_unescape(body))
    return pages, labels


def _merge_py(sources: list[Path], dest: Path) -> None:
    merger = PDFMergerUtility()
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _read_py_labels(path: Path) -> tuple[int, list[str]]:
    """Reload a pypdfbox-merged document and read its per-page labels."""
    doc = PDDocument.load(path)
    try:
        n = doc.get_number_of_pages()
        labels = doc.get_document_catalog().get_page_labels()
        if labels is None:
            return n, [""] * n
        computed = labels.get_labels_by_page_indices()
        out = [computed[i] if i < len(computed) else "" for i in range(n)]
        return n, out
    finally:
        doc.close()


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
def test_merge_page_labels_match_pdfbox(tmp_path: Path) -> None:
    """Merging two ``/PageLabels``-carrying sources must produce the same
    per-page label sequence in PDFBox and pypdfbox: the second source's range
    keys are re-based by the destination page count, so the merged labels read
    as one continuous run (``i, ii, iii, A-5, A-6``).
    """
    sources = _build_source_set(tmp_path / "src")

    java_out = tmp_path / "java_merged.pdf"
    java_pages, java_labels = _parse_probe(
        run_probe_text(
            "MergePageLabelsProbe", str(java_out), *[str(s) for s in sources]
        )
    )

    py_out = tmp_path / "py_merged.pdf"
    _merge_py(sources, py_out)
    py_pages, py_labels = _read_py_labels(py_out)

    java_rc, java_log = _qpdf_check(java_out)
    py_rc, py_log = _qpdf_check(py_out)
    assert java_rc <= 3, f"Java merge failed qpdf --check (rc={java_rc}):\n{java_log}"
    assert py_rc <= 3, f"pypdfbox merge failed qpdf --check (rc={py_rc}):\n{py_log}"

    assert py_pages == java_pages == 5, (
        f"merged page count: pypdfbox {py_pages} vs PDFBox {java_pages}"
    )
    assert py_labels == java_labels, (
        f"merged page-label divergence:\n"
        f"  pypdfbox: {py_labels}\n  PDFBox:   {java_labels}"
    )
    # Pin the expected re-based sequence so the test is self-documenting.
    assert py_labels == ["i", "ii", "iii", "A-5", "A-6"]


@requires_oracle
@_requires_qpdf
def test_merge_page_labels_dest_without_labels_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """When the first (destination) source has no ``/PageLabels`` but the second
    does, PDFBox creates a fresh tree and inserts the second's range at the
    re-based key (destination page count). The destination pages fall back to
    bare decimals. pypdfbox must match.
    """
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    a = src / "a.pdf"
    doc = PDDocument()
    _blank_pages(doc, 2)  # no /PageLabels
    doc.save(str(a))
    doc.close()

    b = src / "b.pdf"
    doc = PDDocument()
    _blank_pages(doc, 2)
    _set_page_labels(doc, [(0, _label_range("R"))])  # roman-upper: I, II
    doc.save(str(b))
    doc.close()

    sources = [a, b]

    java_out = tmp_path / "java.pdf"
    java_pages, java_labels = _parse_probe(
        run_probe_text("MergePageLabelsProbe", str(java_out), str(a), str(b))
    )

    py_out = tmp_path / "py.pdf"
    _merge_py(sources, py_out)
    py_pages, py_labels = _read_py_labels(py_out)

    py_rc, py_log = _qpdf_check(py_out)
    assert py_rc <= 3, f"pypdfbox merge failed qpdf (rc={py_rc}):\n{py_log}"

    assert py_pages == java_pages == 4
    assert py_labels == java_labels, (
        f"merged page-label divergence:\n"
        f"  pypdfbox: {py_labels}\n  PDFBox:   {java_labels}"
    )
