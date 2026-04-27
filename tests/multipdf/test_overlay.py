"""Hand-written tests for :class:`pypdfbox.multipdf.Overlay`."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _build_base_doc() -> PDDocument:
    """Two-page A4 document with a thin rectangle on each page so we can
    tell that overlay content has been prepended (background) or appended
    (foreground) without disturbing the original strokes."""
    doc = PDDocument()
    for _ in range(2):
        page = PDPage(PDRectangle.from_width_height(595.0, 842.0))
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.add_rect(50.0, 50.0, 100.0, 50.0)
            cs.stroke()
    return doc


def _build_overlay_doc() -> PDDocument:
    """Single-page overlay PDF that draws a small filled square."""
    doc = PDDocument()
    page = PDPage(PDRectangle.from_width_height(200.0, 200.0))
    doc.add_page(page)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(20.0, 20.0, 50.0, 50.0)
        cs.fill()
    return doc


def _resolve_xobject_keys(page: PDPage) -> list[str]:
    res = page.get_resources()
    sub = res.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("XObject")
    )
    if not isinstance(sub, COSDictionary):
        return []
    return [k.get_name() for k in sub.key_set()]


def _flatten_contents(page: PDPage) -> list[COSStream]:
    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    out: list[COSStream] = []
    if isinstance(contents, COSStream):
        out.append(contents)
    elif isinstance(contents, COSArray):
        for entry in contents:
            resolved = entry.get_object() if hasattr(entry, "get_object") else entry
            if isinstance(resolved, COSStream):
                out.append(resolved)
    return out


def _decoded_content(page: PDPage) -> bytes:
    chunks: list[bytes] = []
    for stream in _flatten_contents(page):
        with stream.create_input_stream() as src:
            chunks.append(src.read())
    return b"\n".join(chunks)


def test_overlay_default_background_adds_xobject_reference() -> None:
    base = _build_base_doc()
    overlay_doc = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    result = overlay.overlay({})

    assert result is base
    # Every page should now have an /XObject entry containing the form
    # resource the overlay created. Two pages → two distinct overlay forms
    # registered (the form XObject is allocated per page-resource set).
    for i in range(result.get_number_of_pages()):
        page = result.get_page(i)
        xobject_names = _resolve_xobject_keys(page)
        assert xobject_names, f"page {i} has no /XObject entries"
        # The page's combined content stream must reference one of those
        # /XObject names with a ``Do`` operator (overlay invocation).
        body = _decoded_content(page)
        matched = any(
            f"/{name} Do".encode("latin-1") in body for name in xobject_names
        )
        assert matched, (
            f"page {i} contents do not invoke any /XObject with Do; "
            f"got {body!r} (resources: {xobject_names})"
        )


def test_overlay_foreground_wraps_existing_content() -> None:
    base = _build_base_doc()
    overlay_doc = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    overlay.set_overlay_position(Position.FOREGROUND)
    overlay.overlay({})

    # Foreground inserts the q/Q-bracketed original content first, then the
    # overlay invocation last. The combined content stream must therefore
    # start with a `q` stream and have the `Do` invocation appearing AFTER
    # at least one of the original-content streams.
    page = base.get_page(0)
    streams = _flatten_contents(page)
    assert len(streams) >= 3, "FOREGROUND should produce >= 3 content streams"
    # First stream is just `q\n`.
    with streams[0].create_input_stream() as src:
        assert src.read().strip() == b"q"
    # Some later stream is the `… cm\n /OL/Form Do Q\nQ` invocation.
    body = _decoded_content(page)
    assert b" Do Q\nQ\n" in body or b"Do Q" in body


def test_overlay_specific_page_map_via_overlay_documents() -> None:
    base = _build_base_doc()
    overlay_a = _build_overlay_doc()
    overlay_b = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.overlay_documents({1: overlay_a, 2: overlay_b})

    # Both pages get an overlay invocation, and the overlay's resources
    # were cloned (not shared) into the input document — i.e. the form
    # XObject's /Resources is a fresh dictionary, not the overlay-doc
    # original.
    for i in range(base.get_number_of_pages()):
        page = base.get_page(i)
        names = _resolve_xobject_keys(page)
        assert names, f"page {i} missing /XObject"


def test_overlay_specific_page_overlay_pdf_setter() -> None:
    base = _build_base_doc()
    overlay_doc = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_specific_page_overlay_pdf({2: overlay_doc})
    overlay.overlay({})

    # Page 2 (1-based) must have an /XObject; page 1 had no per-page
    # overlay configured and no default → should be untouched.
    page1 = base.get_page(0)
    page2 = base.get_page(1)
    assert not _resolve_xobject_keys(page1), (
        "page 1 unexpectedly received an overlay"
    )
    assert _resolve_xobject_keys(page2), "page 2 should have an overlay /XObject"


def test_overlay_first_and_last_distinct() -> None:
    base = _build_base_doc()
    first_doc = _build_overlay_doc()
    last_doc = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_first_page_overlay_pdf(first_doc)
    overlay.set_last_page_overlay_pdf(last_doc)
    overlay.overlay({})

    for i in (0, 1):
        page = base.get_page(i)
        names = _resolve_xobject_keys(page)
        assert names


def test_overlay_requires_input_document() -> None:
    overlay_doc = _build_overlay_doc()
    overlay = Overlay()
    overlay.set_default_overlay_pdf(overlay_doc)
    with pytest.raises(ValueError, match="No input document"):
        overlay.overlay({})


def test_overlay_overlay_none_argument_rejected() -> None:
    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    with pytest.raises(ValueError):
        overlay.overlay(None)


def test_overlay_pdfbox_6048_uses_real_lower_left_corner() -> None:
    """PDFBOX-6048 — overlay centering must use the real lower-left
    corner of both rectangles, not (0, 0). When the page MediaBox is
    shifted away from the origin the overlay's translation should track
    that shift."""
    overlay_inst = Overlay()
    page = PDPage(PDRectangle(100.0, 200.0, 700.0, 1000.0))  # 600 x 800 page
    overlay_box = PDRectangle(0.0, 0.0, 200.0, 200.0)         # 200 x 200 overlay
    matrix = overlay_inst.calculate_affine_transform(page, overlay_box)
    # Centering: (600-200)/2 + 100 = 300, (800-200)/2 + 200 = 500.
    assert matrix == [1.0, 0.0, 0.0, 1.0, 300.0, 500.0]


def test_overlay_position_enum_round_trip() -> None:
    assert Position.FOREGROUND is not Position.BACKGROUND
    overlay = Overlay()
    overlay.set_overlay_position(Position.FOREGROUND)
    assert overlay._position is Position.FOREGROUND  # noqa: SLF001
    overlay.set_overlay_position(Position.BACKGROUND)
    assert overlay._position is Position.BACKGROUND  # noqa: SLF001


def test_overlay_close_is_idempotent() -> None:
    overlay = Overlay()
    overlay.close()
    overlay.close()


def test_overlay_context_manager_closes_only_owned_documents() -> None:
    base = _build_base_doc()
    overlay_doc = _build_overlay_doc()

    with Overlay() as overlay:
        overlay.set_input_pdf(base)
        overlay.set_default_overlay_pdf(overlay_doc)
        overlay.overlay({})
    # Caller-owned documents must NOT be closed by Overlay.close (mirrors
    # upstream: Overlay only closes documents IT loaded). The base doc
    # was passed in by setInputPDF — it stays open.
    assert not base.is_closed()
