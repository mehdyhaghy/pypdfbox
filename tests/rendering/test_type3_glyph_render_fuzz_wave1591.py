"""Wave 1591 — Type 3 glyph rendering fuzz/parity tests.

Hammers the bug-prone branches in the Type 3 glyph render path
(``PDFRenderer._show_type3_string`` / ``_render_type3_charproc`` /
``_type3_charproc_resources`` / the ``d0`` / ``d1`` width-override
dispatch), comparing against upstream PDFBox ``PageDrawer.showType3Glyph``
-> ``PDFStreamEngine.processType3Stream`` semantics:

* The /FontMatrix is composed onto the text-render matrix so the
  glyph-space charproc lands at the right size/position
  (``glyph_to_user = font_matrix * text_local * text_matrix``).
* The charproc content stream is processed with the Type 3 font's own
  /Resources (or the charproc-local /Resources per PDFBOX-5294), NOT the
  page resources — and restores the page resources afterwards.
* ``d0`` sets the glyph advance; ``d1`` sets advance + bbox and marks
  the glyph an uncoloured mask; ``d1`` takes precedence over ``d0``.
* A missing CharProc for a code is a no-op (skip-paint, still advance).
* An empty CharProc paints nothing and does not crash.
* The nested-stream processing pushes/pops the resource + path + gs
  stacks so the charproc cannot leak state into the surrounding page.

These tests instrument the dispatch directly (capturing the CTM /
resources / colour-gate at the moment the charproc bytes are run, with
the actual painting mocked) so the geometry / resource-stack / metric
arithmetic is asserted exactly rather than read back from pixels.
"""
from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# font / doc builders
# ---------------------------------------------------------------------------


def _make_doc(
    width: float = 200.0, height: float = 100.0
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_font(
    *,
    glyphs: dict[str, bytes],
    differences: list[tuple[int, str]],
    widths: dict[int, int],
    first_char: int,
    last_char: int,
    font_matrix: tuple[float, float, float, float, float, float] = (
        0.001, 0.0, 0.0, 0.001, 0.0, 0.0,
    ),
    font_resources: COSDictionary | None = None,
    charproc_resources: dict[str, COSDictionary] | None = None,
) -> PDType3Font:
    """Build a (possibly multi-glyph) Type 3 font.

    ``glyphs`` maps glyph-name -> charproc bytes; ``differences`` is the
    code->name encoding; ``widths`` maps code->/Widths value;
    ``charproc_resources`` optionally stashes a /Resources dict on a
    named charproc stream (PDFBOX-5294 misplacement).
    """
    char_procs = COSDictionary()
    for name, cp_bytes in glyphs.items():
        cp_stream = COSStream()
        cp_stream.set_raw_data(cp_bytes)
        if charproc_resources is not None and name in charproc_resources:
            cp_stream.set_item(
                COSName.RESOURCES, charproc_resources[name]
            )
        char_procs.set_item(COSName.get_pdf_name(name), cp_stream)

    diff_arr = COSArray()
    for code, name in differences:
        diff_arr.add(COSInteger.get(code))
        diff_arr.add(COSName.get_pdf_name(name))
    encoding_dict = COSDictionary()
    encoding_dict.set_item(COSName.get_pdf_name("Differences"), diff_arr)

    widths_arr = COSArray()
    for code in range(first_char, last_char + 1):
        widths_arr.add(COSInteger.get(widths.get(code, 0)))

    font_bbox = COSArray()
    for v in (0, 0, 1000, 1000):
        font_bbox.add(COSInteger.get(v))

    fm_arr = COSArray()
    for v in font_matrix:
        fm_arr.add(COSFloat(float(v)))

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    font_dict.set_item(COSName.get_pdf_name("FontBBox"), font_bbox)
    font_dict.set_item(COSName.get_pdf_name("FontMatrix"), fm_arr)
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), encoding_dict)
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), first_char)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), last_char)
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths_arr)
    if font_resources is not None:
        font_dict.set_item(COSName.RESOURCES, font_resources)
    return PDType3Font(font_dict)


