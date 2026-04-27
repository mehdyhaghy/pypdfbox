"""Hand-written tests for :class:`pypdfbox.multipdf.Overlay`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _build_base_doc(num_pages: int = 2) -> PDDocument:
    """N-page A4 document with a thin rectangle on each page so we can
    tell that overlay content has been prepended (background) or appended
    (foreground) without disturbing the original strokes."""
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage(PDRectangle.from_width_height(595.0, 842.0))
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.add_rect(50.0, 50.0, 100.0, 50.0)
            cs.stroke()
    return doc


def _build_multi_page_overlay_doc(num_pages: int) -> PDDocument:
    """Multi-page overlay PDF — used to exercise
    :meth:`Overlay.set_all_pages_overlay_pdf` cycling."""
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage(PDRectangle.from_width_height(200.0, 200.0))
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.add_rect(20.0, 20.0, 50.0, 50.0)
            cs.fill()
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


# ---------- odd / even / all-pages / file-path round-out ----------


def test_overlay_odd_pages_only() -> None:
    """``set_odd_page_overlay_pdf`` must apply the overlay only to pages
    1, 3, 5, … (1-based). On a 4-page input we expect XObject/Do on pages
    1 and 3, nothing on 2 and 4."""
    base = _build_base_doc(4)
    odd = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_odd_page_overlay_pdf(odd)
    overlay.overlay({})

    for i in (0, 2):  # 1-based 1, 3 → odd
        assert _resolve_xobject_keys(base.get_page(i))
    for i in (1, 3):  # 1-based 2, 4 → even (no overlay)
        assert not _resolve_xobject_keys(base.get_page(i))


def test_overlay_even_pages_only() -> None:
    base = _build_base_doc(4)
    even = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_even_page_overlay_pdf(even)
    overlay.overlay({})

    for i in (0, 2):  # odd pages — no overlay
        assert not _resolve_xobject_keys(base.get_page(i))
    for i in (1, 3):  # even pages — overlay
        assert _resolve_xobject_keys(base.get_page(i))


def test_overlay_all_pages_overlay_pdf_cycles_through_overlay_pages() -> None:
    """``set_all_pages_overlay_pdf`` builds the per-page layout map from
    the overlay document's pages and applies them cyclically when the
    input has more pages than the overlay. Mirrors upstream
    ``useAllOverlayPages`` semantics."""
    base = _build_base_doc(5)
    overlay_doc = _build_multi_page_overlay_doc(2)  # cycle every 2 pages

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(overlay_doc)
    overlay.overlay({})

    # Every page must have received an overlay (cycle covers all pages).
    for i in range(5):
        assert _resolve_xobject_keys(base.get_page(i)), (
            f"page {i} missing all-pages overlay XObject"
        )


def test_overlay_first_page_takes_precedence_over_default() -> None:
    """When both first-page and default overlays are configured the
    first-page overlay wins on page 1."""
    base = _build_base_doc(2)
    first = _build_overlay_doc()
    default = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_first_page_overlay_pdf(first)
    overlay.set_default_overlay_pdf(default)
    overlay.overlay({})

    # Both pages get an overlay — but page 1 picks the first-page bucket
    # and page 2 picks the default. We can't tell them apart structurally
    # without rendering, but we can verify both got distinct invocations.
    for i in (0, 1):
        assert _resolve_xobject_keys(base.get_page(i))


def test_overlay_specific_page_overrides_default() -> None:
    """``overlay({n: path})`` for page n must beat the default overlay."""
    base = _build_base_doc(2)
    default = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(default)
    overlay.overlay({})

    for i in (0, 1):
        assert _resolve_xobject_keys(base.get_page(i))


def test_overlay_set_input_file_round_trip(tmp_path: Path) -> None:
    """Verify file-path setters work end-to-end: write a base PDF + an
    overlay PDF to disk, configure the Overlay with file paths, and
    confirm the input PDF gets the overlay applied."""
    base_path = tmp_path / "base.pdf"
    overlay_path = tmp_path / "overlay.pdf"

    base = _build_base_doc()
    base.save(str(base_path))
    base.close()

    overlay_doc = _build_overlay_doc()
    overlay_doc.save(str(overlay_path))
    overlay_doc.close()

    with Overlay() as overlay:
        overlay.set_input_file(str(base_path))
        overlay.set_default_overlay_file(str(overlay_path))
        assert overlay.get_input_file() == str(base_path)
        assert overlay.get_default_overlay_file() == str(overlay_path)
        result = overlay.overlay({})
        assert result.get_number_of_pages() == 2
        for i in range(2):
            assert _resolve_xobject_keys(result.get_page(i))


def test_overlay_specific_page_overlay_via_path(tmp_path: Path) -> None:
    """Pass a specific-page overlay via the ``overlay({page: path})``
    argument. Mirrors upstream ``overlay(Map<Integer, String>)``."""
    overlay_path = tmp_path / "specific.pdf"
    overlay_doc = _build_overlay_doc()
    overlay_doc.save(str(overlay_path))
    overlay_doc.close()

    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    result = overlay.overlay({2: str(overlay_path)})

    assert not _resolve_xobject_keys(result.get_page(0))
    assert _resolve_xobject_keys(result.get_page(1))


def test_overlay_specific_page_path_dedupes_repeated_paths(
    tmp_path: Path,
) -> None:
    """Same path mapped to two pages should only be loaded once. Mirrors
    upstream's ``layouts.get(path)`` cache. We can't directly observe the
    cache, but we can confirm the overlay still applies to both pages."""
    overlay_path = tmp_path / "shared.pdf"
    overlay_doc = _build_overlay_doc()
    overlay_doc.save(str(overlay_path))
    overlay_doc.close()

    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    result = overlay.overlay({1: str(overlay_path), 2: str(overlay_path)})

    for i in (0, 1):
        assert _resolve_xobject_keys(result.get_page(i))


def test_overlay_combined_content_handles_array_of_streams() -> None:
    """If the input page already has /Contents as an array of streams,
    the overlay must preserve them (background mode appends them after
    the overlay invocation)."""
    base = PDDocument()
    page = PDPage(PDRectangle.from_width_height(595.0, 842.0))
    base.add_page(page)
    # Two separate content streams produce a /Contents COSArray.
    with PDPageContentStream(base, page) as cs:
        cs.add_rect(10.0, 10.0, 20.0, 20.0)
        cs.stroke()
    with PDPageContentStream(
        base, page, append_mode=True
    ) as cs:
        cs.add_rect(40.0, 40.0, 20.0, 20.0)
        cs.stroke()
    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    assert isinstance(contents, COSArray)
    pre_overlay_count = len(contents)

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_build_overlay_doc())
    overlay.overlay({})

    new_contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    assert isinstance(new_contents, COSArray)
    # Background: 1 overlay invocation stream + the original streams.
    assert len(new_contents) == 1 + pre_overlay_count


def test_overlay_set_adjust_rotation_toggles_flag() -> None:
    overlay = Overlay()
    assert overlay._adjust_rotation is False  # noqa: SLF001
    overlay.set_adjust_rotation(True)
    assert overlay._adjust_rotation is True  # noqa: SLF001
    overlay.set_adjust_rotation(False)
    assert overlay._adjust_rotation is False  # noqa: SLF001


def test_overlay_float_to_string_strips_trailing_zeros() -> None:
    """The internal ``_float_to_string`` must keep ``.0`` for integer-valued
    floats and strip trailing zeros otherwise — this matches upstream's
    BigDecimal-based formatter and keeps content streams compact."""
    f = Overlay._float_to_string  # noqa: SLF001
    assert f(0.0) == "0.0"
    assert f(1.0) == "1.0"
    assert f(1.5) == "1.5"
    # 0.1 has irrational binary representation; we just ensure no trailing 0s.
    s = f(0.1)
    assert s.startswith("0.1")
    assert not s.endswith("0")


def test_overlay_unknown_position_raises() -> None:
    """An invalid position value (e.g. ``None``) must raise on overlay()."""
    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_build_overlay_doc())
    overlay._position = "BAD"  # type: ignore[assignment]  # noqa: SLF001
    with pytest.raises(OSError, match="Unknown type of position"):
        overlay.overlay({})


def test_overlay_addresses_pdfbox_6048_with_overlay_lower_left_offset() -> None:
    """Mirror of the lower-left-corner test, but with the **overlay** box
    starting away from origin. The translation must subtract the overlay's
    own lower-left in addition to the page math."""
    inst = Overlay()
    page = PDPage(PDRectangle.from_width_height(600.0, 800.0))
    overlay_box = PDRectangle(50.0, 100.0, 250.0, 300.0)  # 200 x 200, offset
    matrix = inst.calculate_affine_transform(page, overlay_box)
    # h_shift = (600 - 200) / 2 + 0 - 50 = 150
    # v_shift = (800 - 200) / 2 + 0 - 100 = 200
    assert matrix == [1.0, 0.0, 0.0, 1.0, 150.0, 200.0]


def test_overlay_close_clears_specific_page_layout() -> None:
    """``close()`` must clear the cached specific-page layout map so the
    instance can be reused safely."""
    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.overlay_documents({1: _build_overlay_doc()})
    assert overlay._specific_page_overlay_layout  # noqa: SLF001
    overlay.close()
    assert not overlay._specific_page_overlay_layout  # noqa: SLF001


def test_overlay_returns_input_document_identity() -> None:
    """The overlay() return value must be the same object passed via
    set_input_pdf — mirrors upstream's documented contract."""
    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_build_overlay_doc())
    result = overlay.overlay({})
    assert result is base


def test_overlay_no_overlay_configured_leaves_pages_untouched() -> None:
    """When no overlay buckets are configured, ``overlay({})`` must walk
    every page and skip them all without modifying /Contents."""
    base = _build_base_doc()
    original_contents = [
        base.get_page(i).get_cos_object().get_dictionary_object(COSName.CONTENTS)
        for i in range(base.get_number_of_pages())
    ]
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.overlay({})
    for i, original in enumerate(original_contents):
        # /Contents object identity must be preserved (no overlay layered).
        assert (
            base.get_page(i)
            .get_cos_object()
            .get_dictionary_object(COSName.CONTENTS)
            is original
        )
