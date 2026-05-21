"""Wave 1375 — minimal rich-text (``/RV``) rendering for text fields.

Covers the lite XHTML subset called out in the wave brief:

- ``<p>`` paragraph → line break + paragraph spacing
- ``<b>`` / ``<i>`` → bold / italic font alias swap
- ``<br/>`` → hard line break via ``T*``
- ``<span style="...">`` inline style overrides
- inline ``font-size``, ``color``, ``font-family``
- empty ``<p/>`` → vertical spacing
- malformed XHTML → graceful fallback to ``/V``
- fields without ``/RV`` → unchanged ``/V`` rendering (regression)
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_rv_color,
    _parse_rv_font_size,
    _parse_rv_runs,
    _parse_rv_style,
    _RichTextRun,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
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


# ---------- _parse_rv_color ----------


def test_parse_rv_color_short_hex() -> None:
    assert _parse_rv_color("#f00") == (1.0, 0.0, 0.0)


def test_parse_rv_color_long_hex() -> None:
    assert _parse_rv_color("#00ff00") == (0.0, 1.0, 0.0)


def test_parse_rv_color_rgb_func() -> None:
    assert _parse_rv_color("rgb(0, 0, 255)") == (0.0, 0.0, 1.0)


def test_parse_rv_color_unknown_returns_none() -> None:
    assert _parse_rv_color("red") is None
    assert _parse_rv_color("hsl(0, 100%, 50%)") is None
    assert _parse_rv_color("") is None


# ---------- _parse_rv_font_size ----------


def test_parse_rv_font_size_pt() -> None:
    assert _parse_rv_font_size("14pt") == 14.0


def test_parse_rv_font_size_px() -> None:
    assert _parse_rv_font_size("12px") == 12.0


def test_parse_rv_font_size_bare() -> None:
    assert _parse_rv_font_size("10") == 10.0


def test_parse_rv_font_size_invalid_returns_none() -> None:
    assert _parse_rv_font_size("foo") is None
    assert _parse_rv_font_size("0pt") is None


# ---------- _parse_rv_style ----------


def test_parse_rv_style_multi_value() -> None:
    out = _parse_rv_style("font-size: 12pt; color: #ff0000")
    assert out == {"font-size": "12pt", "color": "#ff0000"}


def test_parse_rv_style_empty() -> None:
    assert _parse_rv_style(None) == {}
    assert _parse_rv_style("") == {}
    assert _parse_rv_style("notakv") == {}


# ---------- _parse_rv_runs ----------


def test_parse_rv_runs_simple_paragraph() -> None:
    runs = _parse_rv_runs("<body><p>Hello world</p></body>")
    assert runs is not None
    texts = [r.text for r in runs if not r.line_break and r.text]
    assert "Hello world" in texts


def test_parse_rv_runs_bold() -> None:
    runs = _parse_rv_runs("<body><p>Hello <b>world</b></p></body>")
    assert runs is not None
    # Find the bold "world" run.
    bold_runs = [r for r in runs if r.bold and r.text]
    assert len(bold_runs) == 1
    assert bold_runs[0].text == "world"


def test_parse_rv_runs_italic() -> None:
    runs = _parse_rv_runs("<body><i>slanted</i></body>")
    assert runs is not None
    italic_runs = [r for r in runs if r.italic and r.text]
    assert len(italic_runs) == 1
    assert italic_runs[0].text == "slanted"


def test_parse_rv_runs_br_emits_linebreak() -> None:
    runs = _parse_rv_runs("<body>line1<br/>line2</body>")
    assert runs is not None
    # Expect text "line1", line break, text "line2".
    assert any(r.text == "line1" for r in runs)
    assert any(r.line_break for r in runs)
    assert any(r.text == "line2" for r in runs)


def test_parse_rv_runs_span_color() -> None:
    runs = _parse_rv_runs(
        "<body><span style='color:#ff0000'>red</span></body>"
    )
    assert runs is not None
    colored = [r for r in runs if r.color is not None and r.text == "red"]
    assert len(colored) == 1
    assert colored[0].color == (1.0, 0.0, 0.0)


def test_parse_rv_runs_font_size_override() -> None:
    runs = _parse_rv_runs(
        "<body><span style='font-size:20pt'>big</span></body>"
    )
    assert runs is not None
    sized = [r for r in runs if r.font_size == 20.0 and r.text == "big"]
    assert len(sized) == 1


def test_parse_rv_runs_font_family() -> None:
    runs = _parse_rv_runs(
        "<body><span style='font-family:Times New Roman'>roman</span></body>"
    )
    assert runs is not None
    family = [r for r in runs if r.font_family and r.text == "roman"]
    assert len(family) == 1
    assert "times" in family[0].font_family.lower()


def test_parse_rv_runs_unknown_tag_walked_transparently() -> None:
    runs = _parse_rv_runs("<body><font>weird</font></body>")
    assert runs is not None
    assert any(r.text == "weird" for r in runs)


def test_parse_rv_runs_empty_paragraph_inserts_spacing() -> None:
    runs = _parse_rv_runs("<body>top<p/>bottom</body>")
    assert runs is not None
    # Expect a line break between top and bottom; empty <p/> emits two
    # breaks per the lite spec but we only assert that at least one
    # break exists between the two text fragments.
    text_indices = [i for i, r in enumerate(runs) if r.text]
    line_break_indices = [i for i, r in enumerate(runs) if r.line_break]
    assert len(text_indices) >= 2
    assert any(
        text_indices[0] < lb < text_indices[-1] for lb in line_break_indices
    )


def test_parse_rv_runs_malformed_returns_none() -> None:
    assert _parse_rv_runs("<body><p>oops</body>") is None
    assert _parse_rv_runs("not xml at all") is None


# ---------- end-to-end appearance ----------


def test_rich_text_simple_appearance_contains_text_and_bold_swap() -> None:
    rv = "<body><p>Hello <b>world</b></p></body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b"Hello " in body
    assert b"world" in body
    # The bold variant Tf operator should reference Helvetica-Bold either by
    # the standard 14 face name or via an auto-allocated F<n> alias whose
    # /Resources entry maps to the bold COS object. Easiest assertion is
    # that the body contains two Tf operators (initial size + bold swap).
    assert body.count(b" Tf") >= 2


def test_rich_text_color_emits_rg_operator() -> None:
    rv = "<body><span style=\"color:#ff0000\">red</span></body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b"red" in body
    # Color operator (non-stroking RGB). Float rendering is "1 0 0 rg".
    assert b"1 0 0 rg" in body


def test_rich_text_br_emits_newline_operator() -> None:
    rv = "<body>line1<br/>line2</body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b"line1" in body
    assert b"line2" in body
    # T* operator emitted between the two lines.
    assert b"T*" in body


def test_rich_text_paragraph_emits_newline() -> None:
    rv = "<body><p>first</p><p>second</p></body>"
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b"first" in body
    assert b"second" in body
    # Paragraph closure emits T* between the two values.
    assert b"T*" in body


def test_rich_text_malformed_falls_back_to_v_value() -> None:
    """A malformed /RV payload silently degrades to the /V text."""
    tf = _build_text_field(value="fallback_text", rv="<body><p>oops</body>")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # /V text wins because /RV failed to parse.
    assert b"fallback_text" in body


def test_rich_text_without_rv_uses_v_regression() -> None:
    """No /RV present → plain /V rendering path (regression guard)."""
    tf = _build_text_field(value="plain_v_only")
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b"plain_v_only" in body
    # No /RV path means no extra Tf swap beyond the initial one.
    assert body.count(b" Tf") == 1


def test_rich_text_password_field_ignores_rv() -> None:
    """Password fields render the masked /V even if /RV is set."""
    tf = _build_text_field(value="secret", rv="<body><p>Hello</p></body>")
    tf.set_password(True)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    # Password mask shows asterisks, not the rich-text body.
    assert b"******" in body
    assert b"Hello" not in body


def test_rich_text_font_size_override_emits_resize() -> None:
    rv = (
        "<body>regular "
        "<span style=\"font-size:20pt\">large</span></body>"
    )
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    body = _appearance_body(tf)
    assert b"regular" in body
    assert b"large" in body
    # The 20pt size shows up in the body.
    assert b" 20 Tf" in body


def test_rich_text_runs_dataclass_repr_safe() -> None:
    run = _RichTextRun(text="x", bold=True)
    assert run.text == "x"
    assert run.bold is True
    assert run.italic is False
    assert run.color is None
    assert run.line_break is False


@pytest.mark.parametrize(
    "rv,expected_text",
    [
        ("<body><p>only</p></body>", b"only"),
        ("<body><i>slanted</i></body>", b"slanted"),
    ],
    ids=["paragraph_only", "italic_only"],
)
def test_rich_text_smoke_variants(rv: str, expected_text: bytes) -> None:
    tf = _build_text_field(value="ignored", rv=rv)
    PDAppearanceGenerator().generate(tf)
    assert expected_text in _appearance_body(tf)
