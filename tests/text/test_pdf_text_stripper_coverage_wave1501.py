"""Coverage round-out for :mod:`pypdfbox.text.pdf_text_stripper` (wave 1501).

Pins reachable behavioural spans of :class:`PDFTextStripper` that the
byte-exact oracle suites and the hand-written stripper tests did not already
exercise:

* form-XObject (``Do``) text recursion — the form body's show-text emits
  into the page text, with the form's ``/Matrix`` folded onto the CTM and the
  form's own ``/Resources`` pushed for the duration (``_show_form_xobject`` /
  ``_current_resources`` active-resources branch);
* a bare ``BMC`` marked-content tag (no property list);
* the ``/ActualText``-suppressed later run under ``ignore_content_stream_space_glyphs``
  (cursor advances, no position emitted);
* text rise (``Ts``) folded through the ignore-space emission path;
* ``_compute_width_of_space`` honouring a font's ``get_glyph_width(32)``;
* the mixed-direction prong of ``_compare_reading_order``.

These assertions are deterministic and do not contradict the byte-exact
suites (eu-001, poems-beads, with_outline, vertical, rotations, by-area).
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text import PDFTextStripper, TextPosition

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _page_with_content(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _make_form_xobject(
    body: bytes, *, matrix: list[float] | None = None
) -> PDFormXObject:
    stream = COSStream()
    stream.set_data(body)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    stream.set_item(
        COSName.get_pdf_name("BBox"),
        COSArray([COSInteger.get(v) for v in (0, 0, 200, 50)]),
    )
    form = PDFormXObject(stream)
    if matrix is not None:
        form.set_matrix(matrix)
    return form


# ---------------------------------------------------------------------------
# form-XObject (Do) text recursion
# ---------------------------------------------------------------------------


def test_do_recurses_into_form_xobject_text() -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        form = _make_form_xobject(b"BT /F0 12 Tf 10 20 Td (FormText) Tj ET")
        resources = PDResources()
        key = resources.add_x_object(form)
        page.set_resources(resources)
        content = COSStream()
        content.set_data(
            b"q 1 0 0 1 100 700 cm /" + key.get_name().encode("ascii") + b" Do Q"
        )
        page.set_contents(content)
        doc.add_page(page)
        out = PDFTextStripper().get_text(doc)
        assert out == "FormText\n"
    finally:
        doc.close()


def test_do_form_xobject_with_own_resources_and_matrix() -> None:
    # The form carries its own /Resources (its /F0 ToUnicode is independent of
    # the host page) and a non-identity /Matrix that is folded onto the CTM.
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        form = _make_form_xobject(
            b"BT /F0 12 Tf 0 0 Td (InForm) Tj ET", matrix=[1.0, 0.0, 0.0, 1.0, 5.0, 5.0]
        )
        form_resources = PDResources()
        form.get_cos_object().set_item(
            COSName.get_pdf_name("Resources"), form_resources.get_cos_object()
        )
        resources = PDResources()
        key = resources.add_x_object(form)
        page.set_resources(resources)
        content = COSStream()
        content.set_data(
            b"q 1 0 0 1 100 700 cm /" + key.get_name().encode("ascii") + b" Do Q"
        )
        page.set_contents(content)
        doc.add_page(page)
        out = PDFTextStripper().get_text(doc)
        assert out == "InForm\n"
    finally:
        doc.close()


def test_do_image_xobject_emits_no_text() -> None:
    # A /Subtype /Image XObject carries no text; Do must skip it silently.
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        img = COSStream()
        img.set_data(b"\x00\x01\x02")
        img.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
        img.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
        img.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
        img.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
        resources = PDResources()
        resources.put(
            COSName.get_pdf_name("XObject"), COSName.get_pdf_name("Im0"), img
        )
        page.set_resources(resources)
        content = COSStream()
        content.set_data(b"BT /F0 12 Tf 100 700 Td (Visible) Tj ET q /Im0 Do Q")
        page.set_contents(content)
        doc.add_page(page)
        out = PDFTextStripper().get_text(doc)
        assert out == "Visible\n"
    finally:
        doc.close()


def test_do_missing_xobject_is_a_noop() -> None:
    # A Do referencing an unregistered name must not raise and must not emit.
    doc = PDDocument()
    try:
        page = _page_with_content(
            doc, b"BT /F0 12 Tf 100 700 Td (Only) Tj ET q /Missing Do Q"
        )
        page.set_resources(PDResources())
        out = PDFTextStripper().get_text(doc)
        assert out == "Only\n"
    finally:
        doc.close()


def test_do_form_with_empty_body_is_a_noop() -> None:
    # A form XObject whose content stream is empty contributes no text.
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        form = _make_form_xobject(b"")
        resources = PDResources()
        key = resources.add_x_object(form)
        page.set_resources(resources)
        content = COSStream()
        content.set_data(
            b"BT /F0 12 Tf 100 700 Td (Host) Tj ET "
            b"q /" + key.get_name().encode("ascii") + b" Do Q"
        )
        page.set_contents(content)
        doc.add_page(page)
        assert PDFTextStripper().get_text(doc) == "Host\n"
    finally:
        doc.close()


def test_do_self_referencing_form_hits_recursion_cap() -> None:
    # A form whose body draws itself recurses until the depth guard (50) stops
    # it; the page-level text is unaffected and no exception escapes.
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        form = _make_form_xobject(b"")
        page_resources = PDResources()
        key = page_resources.add_x_object(form)
        form_resources = PDResources()
        self_key = form_resources.add_x_object(form)
        form.get_cos_object().set_item(
            COSName.get_pdf_name("Resources"), form_resources.get_cos_object()
        )
        form.get_cos_object().set_data(
            b"q /" + self_key.get_name().encode("ascii") + b" Do Q"
        )
        page.set_resources(page_resources)
        content = COSStream()
        content.set_data(
            b"BT /F0 12 Tf 100 700 Td (Outer) Tj ET "
            b"q /" + key.get_name().encode("ascii") + b" Do Q"
        )
        page.set_contents(content)
        doc.add_page(page)
        assert PDFTextStripper().get_text(doc) == "Outer\n"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# /Rotate 180 page coordinate fold
# ---------------------------------------------------------------------------


def test_rotate_180_page_extracts_text() -> None:
    # /Rotate 180 drives the 180-degree prong of _apply_page_rotation
    # (x_adj = pageWidth - x, y_adj = pageHeight - y).
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        page.set_rotation(180)
        content = COSStream()
        content.set_data(b"BT /F0 12 Tf 100 700 Td (Rot180) Tj ET")
        page.set_contents(content)
        doc.add_page(page)
        assert PDFTextStripper().get_text(doc) == "Rot180\n"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# bare BMC marked-content tag
# ---------------------------------------------------------------------------


def test_bmc_bare_tag_does_not_suppress_text() -> None:
    doc = PDDocument()
    try:
        _page_with_content(
            doc, b"/Span BMC BT /F0 12 Tf 100 700 Td (Inside) Tj ET EMC"
        )
        out = PDFTextStripper().get_text(doc)
        assert out == "Inside\n"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# /ActualText suppressed run under ignore-content-stream-space-glyphs
# ---------------------------------------------------------------------------


def test_actual_text_suppressed_run_with_ignore_space() -> None:
    # Two Tj runs inside one /ActualText span: the replacement is emitted once
    # and the second run is suppressed. With ignore-space ON the suppressed
    # branch keeps the cursor advance but emits no position.
    doc = PDDocument()
    try:
        _page_with_content(
            doc,
            b"BT /F0 12 Tf 100 700 Td /Span <</ActualText (Repl)>> BDC "
            b"(AA) Tj (BB) Tj EMC ET",
        )
        s = PDFTextStripper()
        s.set_ignore_content_stream_space_glyphs(True)
        assert s.get_text(doc) == "Repl\n"
    finally:
        doc.close()


def test_text_rise_through_ignore_space_path() -> None:
    # Text rise (Ts) is folded through the ignore-space emission path; spaces
    # are dropped and the rise does not corrupt the surviving text.
    doc = PDDocument()
    try:
        _page_with_content(
            doc, b"BT /F0 12 Tf 5 Ts 100 700 Td (Hi There) Tj ET"
        )
        s = PDFTextStripper()
        s.set_ignore_content_stream_space_glyphs(True)
        assert s.get_text(doc) == "HiThere\n"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# _compute_width_of_space
# ---------------------------------------------------------------------------


class _SpaceWidthFont:
    def get_glyph_width(self, code: int) -> float:
        return 500.0 if code == 32 else 0.0


class _ZeroSpaceFont:
    def get_glyph_width(self, code: int) -> float:
        return 0.0


class _RaisingSpaceFont:
    def get_glyph_width(self, code: int) -> float:
        raise ValueError("malformed metrics")


def test_compute_width_of_space_uses_glyph_width() -> None:
    # 500/1000 em at fontSize 12 -> 6.0 user-space units.
    assert PDFTextStripper._compute_width_of_space(
        _SpaceWidthFont(), 12.0, fallback=99.0
    ) == 6.0


def test_compute_width_of_space_zero_falls_back() -> None:
    assert PDFTextStripper._compute_width_of_space(
        _ZeroSpaceFont(), 12.0, fallback=99.0
    ) == 99.0


def test_compute_width_of_space_malformed_metrics_falls_back() -> None:
    assert PDFTextStripper._compute_width_of_space(
        _RaisingSpaceFont(), 12.0, fallback=42.0
    ) == 42.0


def test_compute_width_of_space_no_font_falls_back() -> None:
    assert PDFTextStripper._compute_width_of_space(
        None, 12.0, fallback=7.0
    ) == 7.0


# ---------------------------------------------------------------------------
# _compare_reading_order — mixed text direction
# ---------------------------------------------------------------------------


def test_compare_reading_order_orders_by_direction() -> None:
    s = PDFTextStripper()
    horizontal = TextPosition(
        text="a", x=0.0, y=0.0, font_size=12.0, dir=0.0
    )
    rotated = TextPosition(
        text="b", x=0.0, y=0.0, font_size=12.0, dir=90.0
    )
    # Lower direction sorts first; the comparison is antisymmetric.
    assert s._compare_reading_order(horizontal, rotated) == -1
    assert s._compare_reading_order(rotated, horizontal) == 1