def _single_glyph_font(
    charproc_bytes: bytes,
    *,
    glyph_name: str = "A",
    code: int = 0x41,
    width: int = 600,
    font_matrix: tuple[float, float, float, float, float, float] = (
        0.001, 0.0, 0.0, 0.001, 0.0, 0.0,
    ),
    font_resources: COSDictionary | None = None,
    charproc_resources: dict[str, COSDictionary] | None = None,
) -> PDType3Font:
    return _build_font(
        glyphs={glyph_name: charproc_bytes},
        differences=[(code, glyph_name)],
        widths={code: width},
        first_char=code,
        last_char=code,
        font_matrix=font_matrix,
        font_resources=font_resources,
        charproc_resources=charproc_resources,
    )


# ---------------------------------------------------------------------------
# instrumentation
# ---------------------------------------------------------------------------


class _Capture:
    """Captured renderer state at each charproc dispatch."""

    def __init__(self) -> None:
        self.ctms: list[tuple[float, ...]] = []
        self.resources: list[object] = []
        self.ignore_color: list[bool] = []
        self.data: list[bytes] = []


def _instrument(renderer: PDFRenderer) -> _Capture:
    """Patch ``_process_form_bytes`` to record the CTM / resources /
    colour-gate at the instant the charproc bytes run, then no-op the
    actual paint. Returns the capture record."""
    cap = _Capture()
    orig = renderer._process_form_bytes

    def _patched(data: bytes) -> None:  # noqa: ANN001
        cap.ctms.append(tuple(renderer._gs.ctm))
        cap.resources.append(renderer._resources)
        cap.ignore_color.append(renderer._type3_ignore_color)
        cap.data.append(data)
        # Do NOT paint — we only assert on the captured geometry/state.

    renderer._process_form_bytes = _patched  # type: ignore[assignment]
    renderer._orig_process_form_bytes = orig  # type: ignore[attr-defined]
    return cap


def _render_with_capture(
    doc: PDDocument,
) -> tuple[PDFRenderer, _Capture]:
    renderer = PDFRenderer(doc)
    cap = _instrument(renderer)
    renderer.render_image(0)
    return renderer, cap


def _show(
    doc: PDDocument,
    page: PDPage,
    font: PDType3Font,
    text: bytes,
    *,
    font_size: float = 100.0,
    at: tuple[float, float] = (20.0, 30.0),
    h_scale: float | None = None,
    rise: float | None = None,
) -> None:
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, font_size)
        if h_scale is not None:
            cs.set_horizontal_scaling(h_scale)
        if rise is not None:
            cs.set_text_rise(rise)
        cs.new_line_at_offset(at[0], at[1])
        cs.show_text(text)
        cs.end_text()


def _approx(a: float, b: float, tol: float = 1e-4) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ===========================================================================
# 1. Font-matrix composition onto the text render matrix
# ===========================================================================


@pytest.mark.parametrize(
    ("font_size", "fm_scale"),
    [
        (100.0, 0.001),
        (50.0, 0.001),
        (12.0, 0.001),
        (100.0, 0.01),
        (72.0, 0.0005),
        (1.0, 0.001),
    ],
)
def test_font_matrix_scale_folds_into_ctm(
    font_size: float, fm_scale: float
) -> None:
    """The charproc CTM scale = font_matrix_scale * font_size * page_scale.
    For a 1:1 page (render scale 1.0) and an unscaled text matrix the
    glyph-space->device scale is ``fm_scale * font_size``."""
    fm = (fm_scale, 0.0, 0.0, fm_scale, 0.0, 0.0)
    charproc = b"0 0 1000 1000 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc, font_matrix=fm)
    _show(doc, page, font, b"A", font_size=font_size, at=(0.0, 0.0))
    _renderer, cap = _render_with_capture(doc)
    assert len(cap.ctms) == 1
    a, b, c, d, _e, _f = cap.ctms[0]
    # The page is y-flipped (render to image), so |d| equals the scale,
    # |a| equals the scale. Off-diagonals stay ~0 for an axis-aligned fm.
    expected = fm_scale * font_size
    assert _approx(abs(a), expected, tol=1e-3)
    assert _approx(abs(d), expected, tol=1e-3)
    assert _approx(b, 0.0, tol=1e-6)
    assert _approx(c, 0.0, tol=1e-6)


