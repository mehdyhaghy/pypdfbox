"""Wave 1585 — text-field appearance-generation fuzz / parity.

Hammers :class:`PDAppearanceGenerator` (the lite-port worker behind
``AppearanceGeneratorHelper.setAppearanceValue``) and the ``/DA``
default-appearance parser across the upstream-relevant text-field
appearance behaviours:

- ``/DA`` parsing — font alias + size + non-stroking colour operators
  (``g`` / ``rg`` / ``k``) re-emitted into the generated content stream.
- auto-font-size when the ``/DA`` size operand is ``0`` (text auto-size).
- quadding ``/Q`` 0/1/2 — left / centre / right x-position of the text.
- multiline (``Ff`` bit 13) line wrapping + per-line baseline advance.
- comb fields (``Ff`` bit 25) — ``/MaxLen`` evenly-spaced cells, with
  the cell width = ``bbox_width / MaxLen`` and the upstream
  incremental ``xOffset`` per-char scheme.
- default-appearance fallback when ``/DA`` is absent.
- setting a value regenerates the ``/AP /N`` normal appearance stream.

Parity reference: upstream
``org.apache.pdfbox.pdmodel.interactive.form.AppearanceGeneratorHelper``
(``insertGeneratedAppearance`` / ``insertGeneratedCombAppearance`` /
``calculateFontSize``) + ``PlainTextFormatter`` (quadding offsets). The
assertions check the resulting content-stream operator structure /
ordering, not byte-identical output (the lite port uses a height-based
auto-size heuristic, documented divergence).
"""

from __future__ import annotations

import re

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_default_appearance,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT = COSName.get_pdf_name("Rect")
_DA = COSName.get_pdf_name("DA")
_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _make_field(
    *,
    width: float = 100.0,
    height: float = 20.0,
    da: str | None = "/Helv 10 Tf 0 g",
    multiline: bool = False,
    comb: bool = False,
    max_len: int = -1,
    quadding: int = 0,
) -> PDTextField:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, width, height))
    if da is not None:
        tf.get_cos_object().set_string(_DA, da)
    if multiline:
        tf.set_multiline(True)
    if comb:
        tf.set_comb(True)
    if max_len >= 0:
        tf.set_max_len(max_len)
    if quadding:
        tf.set_q(quadding)
    return tf


def _normal_body(tf: PDTextField) -> str:
    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    return n.create_input_stream().read().decode("latin-1")


def _first_td(body: str) -> tuple[float, float]:
    m = re.search(r"(-?[\d.]+) (-?[\d.]+) Td", body)
    assert m is not None, f"no Td found in:\n{body}"
    return (float(m.group(1)), float(m.group(2)))


def _set_value(tf: PDTextField, value: str) -> None:
    PDAppearanceGenerator().set_appearance_value(tf, value)


# ---------------------------------------------------------------------------
# /DA parsing — font name + size + colour operators (pure function)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("da", "exp_name", "exp_size", "exp_color"),
    [
        ("/Helv 12 Tf 0 g", "Helv", 12.0, (0.0,)),
        ("/HeBo 9 Tf 0.25 g", "HeBo", 9.0, (0.25,)),
        ("/Helv 8 Tf 1 0 0 rg", "Helv", 8.0, (1.0, 0.0, 0.0)),
        ("/Helv 8 Tf 0 0 0 1 k", "Helv", 8.0, (0.0, 0.0, 0.0, 1.0)),
        ("/Helv 0 Tf 0.5 g", "Helv", 0.0, (0.5,)),
        ("/TiRo 14 Tf", "TiRo", 14.0, None),
        ("1 g /Helv 7 Tf", "Helv", 7.0, (1.0,)),  # colour before Tf
        ("", None, 0.0, None),
    ],
    ids=[
        "helv12-gray",
        "hebo9-gray025",
        "helv8-rgb-red",
        "helv8-cmyk-black",
        "helv-autosize-gray05",
        "tiro14-no-color",
        "color-before-tf",
        "empty",
    ],
)
def test_parse_default_appearance(
    da: str,
    exp_name: str | None,
    exp_size: float,
    exp_color: tuple[float, ...] | None,
) -> None:
    name, size, color = _parse_default_appearance(da)
    assert name == exp_name
    assert size == exp_size
    assert color == exp_color


def test_parse_default_appearance_none() -> None:
    assert _parse_default_appearance(None) == (None, 0.0, None)


def test_parse_default_appearance_last_tf_wins() -> None:
    name, size, _ = _parse_default_appearance("/Helv 6 Tf /HeBo 11 Tf")
    assert name == "HeBo"
    assert size == 11.0


