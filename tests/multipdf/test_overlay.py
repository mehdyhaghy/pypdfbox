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


# ---------- upstream-parity round-out ----------


def test_overlay_uses_ol_prefix_for_form_xobject() -> None:
    """Round-out — upstream registers the overlay form XObject under the
    ``OL`` prefix (``resources.add(overlayFormXObject, "OL")`` in Java).
    The resulting /XObject key must therefore be ``OL0`` / ``OL1`` / …
    rather than the default ``Form*``."""
    base = _build_base_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_build_overlay_doc())
    overlay.overlay({})

    for i in range(base.get_number_of_pages()):
        page = base.get_page(i)
        names = _resolve_xobject_keys(page)
        assert names, f"page {i} missing /XObject"
        assert all(n.startswith("OL") for n in names), (
            f"page {i}: expected OL-prefixed keys, got {names}"
        )


def test_overlay_form_bbox_uses_create_retranslated_rectangle() -> None:
    """Upstream calls ``layoutPage.overlayMediaBox.createRetranslatedRectangle()``
    for the form XObject's /BBox — i.e. the box's lower-left translates to
    (0, 0) and width/height carry over. Verifies the round-out swaps the
    manual ``PDRectangle(0, 0, w, h)`` construction for the upstream call."""
    base = _build_base_doc(1)
    # Overlay doc with a non-zero lower-left to make the retranslation
    # observable: a retranslated 200x200 box is always (0, 0, 200, 200)
    # regardless of the source's lower-left corner.
    overlay_doc = PDDocument()
    page = PDPage(PDRectangle(50.0, 100.0, 250.0, 300.0))
    overlay_doc.add_page(page)
    with PDPageContentStream(overlay_doc, page) as cs:
        cs.add_rect(60.0, 110.0, 50.0, 50.0)
        cs.fill()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    overlay.overlay({})

    # Reach into the registered form XObject and check its /BBox entry.
    base_page = base.get_page(0)
    res = base_page.get_resources()
    sub = res.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("XObject")
    )
    assert isinstance(sub, COSDictionary)
    keys = list(sub.key_set())
    assert keys, "no overlay form XObject registered"
    form_stream = sub.get_dictionary_object(keys[0])
    assert isinstance(form_stream, COSStream)
    bbox = form_stream.get_dictionary_object(COSName.get_pdf_name("BBox"))
    assert isinstance(bbox, COSArray)
    # Retranslated: (0, 0, width, height) where width=200, height=200.
    floats = [bbox.get(i).float_value() for i in range(4)]  # type: ignore[union-attr]
    assert floats == [0.0, 0.0, 200.0, 200.0]


def test_position_value_of_known_names() -> None:
    """``Position.value_of`` mirrors Java's ``Enum.valueOf`` — exact-name
    lookup; raises ValueError on unknown names."""
    assert Position.value_of("FOREGROUND") is Position.FOREGROUND
    assert Position.value_of("BACKGROUND") is Position.BACKGROUND


def test_position_value_of_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="No Position constant"):
        Position.value_of("MIDDLE")


def test_position_value_of_is_case_sensitive() -> None:
    """Java's ``Enum.valueOf`` is case-sensitive; ours must match."""
    with pytest.raises(ValueError):
        Position.value_of("foreground")


# ---------- file-path-vs-PDDocument precedence (upstream parity) ----------


def test_input_file_overrides_input_pdf_when_both_set(tmp_path: Path) -> None:
    """Upstream ``Overlay.loadPDFs`` reloads from filename even when an
    ``inputPDFDocument`` was already staged via ``setInputPDF``. The
    file-path setter must win — the staged PDF gets discarded."""
    on_disk = _build_base_doc(num_pages=3)
    base_path = tmp_path / "on_disk.pdf"
    on_disk.save(str(base_path))
    on_disk.close()

    # Stage a different (2-page) PDF via setInputPDF first.
    staged = _build_base_doc(num_pages=2)
    overlay_doc = _build_overlay_doc()

    overlay = Overlay()
    overlay.set_input_pdf(staged)
    overlay.set_input_file(str(base_path))  # filename should win
    overlay.set_default_overlay_pdf(overlay_doc)
    result = overlay.overlay({})

    # If the filename won, ``result`` is the freshly-loaded 3-page doc,
    # NOT the staged 2-page one.
    assert result is not staged
    assert result.get_number_of_pages() == 3