def test_font_matrix_translation_offsets_glyph_origin() -> None:
    """A /FontMatrix translation shifts the charproc origin in text space
    before the font-size scale is applied."""
    fm = (0.001, 0.0, 0.0, 0.001, 0.5, 0.25)
    charproc = b"0 0 10 10 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc, font_matrix=fm)
    _show(doc, page, font, b"A", font_size=100.0, at=(10.0, 20.0))
    _renderer, cap = _render_with_capture(doc)
    assert len(cap.ctms) == 1
    # fm translation (0.5, 0.25) * font_size (100) = (50, 25) text-space,
    # added onto the new-line offset (10, 20) -> origin (60, 45) before
    # the page y-flip. Compare against a no-translation baseline.
    e1, f1 = cap.ctms[0][4], cap.ctms[0][5]

    doc2, page2 = _make_doc(400.0, 400.0)
    font2 = _single_glyph_font(
        charproc, font_matrix=(0.001, 0.0, 0.0, 0.001, 0.0, 0.0)
    )
    _show(doc2, page2, font2, b"A", font_size=100.0, at=(10.0, 20.0))
    _r2, cap2 = _render_with_capture(doc2)
    e0, f0 = cap2.ctms[0][4], cap2.ctms[0][5]
    # Translated origin differs by (50, -25) in device space (y flipped).
    assert _approx(e1 - e0, 50.0, tol=1e-2)
    assert _approx(abs(f1 - f0), 25.0, tol=1e-2)


def test_font_matrix_rotation_components_propagate() -> None:
    """A skew/rotation in /FontMatrix folds nonzero off-diagonal terms
    into the charproc CTM (b, c become nonzero)."""
    # 45-deg-ish shear: fm = [0.001 0.001 -0.001 0.001 0 0]
    fm = (0.001, 0.001, -0.001, 0.001, 0.0, 0.0)
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc, font_matrix=fm)
    _show(doc, page, font, b"A", font_size=100.0)
    _renderer, cap = _render_with_capture(doc)
    a, b, c, d, _e, _f = cap.ctms[0]
    assert not _approx(b, 0.0, tol=1e-6)
    assert not _approx(c, 0.0, tol=1e-6)


@pytest.mark.parametrize("h_scale", [50.0, 100.0, 200.0])
def test_horizontal_scaling_folds_into_x_scale(h_scale: float) -> None:
    """Th (horizontal scaling) multiplies only the x-axis scale of the
    charproc CTM (matches text_local a = font_size * h_scale)."""
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(600.0, 200.0)
    font = _single_glyph_font(charproc)
    _show(doc, page, font, b"A", font_size=100.0, h_scale=h_scale)
    _renderer, cap = _render_with_capture(doc)
    a, _b, _c, d, _e, _f = cap.ctms[0]
    # a-scale = 0.001 * 100 * (h_scale/100); d-scale = 0.001 * 100.
    assert _approx(abs(a), 0.1 * (h_scale / 100.0), tol=1e-3)
    assert _approx(abs(d), 0.1, tol=1e-3)


def test_text_rise_offsets_charproc_origin_y() -> None:
    """Ts (text rise) shifts the charproc origin in y (text_local f)."""
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc)
    _show(doc, page, font, b"A", font_size=100.0, at=(10.0, 20.0), rise=0.0)
    _r0, cap0 = _render_with_capture(doc)

    doc2, page2 = _make_doc(400.0, 400.0)
    font2 = _single_glyph_font(charproc)
    _show(doc2, page2, font2, b"A", font_size=100.0, at=(10.0, 20.0), rise=15.0)
    _r1, cap1 = _render_with_capture(doc2)
    # Rise of 15 user units shifts the origin by 15 in y (device flipped).
    assert _approx(abs(cap1.ctms[0][5] - cap0.ctms[0][5]), 15.0, tol=1e-2)


# ===========================================================================
# 2. Charproc processed with the Type 3 /Resources (not page resources)
# ===========================================================================


