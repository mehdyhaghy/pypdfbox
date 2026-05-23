"""Wave 1387 — /TK (text knockout) per-text-object transparency-group fork.

PDF 32000-1 §9.3.8 + ExtGState entry. When ``/TK`` is **true** (the spec
default) each text object (a single ``BT…ET`` block) is treated as one
shape with respect to compositing — overlapping glyphs in the same text
object do NOT accumulate alpha against each other. When ``/TK`` is
**false** glyphs paint "directly" and overlapping coverage stacks the
source alpha (so two 50%-opaque glyph footprints in overlap render
75% opaque).

Before wave 1387 the renderer carried ``text_knockout`` on the
``_GState`` (wave 1385) and ExtGState's ``/TK`` already propagated
through ``gs`` into that field (wave 1385 / 1386), but the BT/ET paint
loop never forked on the flag — so files declaring ``/TK false`` would
silently use the spec default. This wave wires the actual fork in
:meth:`PDFRenderer._op_begin_text` /
:meth:`PDFRenderer._op_end_text`.

The fork is **only opened** when knockout has a visible effect
(``fill_alpha < 1.0`` or ``stroke_alpha < 1.0`` or non-Normal blend
mode active). For the overwhelmingly-common alpha=1.0 + Normal case
the visible output is identical regardless of TK, so we skip the
sub-canvas allocation to keep the fast path fast.
"""

from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState

# ---------------------------------------------------------------------------
# Tiny helpers — synthesise a minimal TTF + page with overlapping glyphs.
# ---------------------------------------------------------------------------


