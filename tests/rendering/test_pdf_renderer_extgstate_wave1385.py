"""Wave 1385 — ExtGState entries applied by the ``gs`` operator.

Before wave 1385 the renderer's ``_op_set_graphics_state_parameters``
only honoured ``/BM`` / ``/SMask`` / ``/CA`` / ``/ca``. Real-world PDFs
routinely set ``/LW`` / ``/LC`` / ``/LJ`` / ``/ML`` / ``/D`` /
``/RI`` / ``/Font`` / ``/AIS`` / ``/FL`` / ``/SM`` / ``/SA`` / ``/TK``
through ExtGState dictionaries — none of those were being plumbed through
to the active GS, so any subsequent stroke or text op silently used the
spec defaults instead of the file-declared values.

Upstream's reference is
``org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState
::copyIntoGraphicsState``. This wave wires every rendering-relevant
field; the overprint / transfer / halftone entries remain deferred (no
behavioural effect on the lite renderer's raster output).
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


def _attach_renderer(ext, ext_name="GS0"):
    """Spin up a minimal renderer with a resources dict carrying
    ``ext_g_state`` under ``/Resources/ExtGState/<ext_name>``, then
    invoke ``_op_set_graphics_state_parameters`` so the ``gs`` operator
    fires its full plumb-through."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
    doc.add_page(page)

    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name(ext_name),
        ext.get_cos_object(),
    )

    renderer = PDFRenderer.__new__(PDFRenderer)
    renderer._gs_stack = [_GState()]
    renderer._resources = res
    renderer._op_set_graphics_state_parameters(
        None, [COSName.get_pdf_name(ext_name)]
    )
    return renderer


# ---------------------------------------------------------------------------
# stroke-state plumb-through
# ---------------------------------------------------------------------------


def test_lw_sets_line_width_on_gs() -> None:
    """``/LW`` should override ``gs.line_width`` (spec default 1.0)."""
    ext = PDExtendedGraphicsState()
    ext.set_line_width(5.5)
    r = _attach_renderer(ext)
    assert r._gs.line_width == 5.5


def test_lc_sets_line_cap_style_clamped_to_0_1_2() -> None:
    """``/LC`` — butt / round / projecting square (codes 0..2)."""
    for code in (0, 1, 2):
        ext = PDExtendedGraphicsState()
        ext.set_line_cap_style(code)
        r = _attach_renderer(ext)
        assert r._gs.line_cap == code


def test_lc_out_of_range_clamps_to_2() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_line_cap_style(99)
    r = _attach_renderer(ext)
    assert r._gs.line_cap == 2


def test_lj_sets_line_join_style() -> None:
    for code in (0, 1, 2):
        ext = PDExtendedGraphicsState()
        ext.set_line_join_style(code)
        r = _attach_renderer(ext)
        assert r._gs.line_join == code


def test_ml_sets_miter_limit() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_miter_limit(15.0)
    r = _attach_renderer(ext)
    assert r._gs.miter_limit == 15.0


def test_ml_negative_value_ignored() -> None:
    """A negative miter limit is meaningless (the spec calls it a
    multiplier on line width); the renderer should keep the default."""
    ext = PDExtendedGraphicsState()
    ext.set_miter_limit(-2.0)
    r = _attach_renderer(ext)
    assert r._gs.miter_limit == 10.0  # default


def test_d_sets_dash_pattern() -> None:
    """``/D`` carries ``[dash_array phase]`` — the renderer stores both
    pieces as a ``(tuple_of_floats, phase)`` pair on the GS."""
    from pypdfbox.cos import COSArray, COSInteger

    inner = COSArray()
    inner.add(COSInteger.get(3))
    inner.add(COSInteger.get(2))
    pattern = PDLineDashPattern(inner, 1)
    ext = PDExtendedGraphicsState()
    ext.set_line_dash_pattern(pattern)
    r = _attach_renderer(ext)
    assert r._gs.dash_pattern is not None
    arr, phase = r._gs.dash_pattern
    assert arr == (3.0, 2.0)
    assert phase == 1.0


def test_d_empty_array_means_solid_line() -> None:
    """A ``/D [[] 0]`` entry resets to a solid line — spec §8.4.3.6."""
    from pypdfbox.cos import COSArray

    empty = COSArray()
    pattern = PDLineDashPattern(empty, 0)
    ext = PDExtendedGraphicsState()
    ext.set_line_dash_pattern(pattern)
    r = _attach_renderer(ext)
    assert r._gs.dash_pattern is None


