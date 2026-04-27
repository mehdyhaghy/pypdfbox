from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripperByArea, PDFTextStripper


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# region management
# ---------------------------------------------------------------------------


def test_inherits_from_pdf_text_stripper() -> None:
    s = PDFTextStripperByArea()
    assert isinstance(s, PDFTextStripper)


def test_constructor_disables_beads() -> None:
    s = PDFTextStripperByArea()
    # Upstream's constructor calls super().setShouldSeparateByBeads(false) —
    # the bead flag should start out false rather than the inherited true.
    assert s.is_should_separate_by_beads() is False


def test_set_should_separate_by_beads_is_noop() -> None:
    s = PDFTextStripperByArea()
    s.set_should_separate_by_beads(True)
    # Upstream documents this override as a no-op — beads + regions are
    # incompatible. The flag must remain false even after a setter call.
    assert s.is_should_separate_by_beads() is False


def test_add_and_remove_region_round_trip() -> None:
    s = PDFTextStripperByArea()
    s.add_region("a", (0.0, 0.0, 100.0, 100.0))
    s.add_region("b", (50.0, 50.0, 200.0, 200.0))
    assert s.get_regions() == ["a", "b"]
    s.remove_region("a")
    assert s.get_regions() == ["b"]


def test_remove_region_unknown_is_noop() -> None:
    s = PDFTextStripperByArea()
    s.add_region("a", (0.0, 0.0, 10.0, 10.0))
    s.remove_region("does-not-exist")
    assert s.get_regions() == ["a"]


def test_add_region_overwrites_rect_keeps_position() -> None:
    s = PDFTextStripperByArea()
    s.add_region("a", (0.0, 0.0, 10.0, 10.0))
    s.add_region("b", (0.0, 0.0, 10.0, 10.0))
    s.add_region("a", (5.0, 5.0, 50.0, 50.0))
    # Re-adding "a" must not re-order or duplicate it.
    assert s.get_regions() == ["a", "b"]


def test_add_region_accepts_pdrectangle() -> None:
    s = PDFTextStripperByArea()
    s.add_region("a", PDRectangle(0.0, 0.0, 100.0, 100.0))
    assert s.get_regions() == ["a"]


def test_add_region_rejects_garbage() -> None:
    s = PDFTextStripperByArea()
    with pytest.raises(TypeError):
        s.add_region("a", "not a rect")  # type: ignore[arg-type]


def test_get_text_for_region_unknown_returns_empty() -> None:
    s = PDFTextStripperByArea()
    # Mirrors upstream's StringWriter-on-fresh-key behavior — no
    # extraction has been performed, so an empty string comes back.
    assert s.get_text_for_region("never-added") == ""


# ---------------------------------------------------------------------------
# extract_regions: text routing by rectangle
# ---------------------------------------------------------------------------


def test_extract_regions_returns_only_overlapping_text() -> None:
    """Three rows of text on a page; a region covering only the middle
    row must capture only that row's text."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        # Three rows at y = 700 (top), 600 (middle), 500 (bottom).
        b"BT /F0 12 Tf 100 700 Td (top) Tj ET "
        b"BT /F0 12 Tf 100 600 Td (middle) Tj ET "
        b"BT /F0 12 Tf 100 500 Td (bottom) Tj ET ",
    )

    s = PDFTextStripperByArea()
    # Region tightly around the middle row: y from 590..610 in user space.
    s.add_region("mid", (50.0, 590.0, 500.0, 20.0))
    s.extract_regions(page)

    assert s.get_text_for_region("mid").strip() == "middle"


def test_extract_regions_multiple_regions_independent() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (alpha) Tj ET "
        b"BT /F0 12 Tf 100 600 Td (beta) Tj ET "
        b"BT /F0 12 Tf 100 500 Td (gamma) Tj ET ",
    )

    s = PDFTextStripperByArea()
    s.add_region("top", (50.0, 690.0, 500.0, 20.0))
    s.add_region("bot", (50.0, 490.0, 500.0, 20.0))
    s.extract_regions(page)

    assert s.get_text_for_region("top").strip() == "alpha"
    assert s.get_text_for_region("bot").strip() == "gamma"


def test_extract_regions_overlapping_regions_share_text() -> None:
    """A position whose origin falls inside two regions must land in
    both — overlapping regions are allowed."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (shared) Tj ET"
    )

    s = PDFTextStripperByArea()
    s.add_region("a", (50.0, 690.0, 200.0, 20.0))
    s.add_region("b", (90.0, 695.0, 200.0, 10.0))
    s.extract_regions(page)

    assert s.get_text_for_region("a").strip() == "shared"
    assert s.get_text_for_region("b").strip() == "shared"


def test_extract_regions_drops_text_outside_region() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (inside) Tj ET "
        b"BT /F0 12 Tf 100 100 Td (outside) Tj ET ",
    )

    s = PDFTextStripperByArea()
    # Only catches y near 700.
    s.add_region("top", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)

    captured = s.get_text_for_region("top")
    assert "inside" in captured
    assert "outside" not in captured


def test_extract_regions_resets_between_calls() -> None:
    """A second extract_regions call on a different page must not carry
    text over from the first."""
    doc = PDDocument()
    page1 = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (first) Tj ET"
    )
    page2 = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (second) Tj ET"
    )

    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))

    s.extract_regions(page1)
    assert s.get_text_for_region("r").strip() == "first"

    s.extract_regions(page2)
    assert s.get_text_for_region("r").strip() == "second"


def test_extract_regions_blank_page_yields_empty_text() -> None:
    doc = PDDocument()
    blank = PDPage()
    doc.add_page(blank)

    s = PDFTextStripperByArea()
    s.add_region("r", (0.0, 0.0, 612.0, 792.0))
    # No /Contents on the page → upstream's hasContents() guard returns
    # false, so the region buffer stays empty.
    s.extract_regions(blank)

    assert s.get_text_for_region("r") == ""


def test_remove_region_clears_cached_text() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (hello) Tj ET"
    )
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 20.0))
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == "hello"

    s.remove_region("r")
    # After removal the region's cached text is dropped — a subsequent
    # lookup falls through to the empty-string default.
    assert s.get_text_for_region("r") == ""
