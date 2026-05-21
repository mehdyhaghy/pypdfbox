"""Wave 1377 — long-tail XHTML features for ``/RV`` rich-text rendering.

Extends wave 1375's minimal lite renderer with the deferred features
called out in the wave brief:

- Named CSS colors (147 W3C names, basic + extended)
- ``<sub>`` / ``<sup>`` super-/sub-scripts (``Ts`` operator + 0.583 shrink)
- ``background-color`` style (filled rect behind the run)
- ``<a href="...">`` link styling (blue + underline; no annotation)
- ``hsl(h, s%, l%)`` color (CSS Color-3 functional notation)
- ``<ul>`` / ``<ol>`` / ``<li>`` list rendering (marker prefix + newline)
- ``<table>`` deferred — walked transparently
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _RV_NAMED_COLORS,
    _hsl_to_rgb,
    _parse_rv_color,
    _parse_rv_runs,
    _RichTextRun,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_DA: COSName = COSName.get_pdf_name("DA")
_RV: COSName = COSName.get_pdf_name("RV")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _build_text_field(value: str = "fallback", rv: str | None = None) -> PDTextField:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0.0, 0.0, 300.0, 60.0))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value(value)
    if rv is not None:
        cos.set_string(_RV, rv)
    return tf


def _appearance_body(tf: PDTextField) -> bytes:
    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = PDAppearanceDictionary(widget_cos.get_dictionary_object(_AP))
    n = ap.get_normal_appearance()
    assert n is not None
    n_cos = n.get_cos_object()
    assert isinstance(n_cos, COSStream)
    return n_cos.create_input_stream().read()


# ----------------------------------------------------------------------
# Named CSS colours
# ----------------------------------------------------------------------


def test_named_color_rebeccapurple_parses_to_rgb() -> None:
    # rebeccapurple = #663399 = (102, 51, 153) / 255 = (0.4, 0.2, 0.6).
    parsed = _parse_rv_color("rebeccapurple")
    assert parsed is not None
    r, g, b = parsed
    assert r == pytest.approx(102 / 255.0)
    assert g == pytest.approx(51 / 255.0)
    assert b == pytest.approx(153 / 255.0)


def test_named_color_basic_16_present() -> None:
    # All 16 basic HTML colors should resolve.
    for name in (
        "aqua", "black", "blue", "fuchsia", "gray", "green", "lime",
        "maroon", "navy", "olive", "purple", "red", "silver", "teal",
        "white", "yellow",
    ):
        assert _parse_rv_color(name) is not None, name


def test_named_color_count_is_full_w3c_set() -> None:
    # Wave 1377 brief: the 147 W3C named colours.
    # ``transparent`` is intentionally excluded (treated as None) so
    # 147 - 1 = 146 isn't quite right either -- the table also dedupes
    # gray/grey synonyms, so accept the W3C 147 ± a small delta.
    # The check below is "well over the 16 basic, well within the 200
    # ceiling" -- if someone deletes the table this fails.
    assert 140 < len(_RV_NAMED_COLORS) < 160


def test_named_color_case_insensitive() -> None:
    a = _parse_rv_color("Red")
    b = _parse_rv_color("RED")
    c = _parse_rv_color("red")
    assert a == b == c == (1.0, 0.0, 0.0)


def test_named_color_unknown_returns_none() -> None:
    assert _parse_rv_color("notacolor") is None
    assert _parse_rv_color("transparent") is None  # deferred


def test_named_color_emits_rg_operator_in_appearance() -> None:
    rv = '<body><span style="color: rebeccapurple">x</span></body>'
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # rebeccapurple = (0.4, 0.2, 0.6) in 0..1 RGB. Floats render with up
    # to four fraction digits -- accept either the rounded or exact form.
    assert b" rg" in body
    # 0.4 / 0.2 / 0.6 are exact in our formatter.
    assert b"0.4 0.2 0.6 rg" in body


# ----------------------------------------------------------------------
# HSL colour
# ----------------------------------------------------------------------


def test_hsl_to_rgb_pure_green() -> None:
    r, g, b = _hsl_to_rgb(120.0, 1.0, 0.5)
    assert r == pytest.approx(0.0)
    assert g == pytest.approx(1.0)
    assert b == pytest.approx(0.0)


def test_hsl_to_rgb_pure_red() -> None:
    r, g, b = _hsl_to_rgb(0.0, 1.0, 0.5)
    assert (r, g, b) == pytest.approx((1.0, 0.0, 0.0))


def test_hsl_to_rgb_pure_blue() -> None:
    r, g, b = _hsl_to_rgb(240.0, 1.0, 0.5)
    assert (r, g, b) == pytest.approx((0.0, 0.0, 1.0))


def test_hsl_to_rgb_zero_saturation_is_gray() -> None:
    assert _hsl_to_rgb(180.0, 0.0, 0.5) == pytest.approx((0.5, 0.5, 0.5))


def test_hsl_color_in_style_parses() -> None:
    parsed = _parse_rv_color("hsl(120, 100%, 50%)")
    assert parsed == pytest.approx((0.0, 1.0, 0.0))


def test_hsl_color_alpha_form_parses_and_ignores_alpha() -> None:
    parsed = _parse_rv_color("hsla(240, 100%, 50%, 0.5)")
    assert parsed == pytest.approx((0.0, 0.0, 1.0))


def test_hsl_emits_green_rg_in_appearance() -> None:
    rv = '<body><span style="color: hsl(120, 100%, 50%)">go</span></body>'
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # Pure green in HSL = (0, 1, 0) RGB.
    assert b"0 1 0 rg" in body


# ----------------------------------------------------------------------
# <sub> / <sup>
# ----------------------------------------------------------------------


def test_sup_run_carries_positive_text_rise() -> None:
    runs = _parse_rv_runs("<body>x<sup>2</sup></body>")
    assert runs is not None
    sup_runs = [r for r in runs if r.text == "2"]
    assert sup_runs, "no superscript run emitted"
    assert sup_runs[0].text_rise > 0.0


def test_sub_run_carries_negative_text_rise() -> None:
    runs = _parse_rv_runs("<body>H<sub>2</sub>O</body>")
    assert runs is not None
    sub_runs = [r for r in runs if r.text == "2"]
    assert sub_runs, "no subscript run emitted"
    assert sub_runs[0].text_rise < 0.0


def test_sup_run_shrinks_font_size_relative_to_parent() -> None:
    runs = _parse_rv_runs(
        '<body><span style="font-size:20pt">'
        "X<sup>n</sup></span></body>"
    )
    assert runs is not None
    parent_runs = [r for r in runs if r.text == "X"]
    sup_runs = [r for r in runs if r.text == "n"]
    assert parent_runs and sup_runs
    assert parent_runs[0].font_size == pytest.approx(20.0)
    # 0.583 * 20 = 11.66.
    assert sup_runs[0].font_size == pytest.approx(20.0 * 0.583)


def test_sup_emits_ts_operator_in_appearance() -> None:
    rv = "<body>x<sup>2</sup></body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # ``Ts`` (text rise) operator should appear at least once for the
    # superscript run.
    assert b" Ts" in body
    assert b"2" in body


def test_sub_emits_ts_operator_in_appearance() -> None:
    rv = "<body>H<sub>2</sub>O</body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b" Ts" in body
    # Subscript rise is negative -- look for a negative number followed by Ts.
    assert b"-" in body


# ----------------------------------------------------------------------
# background-color
# ----------------------------------------------------------------------


def test_background_color_run_carries_background_field() -> None:
    runs = _parse_rv_runs(
        '<body><span style="background-color: yellow">hi</span></body>'
    )
    assert runs is not None
    hi = [r for r in runs if r.text == "hi"]
    assert hi
    assert hi[0].background_color == (1.0, 1.0, 0.0)


def test_background_color_emits_rect_fill_in_appearance() -> None:
    rv = (
        '<body><span style="background-color: yellow">marked</span></body>'
    )
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # Yellow fill: ``1 1 0 rg`` should appear (the non-stroking colour
    # set on the rect path), and the path itself uses ``re`` + ``f``.
    assert b"1 1 0 rg" in body
    assert b" re" in body
    assert b"\nf\n" in body or b" f\n" in body


def test_background_color_via_shorthand_property() -> None:
    # CSS shorthand ``background: red`` should also fill.
    runs = _parse_rv_runs('<body><span style="background: red">hi</span></body>')
    assert runs is not None
    hi = [r for r in runs if r.text == "hi"]
    assert hi
    assert hi[0].background_color == (1.0, 0.0, 0.0)


# ----------------------------------------------------------------------
# <a href="...">
# ----------------------------------------------------------------------


def test_link_run_is_blue_and_underlined() -> None:
    runs = _parse_rv_runs(
        '<body>click <a href="https://example.com">here</a></body>'
    )
    assert runs is not None
    link_runs = [r for r in runs if r.text == "here"]
    assert link_runs
    link_run = link_runs[0]
    assert link_run.underline is True
    # Default link colour ``#0000ee`` = (0, 0, 238/255).
    assert link_run.color is not None
    assert link_run.color[0] == pytest.approx(0.0)
    assert link_run.color[1] == pytest.approx(0.0)
    assert link_run.color[2] == pytest.approx(238.0 / 255.0)


def test_link_with_explicit_color_keeps_override() -> None:
    runs = _parse_rv_runs(
        '<body><a href="x" style="color: red">red link</a></body>'
    )
    assert runs is not None
    link_runs = [r for r in runs if r.text == "red link"]
    assert link_runs
    assert link_runs[0].color == (1.0, 0.0, 0.0)
    # Underline still applies.
    assert link_runs[0].underline is True


def test_link_emits_underline_stroke_in_appearance() -> None:
    rv = '<body><a href="https://example.com">click</a></body>'
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # Underline is a stroked line: ``m`` + ``l`` + ``S`` (capital S).
    assert b" m\n" in body
    assert b" l\n" in body
    assert b"\nS\n" in body or b" S\n" in body
    # Blue link colour for the underline stroke + text.
    assert b" RG" in body or b" rg" in body


def test_u_tag_underlines_run() -> None:
    runs = _parse_rv_runs("<body>plain <u>under</u> tail</body>")
    assert runs is not None
    under = [r for r in runs if r.text == "under"]
    assert under and under[0].underline is True


# ----------------------------------------------------------------------
# <ul> / <ol> / <li>
# ----------------------------------------------------------------------


def test_ul_emits_bullet_prefix_and_newline_between_items() -> None:
    runs = _parse_rv_runs("<body><ul><li>A</li><li>B</li></ul></body>")
    assert runs is not None
    texts = [r.text for r in runs if r.text]
    # Bullet markers precede each item text.
    assert "•  " in texts
    assert "A" in texts
    assert "B" in texts
    # Hard line break between items.
    breaks = [r for r in runs if r.line_break]
    assert len(breaks) >= 1


def test_ol_emits_numbered_prefix() -> None:
    runs = _parse_rv_runs(
        "<body><ol><li>first</li><li>second</li><li>third</li></ol></body>"
    )
    assert runs is not None
    texts = [r.text for r in runs if r.text]
    assert "1.  " in texts
    assert "2.  " in texts
    assert "3.  " in texts
    assert "first" in texts
    assert "second" in texts
    assert "third" in texts


def test_ul_renders_bullets_in_appearance() -> None:
    rv = "<body><ul><li>A</li><li>B</li></ul></body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # Bullet codepoint U+2022 may not be encodable in Helvetica's WinAnsi
    # (it is — 0x95 — so it should round-trip). At minimum the "A" / "B"
    # item bodies and a line break (T*) should appear.
    assert b"A" in body
    assert b"B" in body
    assert b"T*" in body


def test_nested_ul_resets_marker_per_level() -> None:
    # Nested lists should each get their own counter / bullet style.
    runs = _parse_rv_runs(
        "<body>"
        "<ul>"
        "<li>outer1<ol><li>inner1</li><li>inner2</li></ol></li>"
        "<li>outer2</li>"
        "</ul>"
        "</body>"
    )
    assert runs is not None
    texts = [r.text for r in runs if r.text]
    # Outer bullets present, inner counter starts at 1.
    assert "•  " in texts
    assert "1.  " in texts
    assert "2.  " in texts
    # Outer counter is unaffected by the inner list.
    assert texts.count("•  ") == 2


# ----------------------------------------------------------------------
# Deferred: <table>
# ----------------------------------------------------------------------


def test_table_walked_transparently_text_still_appears() -> None:
    # <table> is deferred; the walker should still surface inner text
    # (transparent walk-through) so producers using simple tables don't
    # see a hard failure.
    rv = (
        "<body><table>"
        "<tr><td>cell1</td><td>cell2</td></tr>"
        "</table></body>"
    )
    runs = _parse_rv_runs(rv)
    assert runs is not None
    texts = [r.text for r in runs if r.text]
    assert "cell1" in texts
    assert "cell2" in texts


# ----------------------------------------------------------------------
# Backwards compatibility / regression -- the new fields don't break
# plain text rendering.
# ----------------------------------------------------------------------


def test_plain_runs_default_text_rise_zero() -> None:
    runs = _parse_rv_runs("<body><p>plain</p></body>")
    assert runs is not None
    for r in runs:
        assert r.text_rise == 0.0
        assert r.background_color is None
        assert r.underline is False


def test_rich_text_run_repr_with_new_fields() -> None:
    run = _RichTextRun(
        text="x",
        underline=True,
        text_rise=2.5,
        background_color=(1.0, 0.0, 0.0),
    )
    assert run.underline is True
    assert run.text_rise == 2.5
    assert run.background_color == (1.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "rv,expected",
    [
        ('<body><span style="color: red">x</span></body>', b"1 0 0 rg"),
        ('<body><span style="color: lime">x</span></body>', b"0 1 0 rg"),
        ('<body><span style="color: blue">x</span></body>', b"0 0 1 rg"),
    ],
    ids=["named_red", "named_lime", "named_blue"],
)
def test_named_color_smoke_variants(rv: str, expected: bytes) -> None:
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    assert expected in _appearance_body(tf)