def _make_doc(width: float = 100.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_square_ttf_bytes() -> bytes:
    """Synthesise a TTF where glyphs A and B are 800x800-em solid squares
    with a 1000-unit advance. Re-uses the same helper pattern as
    ``test_pdf_renderer_text_rendering_mode_wave1385.py``."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({0x41: "A", 0x42: "B"})

    def square_glyph() -> object:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 100))
        pen.lineTo((900, 100))
        pen.lineTo((900, 900))
        pen.lineTo((100, 900))
        pen.closePath()
        return pen.glyph()

    glyphs = {
        ".notdef": TTGlyphPen(None).glyph(),
        "A": square_glyph(),
        "B": square_glyph(),
    }
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(
        {".notdef": (0, 0), "A": (1024, 0), "B": (1024, 0)}
    )
    fb.setupHorizontalHeader(ascent=900, descent=-100)
    fb.setupNameTable({"familyName": "DejaVuSquare", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, usWinAscent=900, usWinDescent=100)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _wrap_ttf(ttf_bytes: bytes):
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
    from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)

    fd_dict = COSDictionary()
    descriptor = PDFontDescriptor(fd_dict)
    descriptor.set_font_file2(font_file2)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("DejaVuSquare"),
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDTrueTypeFont(font_dict)


def _alpha_at(img: Image.Image, x: int, y: int) -> int:
    """Return the *apparent* source alpha at ``(x, y)`` of an RGB image
    rendered against a white backdrop, assuming the source colour is
    pure black ``(0, 0, 0)``. Composited pixel = ``(255*(1-a),)*3`` so
    ``a = 1 - r/255``. Returns 0..255."""
    px = img.getpixel((x, y))
    r = px[0] if isinstance(px, tuple) else px
    # Apparent source alpha as a 0..255 byte.
    return int(round(255 - r))


def _render_two_overlapping_glyphs(
    *, knockout: bool, alpha: float, blend_mode: object | None = None,
) -> Image.Image:
    """Render two overlapping black square glyphs at ``alpha``.

    Glyph layout: 'A' at offset (10, 30), 'B' at offset (35, 30) — at
    font size 50pt these are 50x50 squares, so they overlap by ~25px
    horizontally. The TK flag is set via an ExtGState passed through
    ``gs`` *inside* the BT/ET so the value reaches the GS before the
    first glyph paints.
    """
    doc, page = _make_doc(120.0, 80.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        # Per-text-object knockout + non-stroking alpha. We set both
        # via the same content stream so the renderer sees them as a
        # single ExtGState plumb-through.
        ext = PDExtendedGraphicsState()
        ext.set_text_knockout_flag(knockout)
        ext.set_non_stroking_alpha_constant(alpha)
        if blend_mode is not None:
            ext.set_blend_mode(blend_mode)
        cs.set_graphics_state_parameters(ext)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(10.0, 30.0)
        cs.show_text("A")
        # Second show_text in same BT — overlapping glyph position.
        # Use a relative TD by setting the text matrix again? Simpler:
        # emit a TJ-style explicit second show_text with manual
        # positioning via Tm.
        cs.set_text_matrix(1.0, 0.0, 0.0, 1.0, 35.0, 30.0)
        cs.show_text("B")
        cs.end_text()
    return PDFRenderer(doc).render_image(0)


# ---------------------------------------------------------------------------
# Smoke tests — TK plumb-through + default
# ---------------------------------------------------------------------------


def test_text_knockout_default_is_true_on_fresh_gs() -> None:
    """Per PDF 32000-1 §9.3.8 the spec default is /TK true."""
    gs = _GState()
    assert gs.text_knockout is True


def test_op_begin_text_does_not_fork_at_alpha_one() -> None:
    """The sub-canvas fork is skipped when knockout has no observable
    effect (the common case: fill_alpha == 1.0, no blend mode). The
    fast path matters — every BT/ET in every PDF page hits this
    branch."""
    doc, page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw

    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._gs_stack = [_GState()]
    renderer._text_clip_paths = []
    # Default knockout=True + default fill_alpha=1.0 → no fork.
    renderer._op_begin_text(None, [])
    assert renderer._text_knockout_layer is None
    renderer._op_end_text(None, [])
    assert renderer._text_knockout_layer is None


def test_op_begin_text_forks_when_alpha_below_one() -> None:
    """Knockout=True + fill_alpha=0.5 → fork opens; ET closes it."""
    doc, page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw

    renderer._draw = aggdraw.Draw(renderer._image)
    gs = _GState()
    gs.fill_alpha = 0.5
    renderer._gs_stack = [gs]
    renderer._text_clip_paths = []
    parent_image = renderer._image
    renderer._op_begin_text(None, [])
    assert renderer._text_knockout_layer is not None
    # Sub-canvas is RGBA + same size + replaces self._image.
    assert renderer._image is renderer._text_knockout_layer
    assert renderer._image.mode == "RGBA"
    assert renderer._image.size == parent_image.size
    # Inner GS alpha is reset to 1.0 (the saved value is restored on ET).
    assert renderer._gs.fill_alpha == 1.0
    renderer._op_end_text(None, [])
    # Layer cleared, parent canvas re-bound, alpha restored.
    assert renderer._text_knockout_layer is None
    assert renderer._image is parent_image
    assert renderer._gs.fill_alpha == 0.5


def test_op_begin_text_skips_fork_when_knockout_false() -> None:
    """Knockout=False → no fork even at alpha < 1.0 (direct paint
    path; overlapping glyphs accumulate alpha)."""
    doc, page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw

    renderer._draw = aggdraw.Draw(renderer._image)
    gs = _GState()
    gs.text_knockout = False
    gs.fill_alpha = 0.5
    renderer._gs_stack = [gs]
    renderer._text_clip_paths = []
    renderer._op_begin_text(None, [])
    assert renderer._text_knockout_layer is None
    renderer._op_end_text(None, [])
    assert renderer._text_knockout_layer is None


def test_op_begin_text_forks_for_non_normal_blend_mode_at_alpha_one() -> None:
    """Even at fill_alpha=1.0, a non-Normal blend mode flips the visible
    behaviour (the spec composite formula isn't equal to direct paint
    for any non-Normal mode) so the fork must open."""
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

    doc, page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw

    renderer._draw = aggdraw.Draw(renderer._image)
    gs = _GState()
    gs.fill_alpha = 1.0
    gs.blend_mode = BlendMode.MULTIPLY
    renderer._gs_stack = [gs]
    renderer._text_clip_paths = []
    renderer._op_begin_text(None, [])
    assert renderer._text_knockout_layer is not None
    assert renderer._gs.blend_mode is None  # saved + reset inside fork.
    renderer._op_end_text(None, [])
    assert renderer._gs.blend_mode is BlendMode.MULTIPLY


# ---------------------------------------------------------------------------
# /TK propagation from ExtGState through gs operator
# ---------------------------------------------------------------------------


def test_tk_false_propagates_from_extgstate_through_gs_into_renderer() -> None:
    """End-to-end ExtGState → /TK false → renderer GS flag check.

    Mirrors the pattern in
    :func:`tests.rendering.test_pdf_renderer_extgstate_wave1385.test_tk_sets_text_knockout_flag`
    but inside a full content-stream context.
    """
    doc, page = _make_doc()
    ext = PDExtendedGraphicsState()
    ext.set_text_knockout_flag(False)
    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GSTK"),
        ext.get_cos_object(),
    )
    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = res
    renderer._op_set_graphics_state_parameters(
        None, [COSName.get_pdf_name("GSTK")]
    )
    assert renderer._gs.text_knockout is False


# ---------------------------------------------------------------------------
# Visible-effect parity — overlapping glyphs at alpha=0.5
# ---------------------------------------------------------------------------


def test_alpha_one_knockout_true_paints_full_black() -> None:
    """At alpha=1.0 (the common case) knockout is invisible — full
    opaque overlap regardless of TK setting. Sanity check that the
    fast path stays correct."""
    img = _render_two_overlapping_glyphs(knockout=True, alpha=1.0)
    # Sample inside the 'A' footprint (well clear of overlap region).
    # Page is 120x80, default 72dpi → 120x80 px. 'A' lives roughly
    # at x∈[10, 60], y∈[30, 80] in PDF coords → y-flipped on the
    # canvas. Sample a pixel that's surely inside 'A'.
    a_alpha = _alpha_at(img, 25, 40)
    assert a_alpha > 240, (
        f"alpha=1.0 should paint fully opaque pixels; got byte={a_alpha}"
    )


def test_alpha_one_knockout_true_matches_knockout_false() -> None:
    """At alpha=1.0 TK is a no-op — TK=true and TK=false should
    produce visually-identical images. The TK fork itself shouldn't
    introduce rounding noise."""
    img_tk_true = _render_two_overlapping_glyphs(knockout=True, alpha=1.0)
    img_tk_false = _render_two_overlapping_glyphs(knockout=False, alpha=1.0)
    # Compare a handful of pixels across the painted region.
    samples = [(25, 40), (45, 40), (55, 40), (75, 40), (90, 40)]
    for x, y in samples:
        a_true = _alpha_at(img_tk_true, x, y)
        a_false = _alpha_at(img_tk_false, x, y)
        assert abs(a_true - a_false) <= 2, (
            f"TK should be invisible at alpha=1.0; "
            f"got byte_tk_true={a_true} vs byte_tk_false={a_false} at ({x},{y})"
        )


def test_overlap_alpha_knockout_true_does_not_stack() -> None:
    """At fill_alpha=0.5 with TK=true the overlap region should read
    as 50% opaque (single-shape compositing — overlapping glyphs
    inside one BT/ET are treated as one path).

    Glyph layout: 'A' covers ~x∈[10, 60], 'B' (Tm-positioned at x=35)
    covers ~x∈[43, 93], so the overlap region sits around x∈[43, 60].
    """
    img = _render_two_overlapping_glyphs(knockout=True, alpha=0.5)
    overlap_alpha = _alpha_at(img, 45, 40)
    # 50% alpha over white → byte ≈ 128 ± rounding.
    assert 110 <= overlap_alpha <= 145, (
        f"TK=true overlap should be ~50% opaque; got byte={overlap_alpha}"
    )


def test_overlap_alpha_knockout_false_accumulates() -> None:
    """At fill_alpha=0.5 with TK=false the overlap region stacks per
    Porter-Duff source-over: ``1 - (1 - 0.5) ** 2 = 0.75``.

    The two glyph squares paint as independent shapes, so the overlap
    region sees the second glyph composite over the first.
    """
    img = _render_two_overlapping_glyphs(knockout=False, alpha=0.5)
    overlap_alpha = _alpha_at(img, 45, 40)
    # 75% alpha over white → byte ≈ 191 ± rounding.
    assert 170 <= overlap_alpha <= 210, (
        f"TK=false overlap should accumulate to ~75% opaque; "
        f"got byte={overlap_alpha}"
    )


def test_non_overlap_alpha_independent_of_knockout() -> None:
    """A pixel inside one glyph but outside the overlap region should
    paint at the requested alpha regardless of TK. Verifies the fork
    doesn't perturb non-overlapping glyph pixels (only the overlap
    behaviour should differ between TK=true and TK=false)."""
    img_tk_true = _render_two_overlapping_glyphs(knockout=True, alpha=0.5)
    img_tk_false = _render_two_overlapping_glyphs(knockout=False, alpha=0.5)
    # Sample a point inside 'A' but outside the overlap region — at
    # x=20 only 'A' covers (its right edge is around x=60, 'B' starts
    # at x=35 but its left edge is x=43 due to glyph padding).
    a_true = _alpha_at(img_tk_true, 20, 40)
    a_false = _alpha_at(img_tk_false, 20, 40)
    # Both should be ~50% opaque since only one glyph covers here.
    assert 110 <= a_true <= 145, (
        f"TK=true non-overlap should be ~50%; got {a_true}"
    )
    assert 110 <= a_false <= 145, (
        f"TK=false non-overlap should be ~50%; got {a_false}"
    )
    assert abs(a_true - a_false) <= 5, (
        f"non-overlap pixels should match between TK settings; "
        f"got tk_true={a_true} vs tk_false={a_false}"
    )