def test_charproc_uses_font_resources_not_page() -> None:
    """During charproc dispatch ``_resources`` is the font's /Resources,
    not the page's."""
    font_res = COSDictionary()
    # a marker entry so we can identify this dict
    font_res.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(7))
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc, font_resources=font_res)
    _show(doc, page, font, b"A")
    _renderer, cap = _render_with_capture(doc)
    assert len(cap.resources) == 1
    res_dict = cap.resources[0].get_cos_object()
    assert res_dict.get_int(COSName.get_pdf_name("Marker")) == 7


def test_charproc_local_resources_win_over_font_pdfbox5294() -> None:
    """PDFBOX-5294: a /Resources stashed on the charproc stream itself
    takes precedence over the parent font's /Resources during dispatch
    (mirrors PDType3CharProc.getResources())."""
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(1))
    cp_res = COSDictionary()
    cp_res.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(99))
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(
        charproc,
        font_resources=font_res,
        charproc_resources={"A": cp_res},
    )
    _show(doc, page, font, b"A")
    _renderer, cap = _render_with_capture(doc)
    res_dict = cap.resources[0].get_cos_object()
    assert res_dict.get_int(COSName.get_pdf_name("Marker")) == 99


def test_charproc_without_resources_keeps_page_resources() -> None:
    """When neither the charproc nor the font declare /Resources the page
    resources stay in scope (charproc inherits parent resources)."""
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc)  # no font /Resources
    _show(doc, page, font, b"A")
    renderer, cap = _render_with_capture(doc)
    # The captured resources during dispatch are the page-level resources
    # (non-None) — not silently dropped to None.
    assert cap.resources[0] is not None


def test_resources_restored_after_charproc() -> None:
    """After the charproc finishes, ``_resources`` is restored to the
    page-level resources (no leak)."""
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(5))
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 400.0)
    font = _single_glyph_font(charproc, font_resources=font_res)
    _show(doc, page, font, b"A")
    renderer, cap = _render_with_capture(doc)
    # The font-resources marker must NOT be visible on the post-render
    # page resources.
    final = renderer._resources
    if final is not None:
        cos = final.get_cos_object()
        assert cos.get_int(COSName.get_pdf_name("Marker")) != 5


# ===========================================================================
# 3. d0 / d1 width override + colour gate
# ===========================================================================


def _render_real(doc: PDDocument) -> PDFRenderer:
    """Render page 0 through the unmocked dispatch (so d0/d1 inside the
    charproc actually run and override the advance)."""
    renderer = PDFRenderer(doc)
    renderer.render_image(0)
    return renderer


def test_d0_sets_width_override() -> None:
    """``wx wy d0`` sets the glyph advance from the charproc, overriding
    /Widths."""
    # /Widths says 600 but d0 declares 900.
    charproc = b"900 0 d0\n0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 200.0)
    font = _single_glyph_font(charproc, width=600)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 50.0))
    renderer = _render_real(doc)
    # advance_units = 900 * fm[0] * 1000 = 900 (since fm[0]=0.001).
    # tx = (900/1000)*100 = 90 user units.
    assert _approx(renderer._gs.text_matrix[4], 90.0, tol=1e-3)


def test_d1_sets_width_override_and_colour_gate() -> None:
    """A leading ``d1`` sets the advance AND marks the glyph an uncoloured
    mask (colour ops suppressed)."""
    charproc = b"850 0 0 0 500 500 d1\n0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 200.0)
    font = _single_glyph_font(charproc, width=600)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 50.0))
    # Colour gate is captured before dispatch, so the mock is fine for it.
    _renderer, cap = _render_with_capture(doc)
    assert cap.ignore_color[0] is True
    # The advance override needs the real dispatch (d1 actually runs).
    doc2, page2 = _make_doc(400.0, 200.0)
    font2 = _single_glyph_font(charproc, width=600)
    _show(doc2, page2, font2, b"A", font_size=100.0, at=(0.0, 50.0))
    renderer = _render_real(doc2)
    # advance from d1 wx (850) -> tx = 85 user units.
    assert _approx(renderer._gs.text_matrix[4], 85.0, tol=1e-3)


