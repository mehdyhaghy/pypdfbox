"""Live PDFBox differential parity for page-label number FORMATTING.

Complements ``test_page_labels_oracle.py`` (which sweeps every style at small
ranges) by pinning the high-value number-rendering boundary forms that the
small ranges never reach. The Java side is
``oracle/probes/PageLabelFormatProbe.java``: it loads a PDF, calls
``getDocumentCatalog().getPageLabels().getLabelsByPageIndices()`` and emits
``count=<n>`` plus one ``<index>\t<label>`` line per page. The Python side
builds the *same* PDF with pypdfbox, saves it, reads it back, and emits the
same canonical report — string-for-string.

Each range starts at a chosen ``/St`` value and spans two pages so we capture
both the boundary value and its successor:

* roman subtractive forms: 8->viii, 40->xl, 90->xc, 400->cd, 900->cm.
* the >=4000 "m-per-thousand" Acrobat quirk (4000 -> mmmm, 4999 -> mmmmcmxcix,
  matched verbatim against PDFBox).
* alphabetic doubling / tripling overflow: 26->z, 27->aa, 52->zz, 53->aaa.
* uppercase roman + uppercase letters to exercise the ``.upper()`` paths.
* a ``/P`` prefix on a roman range to confirm prefix + boundary glyph compose.
"""

from __future__ import annotations

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels
from tests.oracle.harness import requires_oracle, run_probe_text

# (style, prefix, start). Each range spans two pages; ranges are laid out
# back-to-back starting at page 0 in list order.
_RANGES: list[tuple[str | None, str | None, int]] = [
    # lower roman subtractive forms
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 8),    # viii, ix
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 40),   # xl, xli
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 90),   # xc, xci
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 400),  # cd, cdi
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 900),  # cm, cmi
    # the >=4000 m-per-thousand quirk
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 4000),  # mmmm, mmmmi
    (PDPageLabelRange.STYLE_ROMAN_LOWER, None, 4999),  # mmmmcmxcix, mmmmm
    # alphabetic doubling / tripling overflow (lower)
    (PDPageLabelRange.STYLE_LETTERS_LOWER, None, 26),  # z, aa
    (PDPageLabelRange.STYLE_LETTERS_LOWER, None, 52),  # zz, aaa
    # uppercase roman + uppercase letters (.upper() paths)
    (PDPageLabelRange.STYLE_ROMAN_UPPER, None, 49),     # XLIX, L
    (PDPageLabelRange.STYLE_LETTERS_UPPER, None, 27),   # AA, BB
    # prefix + boundary glyph compose
    (PDPageLabelRange.STYLE_ROMAN_LOWER, "App-", 900),  # App-cm, App-cmi
]

_PAGES_PER_RANGE = 2
_NUM_PAGES = len(_RANGES) * _PAGES_PER_RANGE


def _build_pdf(path: str) -> None:
    doc = PDDocument()
    try:
        for _ in range(_NUM_PAGES):
            doc.add_page(PDPage())
        page_labels = PDPageLabels(doc)
        for i, (style, prefix, start_num) in enumerate(_RANGES):
            rng = PDPageLabelRange()
            if style is not None:
                rng.set_style(style)
            if prefix is not None:
                rng.set_prefix(prefix)
            rng.set_start(start_num)
            page_labels.set_label_item(i * _PAGES_PER_RANGE, rng)
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
def test_page_label_formatting_matches_pdfbox(tmp_path) -> None:
    """Pin pypdfbox's number rendering against PDFBox at the roman / alpha
    formatting boundaries, including the >=4000 m-per-thousand quirk."""
    pdf = tmp_path / "page_label_format.pdf"
    _build_pdf(str(pdf))

    java = run_probe_text("PageLabelFormatProbe", str(pdf))

    doc = PDDocument.load(str(pdf))
    try:
        labels = (
            doc.get_document_catalog()
            .get_page_labels()
            .get_labels_by_page_indices()
        )
    finally:
        doc.close()
    py = _report(labels)

    assert py == java, (
        "page-label formatting diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