def test_parse_default_appearance_last_color_wins() -> None:
    _, _, color = _parse_default_appearance("/Helv 8 Tf 1 0 0 rg 0 g")
    assert color == (0.0,)


# ---------------------------------------------------------------------------
# colour operators re-emitted into the content stream
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("da", "color_op"),
    [
        ("/Helv 10 Tf 0 g", "0 g"),
        ("/Helv 10 Tf 0.5 g", "0.5 g"),
        ("/Helv 10 Tf 1 0 0 rg", "1 0 0 rg"),
        ("/Helv 10 Tf 0 0 0 1 k", "0 0 0 1 k"),
    ],
    ids=["gray-black", "gray-half", "rgb-red", "cmyk-black"],
)
def test_da_color_op_applied_to_appearance(da: str, color_op: str) -> None:
    tf = _make_field(da=da)
    _set_value(tf, "X")
    body = _normal_body(tf)
    assert color_op in body
    # colour precedes the glyph show.
    assert body.index(color_op) < body.index("(X) Tj")


def test_da_font_alias_emitted_in_tf_token() -> None:
    tf = _make_field(da="/HeBo 9 Tf 0 g")
    _set_value(tf, "bold")
    body = _normal_body(tf)
    assert "/HeBo 9 Tf" in body


# ---------------------------------------------------------------------------
# auto-font-size when /DA size == 0
# ---------------------------------------------------------------------------


def test_autosize_clamps_to_max_for_tall_field() -> None:
    # height 20 -> 20*0.7 = 14, clamped to AUTO_FONT_SIZE_MAX (12).
    tf = _make_field(height=20.0, da="/Helv 0 Tf 0 g")
    _set_value(tf, "Hi")
    body = _normal_body(tf)
    m = re.search(r"/\S+ ([\d.]+) Tf", body)
    assert m is not None
    assert float(m.group(1)) == 12.0


def test_autosize_proportional_for_short_field() -> None:
    # height 10 -> 10*0.7 = 7 (between MIN 4 and MAX 12).
    tf = _make_field(height=10.0, da="/Helv 0 Tf 0 g")
    _set_value(tf, "")
    body = _normal_body(tf)
    m = re.search(r"/\S+ ([\d.]+) Tf", body)
    assert m is not None
    assert float(m.group(1)) == pytest.approx(7.0)


def test_autosize_clamps_to_min_for_tiny_field() -> None:
    # height 4 -> 4*0.7 = 2.8, clamped up to AUTO_FONT_SIZE_MIN (4).
    tf = _make_field(height=4.0, da="/Helv 0 Tf 0 g")
    _set_value(tf, "")
    body = _normal_body(tf)
    m = re.search(r"/\S+ ([\d.]+) Tf", body)
    assert m is not None
    assert float(m.group(1)) == pytest.approx(4.0)


def test_autosize_shrinks_long_single_line_to_fit_width() -> None:
    # narrow field + long value -> iterative shrink below the height clamp.
    tf = _make_field(width=30.0, height=20.0, da="/Helv 0 Tf 0 g")
    _set_value(tf, "a very long string that overflows the rect")
    body = _normal_body(tf)
    m = re.search(r"/\S+ ([\d.]+) Tf", body)
    assert m is not None
    size = float(m.group(1))
    assert PDAppearanceGenerator.MINIMUM_FONT_SIZE <= size <= 12.0
    # narrowed below the height-only clamp of 12.
    assert size < 12.0


def test_explicit_size_overrides_autosize() -> None:
    tf = _make_field(da="/Helv 7 Tf 0 g")
    _set_value(tf, "fixed")
    body = _normal_body(tf)
    assert "/Helv 7 Tf" in body


# ---------------------------------------------------------------------------
# quadding x-position (left / centre / right)
# ---------------------------------------------------------------------------


def test_quadding_left_starts_at_padding() -> None:
    tf = _make_field(quadding=0)
    _set_value(tf, "Hi")
    x, _ = _first_td(_normal_body(tf))
    assert x == pytest.approx(2.0)


def test_quadding_center_offsets_half_available() -> None:
    tf = _make_field(width=100.0, quadding=1)
    _set_value(tf, "Hi")
    body = _normal_body(tf)
    x, _ = _first_td(body)
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    # quadding uses the generator's average-width estimate, not the exact
    # per-glyph width — mirror that here for an exact parity comparison.
    text_w = PDAppearanceGenerator._estimate_text_width(font, 10.0, "Hi")
    interior_w = 100.0 - 2.0
    expected = 2.0 + (interior_w - text_w) / 2.0
    assert x == pytest.approx(expected, abs=0.01)