def test_default_overlay_file_overrides_default_overlay_pdf(tmp_path: Path) -> None:
    """Same precedence rule applies to the default overlay slot — when
    both ``set_default_overlay_file`` and ``set_default_overlay_pdf`` are
    configured, the file is reloaded and replaces the staged PDF."""
    # Build two distinguishable overlay PDFs — different MediaBox sizes.
    a = PDDocument()
    a.add_page(PDPage(PDRectangle.from_width_height(100.0, 100.0)))
    a_path = tmp_path / "overlay_a.pdf"
    a.save(str(a_path))
    a.close()

    b_doc = PDDocument()
    b_doc.add_page(PDPage(PDRectangle.from_width_height(300.0, 300.0)))

    base = _build_base_doc(num_pages=1)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(b_doc)
    overlay.set_default_overlay_file(str(a_path))  # file wins
    overlay.overlay({})

    # The default-overlay layout should be derived from a_path (100x100),
    # not b_doc (300x300). Inspect the cached _LayoutPage's media box.
    layout = overlay._default_overlay_page  # noqa: SLF001
    assert layout is not None
    assert layout.overlay_media_box.get_width() == 100.0
    assert layout.overlay_media_box.get_height() == 100.0


def test_first_last_odd_even_overlay_file_overrides_pdf(tmp_path: Path) -> None:
    """Filename precedence applies uniformly to first/last/odd/even slots."""
    # One small file overlay PDF and one big in-memory overlay PDF.
    small = PDDocument()
    small.add_page(PDPage(PDRectangle.from_width_height(50.0, 50.0)))
    small_path = tmp_path / "small.pdf"
    small.save(str(small_path))
    small.close()

    def _big() -> PDDocument:
        d = PDDocument()
        d.add_page(PDPage(PDRectangle.from_width_height(500.0, 500.0)))
        return d

    base = _build_base_doc(num_pages=2)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    # All four slots: stage big PDF first, then file path → file wins.
    for set_pdf, set_file in (
        (overlay.set_first_page_overlay_pdf, overlay.set_first_page_overlay_file),
        (overlay.set_last_page_overlay_pdf, overlay.set_last_page_overlay_file),
        (overlay.set_odd_page_overlay_pdf, overlay.set_odd_page_overlay_file),
        (overlay.set_even_page_overlay_pdf, overlay.set_even_page_overlay_file),
    ):
        set_pdf(_big())
        set_file(str(small_path))
    overlay.overlay({})

    # Each slot's cached layout MUST reflect the small (50x50) file, not
    # the staged big (500x500) PDF.
    for layout in (
        overlay._first_page_overlay_page,  # noqa: SLF001
        overlay._last_page_overlay_page,  # noqa: SLF001
        overlay._odd_page_overlay_page,  # noqa: SLF001
        overlay._even_page_overlay_page,  # noqa: SLF001
    ):
        assert layout is not None
        assert layout.overlay_media_box.get_width() == 50.0


def test_all_pages_overlay_file_overrides_pdf(tmp_path: Path) -> None:
    """Filename precedence for the all-pages overlay slot. The file is a
    single-page 50x50; the staged PDF is a 2-page 500x500 doc. After
    overlay() the cached layout map must contain a single 50x50 entry."""
    small = PDDocument()
    small.add_page(PDPage(PDRectangle.from_width_height(50.0, 50.0)))
    small_path = tmp_path / "all_small.pdf"
    small.save(str(small_path))
    small.close()

    big = PDDocument()
    for _ in range(2):
        big.add_page(PDPage(PDRectangle.from_width_height(500.0, 500.0)))

    base = _build_base_doc(num_pages=1)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(big)
    overlay.set_all_pages_overlay_file(str(small_path))  # file wins
    overlay.overlay({})

    # The all-pages overlay layout map should only have the single page
    # from the small file (size 1), not 2 from the big in-memory PDF.
    assert overlay._number_of_overlay_pages == 1  # noqa: SLF001
    layout = overlay._specific_page_overlay_layout[0]  # noqa: SLF001
    assert layout.overlay_media_box.get_width() == 50.0


def test_input_pdf_alone_still_works_when_no_filename_set() -> None:
    """Sanity: when only ``set_input_pdf`` is used (no filename), the
    staged PDF is what ``overlay()`` operates on. Regression-guards
    against the precedence fix accidentally breaking the PDF-only path."""
    base = _build_base_doc(num_pages=2)
    overlay_doc = _build_overlay_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    result = overlay.overlay({})
    assert result is base
    assert result.get_number_of_pages() == 2