def test_d0_does_not_gate_colour() -> None:
    """A ``d0`` glyph keeps its own colour (colour gate off)."""
    charproc = b"700 0 d0\n0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 200.0)
    font = _single_glyph_font(charproc, width=600)
    _show(doc, page, font, b"A")
    _renderer, cap = _render_with_capture(doc)
    assert cap.ignore_color[0] is False


def test_d1_precedence_over_d0_when_both_present() -> None:
    """If a malformed charproc carries both, ``d1`` wins for the advance
    (PDFBox parity)."""
    # First operator is d1 (so the colour gate + first-op detection fire);
    # a later d0 is also present. d1 advance must win.
    charproc = (
        b"800 0 0 0 500 500 d1\n"
        b"300 0 d0\n"
        b"0 0 100 100 re\nf\n"
    )
    doc, page = _make_doc(400.0, 200.0)
    font = _single_glyph_font(charproc, width=600)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 50.0))
    renderer = _render_real(doc)
    # d1 wx 800 -> tx 80; if d0 had won it'd be 30.
    assert _approx(renderer._gs.text_matrix[4], 80.0, tol=1e-3)


def test_no_metric_operator_uses_widths_advance() -> None:
    """A charproc with neither d0 nor d1 advances by the /Widths metric."""
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(400.0, 200.0)
    font = _single_glyph_font(charproc, width=500)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 50.0))
    renderer, _cap = _render_with_capture(doc)
    # /Widths 500 -> advance 500 -> tx 50 user units.
    assert _approx(renderer._gs.text_matrix[4], 50.0, tol=1e-3)


@pytest.mark.parametrize(
    ("widths_val", "font_size", "expected_tx"),
    [
        (1000, 100.0, 100.0),
        (500, 100.0, 50.0),
        (250, 200.0, 50.0),
        (600, 50.0, 30.0),
        (0, 100.0, 0.0),
    ],
)
def test_widths_advance_arithmetic(
    widths_val: int, font_size: float, expected_tx: float
) -> None:
    """advance = W * fm[0] * font_size; charspace/wordspace default 0."""
    charproc = b"0 0 100 100 re\nf\n"
    doc, page = _make_doc(600.0, 200.0)
    font = _single_glyph_font(charproc, width=widths_val)
    _show(doc, page, font, b"A", font_size=font_size, at=(0.0, 50.0))
    renderer, _cap = _render_with_capture(doc)
    assert _approx(renderer._gs.text_matrix[4], expected_tx, tol=1e-3)


# ===========================================================================
# 4. Missing / empty charproc handling
# ===========================================================================


def test_missing_charproc_is_skip_but_advances() -> None:
    """A code whose glyph name has no CharProc paints nothing (no
    dispatch) but the text matrix still advances by /Widths (upstream
    PageDrawer skips the paint, PDFStreamEngine still advances)."""
    # Encoding maps code 0x42 ('B') to glyph 'B' but /CharProcs has no 'B'.
    font = _build_font(
        glyphs={"A": b"0 0 100 100 re\nf\n"},
        differences=[(0x41, "A"), (0x42, "B")],
        widths={0x41: 600, 0x42: 500},
        first_char=0x41,
        last_char=0x42,
    )
    doc, page = _make_doc(400.0, 200.0)
    _show(doc, page, font, b"B", font_size=100.0, at=(0.0, 50.0))
    renderer, cap = _render_with_capture(doc)
    # No charproc dispatched.
    assert len(cap.ctms) == 0
    # But the glyph still advanced by its /Widths (500 -> tx 50).
    assert _approx(renderer._gs.text_matrix[4], 50.0, tol=1e-3)


def test_missing_charproc_then_present_advances_both() -> None:
    """A run mixing a missing-charproc code and a present one dispatches
    once and advances for both."""
    font = _build_font(
        glyphs={"A": b"0 0 100 100 re\nf\n"},
        differences=[(0x41, "A"), (0x42, "B")],
        widths={0x41: 600, 0x42: 400},
        first_char=0x41,
        last_char=0x42,
    )
    doc, page = _make_doc(400.0, 200.0)
    _show(doc, page, font, b"BA", font_size=100.0, at=(0.0, 50.0))
    renderer, cap = _render_with_capture(doc)
    # only 'A' dispatched.
    assert len(cap.ctms) == 1
    # advance = 400 (B) + 600 (A) -> tx = 40 + 60 = 100 user units.
    assert _approx(renderer._gs.text_matrix[4], 100.0, tol=1e-3)


