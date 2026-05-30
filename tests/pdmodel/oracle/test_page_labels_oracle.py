"""Live PDFBox differential parity for PAGE LABELS
(``pypdfbox.pdmodel.PDPageLabels`` / ``PDPageLabelRange``).

Builds a multi-range ``/PageLabels`` number tree on the catalog and compares
pypdfbox's per-page label string against Apache PDFBox's
``PDPageLabels.getLabelsByPageIndices()`` output, via the ``PageLabelsProbe``
Java oracle.

The fixture deliberately exercises every numbering style and the awkward
edges that distinguish a correct implementation from a naive one:

* **range @0** — ``/S r`` (lower Roman), no ``/St`` → ``i, ii, iii``.
* **range @3** — ``/S R`` (upper Roman) with ``/St 4`` → ``IV, V, VI`` (start
  offset must shift the rendered numeral, not the page index).
* **range @6** — ``/S A`` (upper letters) with ``/St 24`` → ``X, Y, Z, AA,
  BB`` across the A..Z → AA wraparound (PDF 32000-1 Table 159 doubling).
* **range @11** — ``/S a`` (lower letters) with ``/St 1`` → ``a, b``.
* **range @13** — ``/S D`` (decimal) with ``/P 'A-'`` prefix and ``/St 1`` →
  ``A-1, A-2`` (prefix + decimal, the classic appendix labelling).
* **range @15** — no ``/S`` at all, only ``/P 'cover'`` → prefix-only label
  ``cover`` repeated (legal per spec; PDFBox emits just the prefix).

Total 17 pages so each range has at least two pages and the letter range
crosses the Z→AA boundary. Each page reduces to ``<index>\\t<label>`` so the
two languages compare byte-for-byte.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N_PAGES = 17


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _range(
    style: str | None = None,
    prefix: str | None = None,
    start: int | None = None,
) -> COSDictionary:
    d = COSDictionary()
    if style is not None:
        d.set_item(_name("S"), _name(style))
    if prefix is not None:
        d.set_item(_name("P"), COSString(prefix))
    if start is not None:
        d.set_item(_name("St"), _i(start))
    return d


def _build_pdf(path: str) -> None:
    """Write a 17-page PDF with a multi-range /PageLabels number tree."""
    doc = PDDocument()
    try:
        for _ in range(_N_PAGES):
            doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()

        nums = COSArray()
        # @0  lower roman: i, ii, iii
        nums.add(_i(0))
        nums.add(_range(style="r"))
        # @3  upper roman, start 4: IV, V, VI
        nums.add(_i(3))
        nums.add(_range(style="R", start=4))
        # @6  upper letters, start 24: X, Y, Z, AA, BB (wraparound)
        nums.add(_i(6))
        nums.add(_range(style="A", start=24))
        # @11 lower letters: a, b
        nums.add(_i(11))
        nums.add(_range(style="a"))
        # @13 decimal with prefix "A-": A-1, A-2
        nums.add(_i(13))
        nums.add(_range(style="D", prefix="A-", start=1))
        # @15 prefix-only (no /S): "cover", "cover"
        nums.add(_i(15))
        nums.add(_range(prefix="cover"))

        page_labels = COSDictionary()
        page_labels.set_item(_name("Nums"), nums)
        catalog.set_item(_name("PageLabels"), page_labels)

        doc.save(path)
    finally:
        doc.close()


def _dump(doc: PDDocument) -> str:
    """Reproduce ``PageLabelsProbe`` in pypdfbox terms."""
    labels = doc.get_document_catalog().get_page_labels()
    if labels is None:
        return ""
    arr = labels.get_labels_by_page_indices()
    return "".join(f"{i}\t{label}\n" for i, label in enumerate(arr))


@pytest.fixture(scope="module")
def page_labels_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_page_labels.pdf")
    os.close(fd)
    _build_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


@requires_oracle
def test_page_labels_match_pdfbox(page_labels_pdf: Path) -> None:
    """pypdfbox computes the SAME per-page label string as Apache PDFBox for
    every physical page across decimal / upper+lower Roman / upper+lower
    letters / prefix / start-offset ranges, including the A..Z → AA letter
    wraparound and the /St start offset."""
    java = run_probe_text("PageLabelsProbe", str(page_labels_pdf))
    doc = PDDocument.load(str(page_labels_pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the battery must actually exercise the tricky edges, proving
    # the oracle saw real labels (not a degenerate all-empty run).
    assert "0\ti\n" in java  # lower roman
    assert "3\tIV\n" in java  # upper roman + /St 4
    assert "8\tZ\n" in java  # letter just before wraparound
    assert "9\tAA\n" in java  # A..Z -> AA wraparound
    assert "10\tBB\n" in java  # continues doubling
    assert "11\ta\n" in java  # lower letters
    assert "13\tA-1\n" in java  # prefix + decimal
    assert "15\tcover\n" in java  # prefix-only, no /S


@requires_oracle
def test_letter_wraparound_and_start_offset(page_labels_pdf: Path) -> None:
    """Pin the two semantics most likely to drift: the letter-style A..Z..AA
    doubling and the /St start offset applied within a range (not to the
    page index)."""
    doc = PDDocument.load(str(page_labels_pdf))
    try:
        labels = doc.get_document_catalog().get_page_labels()
        assert labels is not None
        arr = labels.get_labels_by_page_indices()
        # @6 letters start at /St 24 -> X(24) Y(25) Z(26) AA(27) BB(28)
        assert arr[6:11] == ["X", "Y", "Z", "AA", "BB"]
        # @3 upper roman start at /St 4 -> IV V VI
        assert arr[3:6] == ["IV", "V", "VI"]
        # @0 lower roman default start 1 -> i ii iii
        assert arr[0:3] == ["i", "ii", "iii"]
    finally:
        doc.close()
