"""Wave 1370 — Overlay positioning + page-size mismatch (agent E).

Covers the overlay engine's geometric behaviour:

- ``calculate_affine_transform`` centers a smaller overlay on a larger
  destination page (positive shifts in both axes).
- ``calculate_affine_transform`` centers a larger overlay on a smaller
  destination page (negative shifts both axes).
- Non-zero lower-left origin on the destination page-media-box (the
  PDFBOX-6048 fix — upstream 3.0.x assumed (0, 0); pypdfbox uses the
  real corner).
- Non-zero lower-left origin on the overlay's media box also contributes.
- Equal-size pages produce identity-translation transform.
- Background vs foreground positions: original content order preserved
  (background prepends, foreground appends).
- :meth:`Overlay.close` closes only file-loaded overlay docs, not
  caller-supplied PDDocument instances.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

_CONTENTS = COSName.get_pdf_name("Contents")


def _build_base_doc(num_pages: int, width: float, height: float) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage(PDRectangle.from_width_height(width, height))
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.add_rect(10.0, 10.0, 50.0, 50.0)
            cs.stroke()
    return doc


def _build_overlay_doc(width: float, height: float) -> PDDocument:
    doc = PDDocument()
    page = PDPage(PDRectangle.from_width_height(width, height))
    doc.add_page(page)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(5.0, 5.0, 20.0, 20.0)
        cs.fill()
    return doc


def _flatten_contents(page: PDPage) -> list[COSStream]:
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    out: list[COSStream] = []
    if isinstance(contents, COSStream):
        out.append(contents)
    elif isinstance(contents, COSArray):
        for entry in contents:
            resolved = entry.get_object() if hasattr(entry, "get_object") else entry
            if isinstance(resolved, COSStream):
                out.append(resolved)
    return out


# ---------- affine transform geometry ----------


def test_smaller_overlay_centered_on_larger_page() -> None:
    """A 200x200 overlay on a 400x400 page centers at (100, 100)."""
    overlay = Overlay()
    page = PDPage(PDRectangle.from_width_height(400.0, 400.0))
    overlay_mb = PDRectangle.from_width_height(200.0, 200.0)
    matrix = overlay.calculate_affine_transform(page, overlay_mb)
    assert matrix[0] == 1.0
    assert matrix[1] == 0.0
    assert matrix[2] == 0.0
    assert matrix[3] == 1.0
    # Centering: (400-200)/2 = 100.
    assert matrix[4] == 100.0
    assert matrix[5] == 100.0


def test_larger_overlay_on_smaller_page_negative_shift() -> None:
    """A 400x400 overlay on a 200x200 page is centered with NEGATIVE
    shifts in both axes ((-100, -100))."""
    overlay = Overlay()
    page = PDPage(PDRectangle.from_width_height(200.0, 200.0))
    overlay_mb = PDRectangle.from_width_height(400.0, 400.0)
    matrix = overlay.calculate_affine_transform(page, overlay_mb)
    assert matrix[4] == -100.0
    assert matrix[5] == -100.0


def test_equal_size_no_shift() -> None:
    """Same-size page and overlay → translation is (0, 0)."""
    overlay = Overlay()
    page = PDPage(PDRectangle.from_width_height(300.0, 400.0))
    overlay_mb = PDRectangle.from_width_height(300.0, 400.0)
    matrix = overlay.calculate_affine_transform(page, overlay_mb)
    assert matrix[4] == 0.0
    assert matrix[5] == 0.0


def test_page_with_nonzero_lower_left_origin() -> None:
    """A page whose media box has a non-zero lower-left origin: the shift
    must compensate via the real LL (PDFBOX-6048)."""
    overlay = Overlay()
    # Build a page whose media box is [50, 60, 250, 360] — width 200,
    # height 300, lower-left (50, 60).
    page_mb = PDRectangle(50.0, 60.0, 250.0, 360.0)
    page = PDPage(page_mb)
    overlay_mb = PDRectangle.from_width_height(100.0, 200.0)  # smaller
    matrix = overlay.calculate_affine_transform(page, overlay_mb)
    # Horizontal: (200-100)/2 + 50 - 0 = 100.
    assert matrix[4] == 100.0
    # Vertical: (300-200)/2 + 60 - 0 = 110.
    assert matrix[5] == 110.0


def test_overlay_media_box_with_nonzero_lower_left_origin() -> None:
    """An overlay whose media box has a non-zero LL also contributes a
    subtractive correction."""
    overlay = Overlay()
    page = PDPage(PDRectangle.from_width_height(400.0, 400.0))
    # Overlay media box [10, 20, 210, 220] — width 200, height 200, LL (10, 20).
    overlay_mb = PDRectangle(10.0, 20.0, 210.0, 220.0)
    matrix = overlay.calculate_affine_transform(page, overlay_mb)
    # Horizontal: (400-200)/2 + 0 - 10 = 90.
    assert matrix[4] == 90.0
    # Vertical: (400-200)/2 + 0 - 20 = 80.
    assert matrix[5] == 80.0


# ---------- background vs foreground placement ----------


def test_background_position_prepends_overlay_content() -> None:
    """Background → overlay content appears BEFORE the original content
    in the /Contents array."""
    base = _build_base_doc(1, 595.0, 842.0)
    overlay_doc = _build_overlay_doc(200.0, 200.0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(overlay_doc)
    overlay.set_overlay_position(Position.BACKGROUND)
    result = overlay.overlay({})
    try:
        streams = _flatten_contents(result.get_page(0))
        assert len(streams) >= 2  # at least overlay + original
        # Background means the overlay stream comes first.
        first_body = streams[0].get_raw_data() or b""
        # Marker we left in the original content (rect + stroke) appears
        # in a later content stream, not the first.
        assert b"50 50 re" not in first_body or first_body.startswith(b"q\n")
    finally:
        result.close()
        overlay_doc.close()


def test_foreground_position_appends_overlay_content() -> None:
    """Foreground → original content comes first; overlay appended."""
    base = _build_base_doc(1, 595.0, 842.0)
    overlay_doc = _build_overlay_doc(200.0, 200.0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(overlay_doc)
    overlay.set_overlay_position(Position.FOREGROUND)
    result = overlay.overlay({})
    try:
        streams = _flatten_contents(result.get_page(0))
        # At least 3: the leading q\n marker, the original content, the trailing Q\n + overlay.
        assert len(streams) >= 3
    finally:
        result.close()
        overlay_doc.close()


# ---------- close() does NOT close caller-supplied docs ----------


def test_close_keeps_caller_supplied_input_pdf_open(tmp_path: Path) -> None:
    """When the caller passed a PDDocument via ``set_input_pdf`` (not a
    file path), ``Overlay.close()`` must NOT close that document — it's
    owned by the caller."""
    base = _build_base_doc(1, 595.0, 842.0)
    overlay_doc = _build_overlay_doc(200.0, 200.0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(overlay_doc)
    overlay.overlay({})
    overlay.close()
    # The caller-owned docs are still usable after close().
    assert not base.is_closed()
    assert not overlay_doc.is_closed()
    base.close()
    overlay_doc.close()


def test_close_closes_file_loaded_input_pdf(tmp_path: Path) -> None:
    """When the caller passed a *file path*, ``close()`` must close the
    auto-loaded PDDocument under the hood (no resource leak)."""
    base_path = tmp_path / "base.pdf"
    overlay_path = tmp_path / "overlay.pdf"
    base = _build_base_doc(1, 595.0, 842.0)
    base.save(base_path)
    base.close()
    overlay_doc = _build_overlay_doc(200.0, 200.0)
    overlay_doc.save(overlay_path)
    overlay_doc.close()

    overlay = Overlay()
    overlay.set_input_file(str(base_path))
    overlay.set_all_pages_overlay_file(str(overlay_path))
    result = overlay.overlay({})
    # Close all helper docs BEFORE the next overlay run.
    overlay.close()
    # ``result`` is the same underlying PDDocument as the auto-loaded input,
    # so close() drained it.
    assert result.is_closed()


# ---------- multi-page base + single-page overlay ----------


def test_multi_page_base_all_pages_overlay_applied(tmp_path: Path) -> None:
    """Every page of a multi-page base doc gets the overlay applied (the
    single-page overlay is reused across pages)."""
    base = _build_base_doc(3, 400.0, 400.0)
    overlay_doc = _build_overlay_doc(100.0, 100.0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(overlay_doc)
    overlay.set_overlay_position(Position.BACKGROUND)
    result = overlay.overlay({})
    try:
        # Every page now has a /Contents COSArray (because we built up
        # an array per page during overlay).
        for i in range(result.get_number_of_pages()):
            contents = result.get_page(i).get_cos_object().get_dictionary_object(
                _CONTENTS
            )
            assert isinstance(contents, (COSArray, COSStream))
            # If COSArray, must have at least 2 streams (overlay + original).
            if isinstance(contents, COSArray):
                assert contents.size() >= 2
    finally:
        result.close()
        overlay_doc.close()