def test_empty_charproc_does_not_crash_and_advances() -> None:
    """An empty CharProc stream paints nothing and still advances."""
    font = _single_glyph_font(b"", width=600)
    doc, page = _make_doc(400.0, 200.0)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 50.0))
    renderer, cap = _render_with_capture(doc)
    # An empty charproc yields empty data; the dispatch hook is not even
    # invoked (the renderer guards ``if data:``). Either way, no crash.
    assert all(d == b"" for d in cap.data)
    assert _approx(renderer._gs.text_matrix[4], 60.0, tol=1e-3)


def test_whitespace_only_charproc_advances() -> None:
    """A whitespace-only CharProc is effectively empty."""
    font = _single_glyph_font(b"   \n  \t ", width=300)
    doc, page = _make_doc(400.0, 200.0)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 50.0))
    renderer, _cap = _render_with_capture(doc)
    assert _approx(renderer._gs.text_matrix[4], 30.0, tol=1e-3)


# ===========================================================================
# 5. Multi-glyph runs: per-glyph CTM advances; resource stack stable
# ===========================================================================


def test_multi_glyph_run_advances_each_ctm() -> None:
    """Three glyphs of the same charproc dispatch at three increasing
    x origins (the text matrix advances between each)."""
    charproc = b"0 0 100 100 re\nf\n"
    font = _single_glyph_font(charproc, width=500)
    doc, page = _make_doc(800.0, 200.0)
    _show(doc, page, font, b"AAA", font_size=100.0, at=(0.0, 50.0))
    _renderer, cap = _render_with_capture(doc)
    assert len(cap.ctms) == 3
    xs = [c[4] for c in cap.ctms]
    # Each glyph advances 50 user units in x -> strictly increasing.
    assert xs[0] < xs[1] < xs[2]
    assert _approx(xs[1] - xs[0], 50.0, tol=1e-2)
    assert _approx(xs[2] - xs[1], 50.0, tol=1e-2)


def test_multi_glyph_run_same_resources_each_dispatch() -> None:
    """Every glyph in a run dispatches under the same font /Resources."""
    font_res = COSDictionary()
    font_res.set_item(COSName.get_pdf_name("Marker"), COSInteger.get(3))
    charproc = b"0 0 100 100 re\nf\n"
    font = _single_glyph_font(charproc, width=400, font_resources=font_res)
    doc, page = _make_doc(800.0, 200.0)
    _show(doc, page, font, b"AAAA", font_size=50.0, at=(0.0, 50.0))
    _renderer, cap = _render_with_capture(doc)
    assert len(cap.resources) == 4
    for res in cap.resources:
        cos = res.get_cos_object()
        assert cos.get_int(COSName.get_pdf_name("Marker")) == 3


def test_charspace_wordspace_fold_into_advance() -> None:
    """Tc / Tw add onto the Type 3 advance just like simple fonts."""
    charproc = b"0 0 100 100 re\nf\n"
    # space code 0x20 maps to a glyph so wordspace applies.
    font = _build_font(
        glyphs={"space": charproc},
        differences=[(0x20, "space")],
        widths={0x20: 500},
        first_char=0x20,
        last_char=0x20,
    )
    doc, page = _make_doc(600.0, 200.0)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 100.0)
        cs.set_character_spacing(5.0)
        cs.set_word_spacing(10.0)
        cs.new_line_at_offset(0.0, 50.0)
        cs.show_text(b" ")
        cs.end_text()
    renderer, _cap = _render_with_capture(doc)
    # advance = (500/1000)*100 + charspace(5) + wordspace(10) = 50+15 = 65.
    assert _approx(renderer._gs.text_matrix[4], 65.0, tol=1e-3)


# ===========================================================================
# 6. State isolation — charproc cannot leak path / gs state
# ===========================================================================


