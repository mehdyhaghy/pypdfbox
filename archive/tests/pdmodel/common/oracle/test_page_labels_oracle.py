"""Live PDFBox differential parity for page labels (``PDPageLabels``).

Pins ``PDPageLabels.get_labels_by_page_indices()`` against Apache PDFBox
3.0.7. The Java side is ``oracle/probes/PageLabelProbe.java``: it loads a PDF,
calls ``getDocumentCatalog().getPageLabels().getLabelsByPageIndices()`` and
emits ``count=<n>`` plus one ``<index>\t<label>`` line per page. The Python
side builds the *same* PDF with pypdfbox, saves it, reads it back, and emits
the same canonical report — string-for-string.

The /PageLabels number tree built here exercises every numbering style and the
high-value edge cases:

* lower-roman range from page 0 (``i, ii, iii, iv, v``) — covers the 4->iv
  subtractive form.
* decimal range with ``/St 1`` (``1, 2, 3``).
* prefixed decimal range (``/P "A-"`` + ``/St 1`` -> ``A-1, A-2``).
* upper-letter range straddling the 26->Z / 27->AA overflow boundary
  (``/St 25`` -> ``Y, Z, AA, BB``).
* upper-roman range with ``/St 9`` (``IX, X, XL ...``) exercising 9->ix and
  40->xl subtractive forms via a large ``/St``.
* lower-letter range (``a, b, c``).
* no-style range (prefix only -> the prefix repeated).
"""

from __future__ import annotations

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels
from tests.oracle.harness import requires_oracle, run_probe_text

# (start_index, style, prefix, start) for each /Nums range. None style => no /S.
_RANGES: list[tuple[int, str | None, str | None, int | None]] = [
    # lower roman from page 0: i ii iii iv v   (4 -> iv subtractive)
    (0, PDPageLabelRange.STYLE_ROMAN_LOWER, None, None),
    # decimal /St 1 from page 5: 1 2 3
    (5, PDPageLabelRange.STYLE_DECIMAL, None, 1),
    # prefixed decimal A- from page 8: A-1 A-2
    (8, PDPageLabelRange.STYLE_DECIMAL, "A-", 1),
    # upper letters straddling overflow from page 10 /St 25: Y Z AA BB
    (10, PDPageLabelRange.STYLE_LETTERS_UPPER, None, 25),
    # upper roman /St 9 from page 14: IX X XL ... (9 -> ix, 40 -> xl)
    (14, PDPageLabelRange.STYLE_ROMAN_UPPER, None, 9),
    # lower letters from page 17: a b c
    (17, PDPageLabelRange.STYLE_LETTERS_LOWER, None, None),
    # no-style prefix-only from page 20: "App" repeated
    (20, None, "App", None),
]

_NUM_PAGES = 23


def _build_pdf(path: str) -> None:
    """Build the multi-range labelled PDF with pypdfbox and save it."""
    doc = PDDocument()
    try:
        for _ in range(_NUM_PAGES):
            doc.add_page(PDPage())
        page_labels = PDPageLabels(doc)
        for start, style, prefix, start_num in _RANGES:
            rng = PDPageLabelRange()
            if style is not None:
                rng.set_style(style)
            if prefix is not None:
                rng.set_prefix(prefix)
            if start_num is not None:
                rng.set_start(start_num)
            page_labels.set_label_item(start, rng)
        doc.get_document_catalog().set_page_labels(page_labels)
        doc.save(path)
    finally:
        doc.close()


def _report(labels: list[str]) -> str:
    lines = [f"count={len(labels)}"]
    for i, label in enumerate(labels):
        lines.append(f"{i}\t{label}")
    return "\n".join(lines) + "\n"


@requires_oracle
def test_page_labels_match_pdfbox(tmp_path) -> None:
    """Build a many-range PDF, then assert pypdfbox's per-page label strings
    equal Apache PDFBox's across every style and edge case."""
    pdf = tmp_path / "page_labels.pdf"
    _build_pdf(str(pdf))

    java = run_probe_text("PageLabelProbe", str(pdf))

    doc = PDDocument.load(str(pdf))
    try:
        labels = doc.get_document_catalog().get_page_labels().get_labels_by_page_indices()
    finally:
        doc.close()
    py = _report(labels)

    assert py == java, (
        "page-label report diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
