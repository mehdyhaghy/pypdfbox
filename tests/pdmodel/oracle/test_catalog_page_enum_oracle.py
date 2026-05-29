"""Live PDFBox differential parity for the catalog page-display enums.

Exhaustively pins the catalog ``/PageMode`` and ``/PageLayout`` enum surface:
for every one of the six :class:`PageMode` members (``UseNone`` /
``UseOutlines`` / ``UseThumbs`` / ``FullScreen`` / ``UseOC`` /
``UseAttachments``) and every one of the six :class:`PageLayout` members
(``SinglePage`` / ``OneColumn`` / ``TwoColumnLeft`` / ``TwoColumnRight`` /
``TwoPageLeft`` / ``TwoPageRight``), pypdfbox builds a one-page PDF with that
value set on the catalog, saves it, and Apache PDFBox reads it back. We assert
Apache PDFBox's ``getPageMode().stringValue()`` / ``getPageLayout()
.stringValue()`` matches the value pypdfbox wrote.

The companion :data:`test_catalog_oracle` exercises only a couple of these enum
values via real fixtures; this test pins the full enum-name-to-``/PageMode`` /
``/PageLayout`` mapping (pypdfbox setter → on-disk ``COSName`` → Apache PDFBox
getter) member by member so a future rename or mis-spelt enum string is caught.

The Java side is ``oracle/probes/CatalogPageEnumProbe.java``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.page_layout import PageLayout
from pypdfbox.pdmodel.page_mode import PageMode
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_pdf(
    out_path: Path, mode: PageMode, layout: PageLayout
) -> None:
    """Build a one-page PDF whose catalog carries the given /PageMode and
    /PageLayout enum values."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.set_page_mode(mode)
        cat.set_page_layout(layout)
        doc.save(out_path)
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize(
    "mode",
    list(PageMode),
    ids=[m.value for m in PageMode],
)
def test_page_mode_round_trips_through_pdfbox(
    mode: PageMode, tmp_path: Path
) -> None:
    """Every PageMode member written by pypdfbox is read back identically by
    Apache PDFBox. /PageLayout is held at SinglePage so the layout line is a
    constant control."""
    pdf = tmp_path / "page_mode.pdf"
    _build_pdf(pdf, mode, PageLayout.SINGLE_PAGE)
    out = run_probe_text("CatalogPageEnumProbe", str(pdf))
    expected = f"pageMode={mode.value}\npageLayout=SinglePage\n"
    assert out == expected, (
        f"PageMode {mode.value!r}: catalog enum diverges from PDFBox.\n"
        f"--- expected (pypdfbox-written) ---\n{expected}\n"
        f"--- java (read back) ---\n{out}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "layout",
    list(PageLayout),
    ids=[layout.value for layout in PageLayout],
)
def test_page_layout_round_trips_through_pdfbox(
    layout: PageLayout, tmp_path: Path
) -> None:
    """Every PageLayout member written by pypdfbox is read back identically by
    Apache PDFBox. /PageMode is held at UseNone so the mode line is a constant
    control."""
    pdf = tmp_path / "page_layout.pdf"
    _build_pdf(pdf, PageMode.USE_NONE, layout)
    out = run_probe_text("CatalogPageEnumProbe", str(pdf))
    expected = f"pageMode=UseNone\npageLayout={layout.value}\n"
    assert out == expected, (
        f"PageLayout {layout.value!r}: catalog enum diverges from PDFBox.\n"
        f"--- expected (pypdfbox-written) ---\n{expected}\n"
        f"--- java (read back) ---\n{out}"
    )