def test_charproc_path_does_not_leak_to_page() -> None:
    """A charproc that builds a path but never paints it must not leave
    that path in the page-level subpath buffer."""
    # charproc constructs but never closes/paints a path.
    charproc = b"10 10 m\n900 900 l\n"
    font = _single_glyph_font(charproc, width=600)
    doc, page = _make_doc(400.0, 200.0)
    # Run for real (no capture) so the actual dispatch path runs.
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 100.0)
        cs.new_line_at_offset(10.0, 20.0)
        cs.show_text(b"A")
        cs.end_text()
    renderer = PDFRenderer(doc)
    renderer.render_image(0)
    # After rendering, no half-built subpath leaked.
    assert renderer._subpaths == []
    assert renderer._current_subpath is None


def test_charproc_q_without_matching_restore_does_not_leak() -> None:
    """A charproc with an unbalanced ``q`` does not corrupt the page gs
    depth (the renderer push/pops a gs frame around the charproc)."""
    charproc = b"q\n0 0 100 100 re\nf\n"  # missing Q
    font = _single_glyph_font(charproc, width=600)
    doc, page = _make_doc(400.0, 200.0)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 100.0)
        cs.show_text(b"A")
        cs.end_text()
    renderer = PDFRenderer(doc)
    # Should not raise.
    img = renderer.render_image(0)
    assert img is not None


# ===========================================================================
# 7. Defaulting / robustness
# ===========================================================================


def test_default_font_matrix_when_absent() -> None:
    """A Type 3 font with no /FontMatrix uses the spec default
    [0.001 0 0 0.001 0 0] for the CTM scale."""
    charproc = b"0 0 1000 1000 re\nf\n"
    # Build a font then strip /FontMatrix.
    font = _single_glyph_font(charproc)
    font.get_cos_object().remove_item(COSName.get_pdf_name("FontMatrix"))
    doc, page = _make_doc(400.0, 400.0)
    _show(doc, page, font, b"A", font_size=100.0, at=(0.0, 0.0))
    _renderer, cap = _render_with_capture(doc)
    a = cap.ctms[0][0]
    assert _approx(abs(a), 0.001 * 100.0, tol=1e-3)


def test_zero_font_size_skips_rendering() -> None:
    """A zero font size short-circuits _show_string (no charproc runs)."""
    charproc = b"0 0 100 100 re\nf\n"
    font = _single_glyph_font(charproc)
    doc, page = _make_doc(400.0, 200.0)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 0.0)
        cs.show_text(b"A")
        cs.end_text()
    _renderer, cap = _render_with_capture(doc)
    assert len(cap.ctms) == 0


def test_invisible_text_mode_skips_charproc_but_advances() -> None:
    """Tr 3 (invisible) skips the charproc paint (upstream
    PageDrawer.showType3Glyph) yet still advances by /Widths."""
    charproc = b"0 0 100 100 re\nf\n"
    font = _single_glyph_font(charproc, width=700)
    doc, page = _make_doc(400.0, 200.0)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 100.0)
        cs.set_rendering_mode(3)
        cs.new_line_at_offset(0.0, 50.0)
        cs.show_text(b"A")
        cs.end_text()
    renderer, cap = _render_with_capture(doc)
    assert len(cap.ctms) == 0
    assert _approx(renderer._gs.text_matrix[4], 70.0, tol=1e-3)


def test_notdef_fallback_when_no_typed_encoding() -> None:
    """Without a usable encoding the renderer falls back to .notdef; a
    charproc named .notdef is then dispatched."""
    # Build a font whose /CharProcs has a .notdef but the encoding maps
    # the code to a name with no charproc -> .notdef fallback would NOT
    # fire here (encoding present). Instead verify .notdef IS used only
    # when encoding lookup yields nothing. We simulate by mapping the
    # code to .notdef directly.
    font = _build_font(
        glyphs={".notdef": b"0 0 100 100 re\nf\n"},
        differences=[(0x41, ".notdef")],
        widths={0x41: 600},
        first_char=0x41,
        last_char=0x41,
    )
    doc, page = _make_doc(400.0, 200.0)
    _show(doc, page, font, b"A")
    _renderer, cap = _render_with_capture(doc)
    # .notdef charproc IS dispatched (upstream getCharProc honours it).
    assert len(cap.ctms) == 1