def test_quadding_right_offsets_full_available() -> None:
    tf = _make_field(width=100.0, quadding=2)
    _set_value(tf, "Hi")
    body = _normal_body(tf)
    x, _ = _first_td(body)
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    text_w = PDAppearanceGenerator._estimate_text_width(font, 10.0, "Hi")
    interior_w = 100.0 - 2.0
    expected = 2.0 + (interior_w - text_w)
    assert x == pytest.approx(expected, abs=0.01)


def test_quadding_center_left_of_right() -> None:
    xs: dict[int, float] = {}
    for q in (0, 1, 2):
        tf = _make_field(width=120.0, quadding=q)
        _set_value(tf, "abc")
        xs[q] = _first_td(_normal_body(tf))[0]
    assert xs[0] < xs[1] < xs[2]


def test_quadding_overflow_text_falls_back_to_left() -> None:
    # When the value is wider than the interior, centre/right clamp to
    # the left padding (available width is 0) — matches upstream's
    # ``lineWidth < width`` guard.
    long_value = "x" * 200
    tf = _make_field(width=40.0, da="/Helv 10 Tf 0 g", quadding=2)
    _set_value(tf, long_value)
    x, _ = _first_td(_normal_body(tf))
    assert x == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# multiline wrapping + baseline advance
# ---------------------------------------------------------------------------


def test_multiline_wraps_into_multiple_lines() -> None:
    tf = _make_field(width=80.0, height=60.0, multiline=True, da="/Helv 10 Tf 0 g")
    _set_value(tf, "one two three four five six seven")
    body = _normal_body(tf)
    # more than one (...) Tj => wrapped onto multiple lines.
    assert body.count(") Tj") >= 2


def test_multiline_advances_baseline_by_line_height() -> None:
    tf = _make_field(width=80.0, height=60.0, multiline=True, da="/Helv 10 Tf 0 g")
    _set_value(tf, "one two three four five six seven")
    body = _normal_body(tf)
    # line-height = size * 1.15 = 11.5; subsequent lines advance by -11.5.
    assert "-11.5 Td" in body


def test_multiline_first_baseline_near_top() -> None:
    tf = _make_field(width=80.0, height=60.0, multiline=True, da="/Helv 10 Tf 0 g")
    _set_value(tf, "alpha beta")
    body = _normal_body(tf)
    _, y = _first_td(body)
    # top_y = max(2, height - size*1.15) = 60 - 11.5 = 48.5.
    assert y == pytest.approx(48.5, abs=0.01)


def test_multiline_autosize_uses_default_for_tall_field() -> None:
    tf = _make_field(width=80.0, height=60.0, multiline=True, da="/Helv 0 Tf 0 g")
    _set_value(tf, "wrap me please across some lines")
    body = _normal_body(tf)
    m = re.search(r"/\S+ ([\d.]+) Tf", body)
    assert m is not None
    assert float(m.group(1)) == 12.0


def test_multiline_keeps_explicit_newlines() -> None:
    tf = _make_field(width=120.0, height=60.0, multiline=True, da="/Helv 10 Tf 0 g")
    _set_value(tf, "line1\nline2")
    body = _normal_body(tf)
    assert "(line1) Tj" in body
    assert "(line2) Tj" in body


# ---------------------------------------------------------------------------
# comb fields — /MaxLen evenly spaced cells
# ---------------------------------------------------------------------------


def test_comb_cell_width_is_bbox_over_maxlen() -> None:
    # width 100, MaxLen 5 -> cell width 20. Second char advances by the
    # full cell width (chars of equal width => prev/2 - curr/2 == 0).
    tf = _make_field(width=100.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5)
    _set_value(tf, "AB")
    body = _normal_body(tf)
    # the inter-char advance equals the cell width (20) for the 2nd glyph.
    assert "20 0 Td" in body or re.search(r"20(\.0+)? 0 Td", body)


def test_comb_first_char_centered_in_cell() -> None:
    tf = _make_field(width=100.0, height=20.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5)
    _set_value(tf, "A")
    body = _normal_body(tf)
    x, _ = _first_td(body)
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    cell_w = 100.0 / 5.0
    first_w = font.get_string_width("A") / 1000.0 * 10.0
    expected_x = (cell_w - first_w) / 2.0
    assert x == pytest.approx(expected_x, abs=0.01)


def test_comb_emits_one_show_per_char() -> None:
    tf = _make_field(width=120.0, da="/Helv 10 Tf 0 g", comb=True, max_len=6)
    _set_value(tf, "ABCD")
    body = _normal_body(tf)
    assert body.count(") Tj") == 4