def test_ri_sets_rendering_intent() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_rendering_intent("AbsoluteColorimetric")
    r = _attach_renderer(ext)
    assert r._gs.rendering_intent == "AbsoluteColorimetric"


# ---------------------------------------------------------------------------
# /Font [font size]
# ---------------------------------------------------------------------------


def test_font_pair_sets_text_font_and_size() -> None:
    """``/Font [font_dict size]`` — both pieces land on the text state."""
    from pypdfbox.cos import COSArray, COSFloat

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )

    arr = COSArray()
    arr.add(font_dict)
    arr.add(COSFloat(12.0))

    ext = PDExtendedGraphicsState()
    ext.get_cos_object().set_item(COSName.get_pdf_name("Font"), arr)

    r = _attach_renderer(ext)
    assert r._gs.text_font is not None
    assert r._gs.text_font_size == 12.0


# ---------------------------------------------------------------------------
# alpha-is-shape + text knockout flags
# ---------------------------------------------------------------------------


def test_ais_sets_alpha_is_shape_flag() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_alpha_source_flag(True)
    r = _attach_renderer(ext)
    assert r._gs.alpha_is_shape is True


def test_tk_sets_text_knockout_flag() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_text_knockout_flag(False)
    r = _attach_renderer(ext)
    assert r._gs.text_knockout is False


# ---------------------------------------------------------------------------
# tolerance / adjustment flags
# ---------------------------------------------------------------------------


def test_fl_sets_flatness_tolerance() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_flatness(3.5)
    r = _attach_renderer(ext)
    assert r._gs.flatness == 3.5


def test_sm_sets_smoothness_tolerance() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_smoothness(0.25)
    r = _attach_renderer(ext)
    assert r._gs.smoothness == 0.25


def test_sa_sets_stroke_adjustment_flag() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_stroke_adjustment(True)
    r = _attach_renderer(ext)
    assert r._gs.stroke_adjustment is True


# ---------------------------------------------------------------------------
# GS clone / save-restore preserves the new fields
# ---------------------------------------------------------------------------


def test_clone_carries_new_fields() -> None:
    """``q`` / ``Q`` save / restore — :meth:`_GState.clone` must carry
    every new field forward so an ExtGState applied inside a save block
    survives the matching restore."""
    gs = _GState(
        line_cap=2,
        line_join=1,
        miter_limit=8.0,
        dash_pattern=((4.0, 1.0), 0.5),
        rendering_intent="Saturation",
        text_rendering_mode=5,
        alpha_is_shape=True,
        text_knockout=False,
        flatness=2.0,
        smoothness=0.1,
        stroke_adjustment=True,
    )
    clone = gs.clone()
    assert clone.line_cap == 2
    assert clone.line_join == 1
    assert clone.miter_limit == 8.0
    assert clone.dash_pattern == ((4.0, 1.0), 0.5)
    assert clone.rendering_intent == "Saturation"
    assert clone.text_rendering_mode == 5
    assert clone.alpha_is_shape is True
    assert clone.text_knockout is False
    assert clone.flatness == 2.0
    assert clone.smoothness == 0.1
    assert clone.stroke_adjustment is True


def test_existing_ext_gstate_entries_still_apply_after_new_wiring() -> None:
    """Regression guard — the new ExtGState wiring sits beside the
    existing /BM /SMask /CA /ca handlers; make sure they still apply."""
    ext = PDExtendedGraphicsState()
    ext.set_stroking_alpha_constant(0.5)
    ext.set_non_stroking_alpha_constant(0.25)
    r = _attach_renderer(ext)
    assert r._gs.stroke_alpha == 0.5
    assert r._gs.fill_alpha == 0.25


def test_unknown_extgstate_name_silently_ignored() -> None:
    """The ``gs`` operator with a name that doesn't resolve to an
    ExtGState dict shouldn't crash — it should simply leave the GS
    untouched (matches upstream's defensive behaviour)."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
    doc.add_page(page)
    res = PDResources()
    page.set_resources(res)

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._resources = res
    # No ExtGState registered — operator must be a silent no-op.
    r._op_set_graphics_state_parameters(
        None, [COSName.get_pdf_name("DOES_NOT_EXIST")]
    )
    assert r._gs.line_width == 1.0  # spec default unchanged