def test_comb_truncates_value_to_maxlen() -> None:
    tf = _make_field(width=120.0, da="/Helv 10 Tf 0 g", comb=True, max_len=3)
    _set_value(tf, "ABCDEF")
    body = _normal_body(tf)
    # only 3 cells -> 3 glyph shows.
    assert body.count(") Tj") == 3


def test_comb_right_quadding_shifts_short_value() -> None:
    # value shorter than MaxLen with /Q 2: initial offset gains
    # (maxLen - numChars) * cellWidth vs left-aligned.
    left = _make_field(width=100.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5, quadding=0)
    _set_value(left, "AB")
    right = _make_field(width=100.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5, quadding=2)
    _set_value(right, "AB")
    x_left, _ = _first_td(_normal_body(left))
    x_right, _ = _first_td(_normal_body(right))
    cell_w = 100.0 / 5.0
    # 5 cells, 2 chars -> shift of (5-2)=3 cells.
    assert x_right - x_left == pytest.approx(3 * cell_w, abs=0.01)


def test_comb_center_quadding_uses_floor_div() -> None:
    left = _make_field(width=100.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5, quadding=0)
    _set_value(left, "AB")
    center = _make_field(width=100.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5, quadding=1)
    _set_value(center, "AB")
    x_left, _ = _first_td(_normal_body(left))
    x_center, _ = _first_td(_normal_body(center))
    cell_w = 100.0 / 5.0
    # floor((5-2)/2) = 1 cell shift.
    assert x_center - x_left == pytest.approx(1 * cell_w, abs=0.01)


def test_comb_empty_value_produces_no_glyphs() -> None:
    tf = _make_field(width=100.0, da="/Helv 10 Tf 0 g", comb=True, max_len=5)
    _set_value(tf, "")
    body = _normal_body(tf)
    assert ") Tj" not in body


# ---------------------------------------------------------------------------
# default-appearance fallback + value regeneration
# ---------------------------------------------------------------------------


def test_missing_da_falls_back_to_helvetica_autosize() -> None:
    tf = _make_field(da=None)
    _set_value(tf, "NoDA")
    body = _normal_body(tf)
    # no /DA -> auto-sized Helvetica (12 for a 20-tall field), value shown.
    assert "12 Tf" in body
    assert "(NoDA) Tj" in body


def test_generator_override_supplies_missing_da() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.set_value("override")
    PDAppearanceGenerator("/HeBo 9 Tf 0.25 g").generate(tf)
    body = _normal_body(tf)
    assert "/HeBo 9 Tf" in body
    assert "0.25 g" in body
    assert "(override) Tj" in body


def test_field_da_wins_over_generator_override() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 8 Tf 0 g")
    tf.set_value("field-da")
    PDAppearanceGenerator("/HeBo 11 Tf 0.5 g").generate(tf)
    body = _normal_body(tf)
    assert "8 Tf" in body
    assert "11 Tf" not in body


def test_set_value_regenerates_normal_appearance() -> None:
    tf = _make_field()
    _set_value(tf, "first")
    assert "(first) Tj" in _normal_body(tf)
    _set_value(tf, "second")
    body = _normal_body(tf)
    assert "(second) Tj" in body
    assert "(first) Tj" not in body


def test_set_value_marks_tx_bmc_and_emc() -> None:
    tf = _make_field()
    _set_value(tf, "tagged")
    body = _normal_body(tf)
    assert "/Tx BMC" in body
    assert "EMC" in body
    assert body.index("/Tx BMC") < body.index("EMC")


def test_set_value_collapses_newline_in_single_line() -> None:
    tf = _make_field(width=140.0)
    _set_value(tf, "a\nb")
    body = _normal_body(tf)
    # single-line fields collapse newline-class chars to a single space.
    assert "(a b) Tj" in body


def test_set_value_installs_clip_rect_with_padding() -> None:
    tf = _make_field(width=100.0, height=20.0)
    _set_value(tf, "clip")
    body = _normal_body(tf)
    # interior clip rect: 1pt margin all round -> "1 1 98 18 re" then the
    # clip + no-op path operators on their own lines.
    assert "1 1 98 18 re" in body
    assert "\nW\n" in body
    assert "\nn\n" in body


def test_set_value_sets_field_v() -> None:
    tf = _make_field()
    _set_value(tf, "stored")
    assert tf.get_value() == "stored"


def test_empty_value_still_emits_font_and_clip() -> None:
    tf = _make_field()
    _set_value(tf, "")
    body = _normal_body(tf)
    assert "Tf" in body
    assert "BT" in body
    assert "ET" in body
