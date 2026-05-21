from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_default_appearance,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_DA: COSName = COSName.get_pdf_name("DA")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_TYPE: COSName = COSName.get_pdf_name("Type")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


# ---------- /DA parser ----------


def test_parse_default_appearance_full() -> None:
    name, size, color = _parse_default_appearance("/Helv 12 Tf 0 0 0 rg")
    assert name == "Helv"
    assert size == 12.0
    assert color == (0.0, 0.0, 0.0)


def test_parse_default_appearance_grayscale() -> None:
    name, size, color = _parse_default_appearance("/HeBo 10 Tf 0.5 g")
    assert name == "HeBo"
    assert size == 10.0
    assert color == (0.5,)


def test_parse_default_appearance_cmyk() -> None:
    name, size, color = _parse_default_appearance("/TiRo 14 Tf 0 1 1 0 k")
    assert name == "TiRo"
    assert size == 14.0
    assert color == (0.0, 1.0, 1.0, 0.0)


def test_parse_default_appearance_empty() -> None:
    assert _parse_default_appearance(None) == (None, 0.0, None)
    assert _parse_default_appearance("") == (None, 0.0, None)


def test_parse_default_appearance_auto_size() -> None:
    name, size, _ = _parse_default_appearance("/Helv 0 Tf 0 g")
    assert name == "Helv"
    assert size == 0.0


# ---------- generator end-to-end ----------


def _build_text_field(value: str = "hello") -> PDTextField:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(50.0, 700.0, 250.0, 720.0))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value(value)
    return tf


def test_generate_creates_normal_appearance() -> None:
    tf = _build_text_field("hello world")
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n_entry = ap.get_dictionary_object(_N)
    assert isinstance(n_entry, COSStream)


def test_generate_appearance_stream_carries_value_text() -> None:
    tf = _build_text_field("hello world")
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = PDAppearanceDictionary(widget_cos.get_dictionary_object(_AP))
    n_entry = ap.get_normal_appearance()
    assert n_entry is not None
    n_cos = n_entry.get_cos_object()
    assert isinstance(n_cos, COSStream)

    # Wrap as appearance stream so we can read the body.
    stream = PDAppearanceStream(n_cos)
    body = stream.get_stream().create_input_stream().read()
    assert b"BT" in body
    assert b"ET" in body
    assert b"hello world" in body
    # Tf operator emitted with the resolved size.
    assert b"Tf" in body
    # /Tx BMC marker — Acrobat looks for this on form-field appearances.
    assert b"/Tx BMC" in body
    assert b"EMC" in body


def test_text_field_construct_appearances_creates_normal_appearance() -> None:
    tf = _build_text_field("constructed")

    tf.construct_appearances()

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"constructed" in body
    assert b"Tj" in body


def test_generate_sets_form_xobject_metadata() -> None:
    tf = _build_text_field()
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    assert n.get_name(_TYPE) == "XObject"
    assert n.get_name(_SUBTYPE) == "Form"
    bbox = n.get_dictionary_object(_BBOX)
    assert isinstance(bbox, COSArray)
    assert bbox.size() == 4
    # bbox is [0 0 width height] of the Rect (200 x 20).
    floats = [bbox.get_object(i).value for i in range(4)]
    assert floats[0] == 0.0
    assert floats[1] == 0.0
    assert abs(floats[2] - 200.0) < 1e-6
    assert abs(floats[3] - 20.0) < 1e-6


def test_generate_signature_field_unsigned_emits_empty_stream() -> None:
    """Unsigned signature fields get an empty /AP/N stream (no /V)."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig = PDSignatureField(form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    PDAppearanceGenerator().generate(sig)
    widget_cos = sig.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)


def test_generate_empty_value_emits_no_text_string_but_keeps_stream() -> None:
    tf = _build_text_field("")
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    # BT/ET still emitted; show-text operator is skipped because value is "".
    assert b"BT" in body
    assert b"ET" in body
    # No "Tj" without a value.
    assert b"Tj" not in body


def test_generate_handles_missing_da_with_helvetica_fallback() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.set_value("x")
    # No /DA set anywhere — generator falls back to Helvetica auto-size.
    PDAppearanceGenerator().generate(tf)
    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)


# ---------- set_value(regenerate_appearance=...) wiring ----------


def test_set_value_regenerate_appearance_false_does_not_create_ap() -> None:
    tf = _build_text_field()
    # Strip any /AP that might already be on the widget; default path
    # should keep it that way.
    tf.get_cos_object().remove_item(_AP)
    tf.set_value("changed")
    assert tf.get_cos_object().get_dictionary_object(_AP) is None


def test_set_value_regenerate_appearance_true_creates_ap() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_value("changed", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    assert b"changed" in body


def test_set_value_clear_with_regenerate_appearance() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_value("first", regenerate_appearance=True)
    tf.set_value(None, regenerate_appearance=True)

    # After clearing, /AP /N is rewritten with empty body (no Tj).
    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"Tj" not in body


# ---------- single-line text auto-sizing ----------


def test_single_line_auto_size_when_da_size_is_zero() -> None:
    """Auto-size kicks in when /DA size is 0 — clamped to AUTO_FONT_SIZE_MAX."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 30))
    tf.get_cos_object().set_string(_DA, "/Helv 0 Tf 0 g")
    tf.set_value("hello", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"hello" in body
    # Auto-size of 0.7 * 30 = 21, clamped to AUTO_FONT_SIZE_MAX = 12.
    assert b"12 Tf" in body


# ---------- multi-line text wrapping ----------


def test_multiline_text_wraps_long_lines() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 80, 60))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_multiline(True)
    # Long enough that the lite-port width estimator forces a wrap into
    # at least two rows when the rect is only 80pt wide.
    tf.set_value(
        "the quick brown fox jumps over the lazy dog",
        regenerate_appearance=True,
    )

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Multiple Tj calls = multiple lines.
    assert body.count(b"Tj") >= 2
    # Td at least once for line advance.
    assert b"Td" in body


def test_multiline_preserves_explicit_newlines() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 60))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_multiline(True)
    tf.set_value("line1\nline2\nline3", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"line1" in body
    assert b"line2" in body
    assert b"line3" in body
    assert body.count(b"Tj") == 3


# ---------- comb mode ----------


def test_comb_text_distributes_chars_into_cells() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_comb(True)
    tf.set_max_len(5)
    tf.set_value("ABCDE", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # One Tj per character — comb mode emits one show op per cell.
    assert body.count(b"Tj") == 5
    # Each character appears on its own.
    for ch in (b"A", b"B", b"C", b"D", b"E"):
        assert b"(" + ch + b")" in body


def test_comb_truncates_overflow_to_max_len() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_comb(True)
    tf.set_max_len(3)
    tf.set_value("XYZW", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Exactly 3 cells emitted — W is dropped.
    assert body.count(b"Tj") == 3
    assert b"(W)" not in body


# ---------- quadding ----------


def test_quadding_centered_uses_offset_x() -> None:
    """Quadding=1 (centered) emits a Td offset different from quadding=0 (left)."""
    form = PDAcroForm()
    tf_left = PDTextField(form)
    tf_left.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf_left.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf_left.set_q(0)
    tf_left.set_value("hi", regenerate_appearance=True)
    body_left = (
        tf_left.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )

    tf_center = PDTextField(form)
    tf_center.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf_center.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf_center.set_q(1)
    tf_center.set_value("hi", regenerate_appearance=True)
    body_center = (
        tf_center.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )

    # The two streams must differ — quadding has shifted x.
    assert body_left != body_center


# ---------- password masking ----------


def test_password_field_masks_value_with_asterisks() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_password(True)
    tf.set_value("secret123", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Plain value must not appear.
    assert b"secret123" not in body
    # 9 stars instead.
    assert b"*********" in body
    # /V is unchanged (the underlying value is preserved).
    assert tf.get_value() == "secret123"


def test_password_field_empty_value_emits_no_text() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_password(True)
    tf.set_value("", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"*" not in body
    assert b"Tj" not in body


# ---------- list-box selection highlight + scroll ----------


def test_list_box_selected_row_emits_highlight_rect() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

    form = PDAcroForm()
    lb = PDListBox(form)
    lb.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 60))
    lb.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["alpha", "beta", "gamma"])
    lb.set_value("beta", regenerate_appearance=True)

    widget_cos = lb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # All three options rendered (one Tj per row).
    assert body.count(b"Tj") == 3
    # Selection highlight color (Acrobat default blue) emitted.
    # Upstream HIGHLIGHT_COLOR is exactly {153/255, 193/255, 215/255}
    # — emitted to four decimal places by the float operand writer.
    assert b"0.6 0.7569 0.8431" in body
    # f operator (fill) emitted for the highlight rect.
    assert b"f\n" in body


def test_list_box_top_index_skips_leading_options() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

    form = PDAcroForm()
    lb = PDListBox(form)
    lb.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 60))
    lb.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["one", "two", "three", "four", "five"])
    lb.set_top_index(2)
    lb.set_value("four", regenerate_appearance=True)

    widget_cos = lb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Skipped rows must not appear in the stream.
    assert b"one" not in body
    assert b"two" not in body
    # Visible rows do appear.
    assert b"three" in body
    assert b"four" in body
    assert b"five" in body


def test_list_box_selected_indices_drive_highlight() -> None:
    """/I (selected indices) takes precedence even when /V is missing."""
    from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

    form = PDAcroForm()
    lb = PDListBox(form)
    lb.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 60))
    lb.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["alpha", "beta", "gamma"])
    lb.set_multi_select(True)
    lb.set_selected_options_indices([0, 2])
    PDAppearanceGenerator().generate(lb)

    widget_cos = lb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Two highlight rects = two `f` fill operators (plus background, none).
    # Just check the highlight color was emitted.
    # Upstream HIGHLIGHT_COLOR is exactly {153/255, 193/255, 215/255}
    # — emitted to four decimal places by the float operand writer.
    assert b"0.6 0.7569 0.8431" in body


# ---------- signature unsigned-state placeholder ----------


def test_signature_unsigned_emits_sign_here_placeholder() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig = PDSignatureField(form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    PDAppearanceGenerator().generate(sig)

    widget_cos = sig.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Unsigned widgets show the "Click to sign" placeholder (wave 1374
    # — matches upstream PDVisibleSigBuilder prompt).
    assert b"Click to sign" in body
    # Dashed border (3 on / 3 off) emitted.
    assert b"[3 3] 0 d" in body


def test_signature_signed_emits_name_and_date() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig_field = PDSignatureField(form)
    sig_field.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))

    signature = PDSignature()
    signature.set_name("Alice Example")
    sig_field.set_value(signature, regenerate_appearance=True)

    widget_cos = sig_field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"Alice Example" in body
    # Signed widgets do NOT use the placeholder (neither the wave-1374
    # "Click to sign" prompt nor the historical "Sign here" label).
    assert b"Click to sign" not in body
    assert b"Sign here" not in body
    # Solid border (no dash array).
    assert b"[3 3] 0 d" not in body


def test_signature_field_construct_appearances_does_not_generate_placeholder() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig = PDSignatureField(form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))

    sig.construct_appearances()

    widget_cos = sig.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None


# ---------- upstream-parity constants ----------


def test_constants_match_upstream() -> None:
    """Mirrors AppearanceGeneratorHelper static constants verbatim."""
    assert PDAppearanceGenerator.FONTSCALE == 1000
    assert PDAppearanceGenerator.MINIMUM_FONT_SIZE == 4.0
    assert PDAppearanceGenerator.DEFAULT_FONT_SIZE == 12.0
    assert PDAppearanceGenerator.DEFAULT_PADDING == 0.5
    # HIGHLIGHT_COLOR — upstream is {153/255f, 193/255f, 215/255f}.
    r, g, b = PDAppearanceGenerator.HIGHLIGHT_COLOR
    assert abs(r - 153.0 / 255.0) < 1e-9
    assert abs(g - 193.0 / 255.0) < 1e-9
    assert abs(b - 215.0 / 255.0) < 1e-9


# ---------- set_appearance_value ----------


def test_set_appearance_value_sets_value_and_regenerates() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")

    PDAppearanceGenerator().set_appearance_value(tf, "fresh")

    assert tf.get_value() == "fresh"
    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    assert b"fresh" in body


def test_set_appearance_value_collapses_newlines_for_single_line_text() -> None:
    """PDFBOX-3911: single-line /Tx widgets collapse newlines to spaces."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")

    PDAppearanceGenerator().set_appearance_value(tf, "line1\nline2\rline3")

    # Field /V also normalized.
    assert "\n" not in (tf.get_value() or "")
    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Newlines flattened — all three tokens on one line, joined by spaces.
    assert b"line1 line2 line3" in body


def test_generate_collapses_newlines_for_single_line_text_field() -> None:
    """``generate()`` directly also normalizes — covers callers that
    set /V outside ``set_appearance_value``."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    # Stuff /V directly with control characters — multiline = False.
    tf.set_value("abc def ghi")

    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"abc def ghi" in body


def test_set_appearance_value_preserves_newlines_for_multiline() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 60))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_multiline(True)

    PDAppearanceGenerator().set_appearance_value(tf, "first\nsecond")

    # Multi-line keeps the embedded newline in /V.
    assert tf.get_value() == "first\nsecond"
    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # Both lines emitted as separate Tj operators.
    assert b"first" in body
    assert b"second" in body


def test_set_appearance_value_handles_none_value() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_value("seed")

    PDAppearanceGenerator().set_appearance_value(tf, None)

    # None -> empty string (single-line normalization treats it as "").
    assert (tf.get_value() or "") == ""


# ---------- DA_FONT_ALIASES (Wave 214) ----------


def test_da_font_aliases_covers_standard14_short_keys() -> None:
    """Public alias map mirrors Acrobat's /DR /Font short keys.

    Each key resolves to a Standard 14 font name so callers introspecting
    the mapping (e.g. for /DR fix-ups) get the same answer the generator
    uses internally.
    """
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    aliases = PDAppearanceGenerator.DA_FONT_ALIASES
    # All upstream-canonical short keys are present.
    for short_key in (
        "Helv",
        "HeBo",
        "HeIt",
        "HeBI",
        "TiRo",
        "TiBo",
        "TiIt",
        "TiBI",
        "CoRo",
        "CoBo",
        "CoIt",
        "CoBI",
        "Symb",
        "ZaDb",
    ):
        assert short_key in aliases
        # Every value resolves to a Standard 14 face.
        assert (
            Standard14Fonts.get_mapped_font_name(aliases[short_key]) is not None
        )
    # Spot-check a few canonical pairings.
    assert aliases["Helv"] == Standard14Fonts.HELVETICA
    assert aliases["HeBo"] == Standard14Fonts.HELVETICA_BOLD
    assert aliases["TiRo"] == "Times-Roman"
    assert aliases["ZaDb"] == "ZapfDingbats"


def test_da_font_aliases_drives_resolve_font_for_known_short_key() -> None:
    """``_resolve_font`` reads from the public alias map — patching the
    mapping changes resolution behavior."""
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = Gen._resolve_font("HeBo")
    # Resolved via alias to Helvetica-Bold, not the literal "HeBo" name.
    assert font.get_name() == "Helvetica-Bold"


def test_resolve_font_fallback_to_helvetica_for_unknown_alias() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = Gen._resolve_font("MyCustomFont")
    assert font.get_name() == "Helvetica"


def test_resolve_font_none_falls_back_to_helvetica() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = Gen._resolve_font(None)
    assert font.get_name() == "Helvetica"


def test_resolve_font_recognises_full_standard14_name() -> None:
    """Passing a Standard 14 face name directly (rather than a short key)
    should also resolve — useful when /DA carries the canonical name."""
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = Gen._resolve_font("Times-Roman")
    assert font.get_name() == "Times-Roman"


# ---------- is_supported_field (Wave 214) ----------


def test_is_supported_field_text_button_choice_signature() -> None:
    """Predicate matches the dispatch table in :meth:`generate`."""
    from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
    from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
    from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
    from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
    from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    assert PDAppearanceGenerator.is_supported_field(PDTextField(form))
    assert PDAppearanceGenerator.is_supported_field(PDCheckBox(form))
    assert PDAppearanceGenerator.is_supported_field(PDRadioButton(form))
    assert PDAppearanceGenerator.is_supported_field(PDPushButton(form))
    assert PDAppearanceGenerator.is_supported_field(PDComboBox(form))
    assert PDAppearanceGenerator.is_supported_field(PDListBox(form))
    assert PDAppearanceGenerator.is_supported_field(PDSignatureField(form))


def test_is_supported_field_rejects_non_terminal_field() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )

    form = PDAcroForm()
    assert not PDAppearanceGenerator.is_supported_field(PDNonTerminalField(form))


def test_is_supported_field_is_static() -> None:
    """Predicate must be callable without instantiating the generator."""
    form = PDAcroForm()
    tf = PDTextField(form)
    # No ``self`` needed — call from class.
    assert PDAppearanceGenerator.is_supported_field(tf) is True


# ---------- _auto_size clamping (Wave 214) ----------


def test_auto_size_clamps_to_minimum_for_short_rect() -> None:
    """Very short widgets clamp up to AUTO_FONT_SIZE_MIN."""
    # height * 0.7 = 1.4 < AUTO_FONT_SIZE_MIN (4.0)
    assert PDAppearanceGenerator._auto_size(2.0) == (
        PDAppearanceGenerator.AUTO_FONT_SIZE_MIN
    )


def test_auto_size_clamps_to_maximum_for_tall_rect() -> None:
    """Very tall widgets clamp down to AUTO_FONT_SIZE_MAX."""
    # height * 0.7 = 70.0 > AUTO_FONT_SIZE_MAX (12.0)
    assert PDAppearanceGenerator._auto_size(100.0) == (
        PDAppearanceGenerator.AUTO_FONT_SIZE_MAX
    )


def test_auto_size_proportional_in_middle_range() -> None:
    """Inside the clamp range, picks 0.7 * height."""
    # height = 10 -> 7.0 (between 4 and 12)
    assert PDAppearanceGenerator._auto_size(10.0) == 7.0


def test_auto_size_zero_height_clamps_to_min() -> None:
    """Zero-height widgets still pick a sensible minimum."""
    assert PDAppearanceGenerator._auto_size(0.0) == (
        PDAppearanceGenerator.AUTO_FONT_SIZE_MIN
    )


# ---------- _color_array_to_tuple (Wave 214) ----------


def test_color_array_to_tuple_grayscale() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    arr = COSArray([COSFloat(0.5)])
    result = Gen._color_array_to_tuple(arr)
    assert result is not None
    assert len(result) == 1
    assert result[0] == pytest.approx(0.5)


def test_color_array_to_tuple_rgb() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    arr = COSArray([COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)])
    result = Gen._color_array_to_tuple(arr)
    assert result is not None
    assert len(result) == 3
    assert result == pytest.approx((0.1, 0.2, 0.3))


def test_color_array_to_tuple_cmyk() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    arr = COSArray(
        [COSFloat(0.0), COSFloat(1.0), COSFloat(0.5), COSFloat(0.25)]
    )
    result = Gen._color_array_to_tuple(arr)
    assert result is not None
    assert len(result) == 4
    assert result == pytest.approx((0.0, 1.0, 0.5, 0.25))


def test_color_array_to_tuple_two_components_returns_none() -> None:
    """PDF color spaces are 1, 3, or 4 components — 2-component arrays
    are invalid /MK colors."""
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    arr = COSArray([COSFloat(0.1), COSFloat(0.2)])
    assert Gen._color_array_to_tuple(arr) is None


def test_color_array_to_tuple_empty_array_returns_none() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    assert Gen._color_array_to_tuple(COSArray()) is None


def test_color_array_to_tuple_none_returns_none() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    assert Gen._color_array_to_tuple(None) is None


def test_color_array_to_tuple_non_array_returns_none() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    # A COSDictionary is not a color array — defensive fallback.
    assert Gen._color_array_to_tuple(COSDictionary()) is None


def test_color_array_to_tuple_non_numeric_entry_returns_none() -> None:
    """A /BG array with a name or string entry is malformed — fall back
    to None rather than raising."""
    from pypdfbox.cos import COSName as _CN
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    arr = COSArray([COSFloat(0.5), _CN.get_pdf_name("Foo"), COSFloat(0.5)])
    assert Gen._color_array_to_tuple(arr) is None


# ---------- _rect_from_cos (Wave 214) ----------


def test_rect_from_cos_normalizes_swapped_coordinates() -> None:
    """A /Rect with urx < llx (legal per PDF 32000-1) is normalized so
    width / height are non-negative — matches PDRectangle.from_cos_array."""
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        _rect_from_cos,
    )

    swapped = _rect(250.0, 720.0, 50.0, 700.0)
    assert _rect_from_cos(swapped) == (50.0, 700.0, 250.0, 720.0)


def test_rect_from_cos_returns_none_for_non_array() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        _rect_from_cos,
    )

    assert _rect_from_cos(None) is None
    assert _rect_from_cos(COSDictionary()) is None


def test_rect_from_cos_returns_none_for_short_array() -> None:
    """A /Rect with fewer than 4 entries is malformed."""
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        _rect_from_cos,
    )

    short = COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(10.0)])
    assert _rect_from_cos(short) is None


def test_rect_from_cos_returns_none_for_non_numeric_entry() -> None:
    """A /Rect with a non-numeric entry can't be parsed — fall back to None."""
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        _rect_from_cos,
    )

    arr = COSArray(
        [COSFloat(0.0), COSName.get_pdf_name("X"), COSFloat(10.0), COSFloat(20.0)]
    )
    assert _rect_from_cos(arr) is None


# ---------- _estimate_text_width (Wave 214) ----------


def test_estimate_text_width_empty_string_returns_zero() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    assert Gen._estimate_text_width(font, 12.0, "") == 0.0


def test_estimate_text_width_scales_linearly_with_size() -> None:
    """Width is proportional to ``size`` for the same string + font."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    w_at_10 = Gen._estimate_text_width(font, 10.0, "ABC")
    w_at_20 = Gen._estimate_text_width(font, 20.0, "ABC")
    # Doubling the size doubles the width.
    assert abs(w_at_20 - 2.0 * w_at_10) < 1e-9
    assert w_at_10 > 0.0


def test_estimate_text_width_scales_linearly_with_length() -> None:
    """Width is proportional to character count for the same font + size."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    w_one = Gen._estimate_text_width(font, 12.0, "A")
    w_three = Gen._estimate_text_width(font, 12.0, "AAA")
    # 3 chars -> 3x width.
    assert abs(w_three - 3.0 * w_one) < 1e-9


# ---------- _x_for_quadding (Wave 214) ----------


def test_x_for_quadding_left_returns_left_margin() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    gen = Gen()
    # quadding=0 -> left -> always 2.0 (the 1pt margin + interior offset).
    assert gen._x_for_quadding(font, 12.0, "A", 100.0, 0) == 2.0


def test_x_for_quadding_right_pushes_text_to_right_edge() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    gen = Gen()
    text_w = Gen._estimate_text_width(font, 12.0, "AB")
    interior_w = 100.0
    x = gen._x_for_quadding(font, 12.0, "AB", interior_w, 2)
    # Right-aligned: x = 2 + (interior_w - text_w).
    assert abs(x - (2.0 + interior_w - text_w)) < 1e-9


def test_x_for_quadding_centered_splits_available_space() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    gen = Gen()
    text_w = Gen._estimate_text_width(font, 12.0, "ABC")
    interior_w = 100.0
    x = gen._x_for_quadding(font, 12.0, "ABC", interior_w, 1)
    # Centered: x = 2 + (interior_w - text_w) / 2.
    assert abs(x - (2.0 + (interior_w - text_w) / 2.0)) < 1e-9


def test_x_for_quadding_text_wider_than_rect_clamps_offset() -> None:
    """When the text overflows the rect, the available offset is clamped
    to 0 so the text doesn't shift left of the margin."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    gen = Gen()
    # interior_w of 1.0 means almost any text overflows -> available = 0.
    x_centered = gen._x_for_quadding(font, 12.0, "very long", 1.0, 1)
    x_right = gen._x_for_quadding(font, 12.0, "very long", 1.0, 2)
    # Both clamp to the left margin.
    assert x_centered == 2.0
    assert x_right == 2.0


def test_x_for_quadding_unknown_value_falls_back_to_left() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    gen = Gen()
    # quadding=99 (out of range) -> left fallback.
    assert gen._x_for_quadding(font, 12.0, "X", 100.0, 99) == 2.0


# ---------- _wrap_lines (Wave 214) ----------


def test_wrap_lines_empty_value_yields_single_empty_line() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    assert Gen()._wrap_lines("", font, 12.0, 100.0) == [""]


def test_wrap_lines_preserves_empty_paragraphs() -> None:
    """Two consecutive ``\\n`` characters preserve the empty paragraph.

    Wave 1375: the wrap engine now delegates to :class:`PlainText`, which
    mirrors upstream's ``PlainText`` constructor by emitting ``" "`` for
    an empty paragraph (so Acrobat-faithful blank lines render).
    """
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    out = Gen()._wrap_lines("a\n\nb", font, 12.0, 1000.0)
    # Three lines: "a", " ", "b" — empty paragraph is preserved as a
    # blank line (single space, per upstream PlainText.java line 67).
    assert out == ["a", " ", "b"]


def test_wrap_lines_wide_word_force_splits() -> None:
    """A single word wider than the rect is force-split per the
    PDFBOX-5049 / PDFBOX-6082 fallback (wave 1375). At least one
    character is placed per line so the wrap engine always makes
    forward progress.
    """
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator as Gen,
    )

    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    # interior_w = 1.0 -> every word is too wide -> each char ends up on
    # its own line (per PDFBOX-6082 ``at least 1 char per line``).
    out = Gen()._wrap_lines("alpha beta", font, 12.0, 1.0)
    # Joining the lines back yields the original characters in order.
    assert "".join(out) == "alpha beta"
    # All lines have positive length (no empty lines).
    assert all(len(line) >= 1 for line in out)
    # No line wider than ``alpha`` (each character split out).
    assert all(len(line) <= len("alpha") for line in out)


# ---------- _NEWLINE_PATTERN (Wave 214) ----------


def test_newline_pattern_matches_unicode_line_separators() -> None:
    """PDFBOX-3911: pattern matches CRLF, LF, VT, FF, CR, NEL, LS, PS."""
    pat = PDAppearanceGenerator._NEWLINE_PATTERN
    # CRLF collapses to a single match (not two).
    assert pat.sub(" ", "a\r\nb") == "a b"
    # Each individual character also matches.
    for ch in ("\n", "\r", "", "", "", " ", " "):
        assert pat.sub("|", f"X{ch}Y") == "X|Y"


def test_newline_pattern_leaves_normal_chars_alone() -> None:
    pat = PDAppearanceGenerator._NEWLINE_PATTERN
    assert pat.sub("|", "no newlines here") == "no newlines here"


# ---------- _parse_default_appearance edge cases (Wave 214) ----------


def test_parse_default_appearance_tf_without_preceding_tokens() -> None:
    """A bare ``Tf`` operator with no font / size tokens before it can't
    populate ``font_name`` / ``size`` — both stay at defaults."""
    name, size, _ = _parse_default_appearance("Tf")
    assert name is None
    assert size == 0.0


def test_parse_default_appearance_malformed_size_falls_back() -> None:
    """If the size token isn't numeric, ``size`` falls back to 0.0
    (the auto-size sentinel)."""
    name, size, _ = _parse_default_appearance("/Helv abc Tf 0 g")
    assert name == "Helv"
    assert size == 0.0


def test_parse_default_appearance_color_only_no_tf() -> None:
    """A /DA carrying only a color operator returns the color but a
    ``None`` font name + zero size."""
    name, size, color = _parse_default_appearance("0.25 g")
    assert name is None
    assert size == 0.0
    assert color == (0.25,)


def test_parse_default_appearance_malformed_rg_skipped() -> None:
    """Non-numeric color components for ``rg`` skip color extraction."""
    _, _, color = _parse_default_appearance("/Helv 10 Tf x y z rg")
    assert color is None


def test_parse_default_appearance_last_color_wins() -> None:
    """When /DA carries multiple color operators, the last one wins."""
    _, _, color = _parse_default_appearance("/Helv 10 Tf 0.1 g 0.2 0.3 0.4 rg")
    # rg comes after g -> tuple of length 3 wins.
    assert color == (0.2, 0.3, 0.4)


def test_parse_default_appearance_font_name_without_slash_ignored() -> None:
    """A font-name token without the leading slash isn't recognised
    (PDFBox /DA grammar requires the /Name prefix)."""
    name, size, _ = _parse_default_appearance("Helv 10 Tf")
    assert name is None
    # Size is still picked up.
    assert size == 10.0


# ---------- Wave 1374: /MK /R rotation + iterative shrink-to-fit ----------


def _make_mk(**entries: object) -> COSDictionary:
    mk = COSDictionary()
    for key, value in entries.items():
        cos_key = COSName.get_pdf_name(key)
        if isinstance(value, COSArray):
            mk.set_item(cos_key, value)
        elif isinstance(value, int):
            mk.set_int(cos_key, value)
        elif isinstance(value, str):
            mk.set_string(cos_key, value)
    return mk


def test_wave1374_resolve_widget_rotation_canonical() -> None:
    """Rotations of 0/90/180/270 round-trip verbatim."""
    Gen = PDAppearanceGenerator
    for rot in (0, 90, 180, 270):
        widget = COSDictionary()
        widget.set_item(COSName.get_pdf_name("MK"), _make_mk(R=rot))
        assert Gen._resolve_widget_rotation(widget) == rot


def test_wave1374_resolve_widget_rotation_negative_normalises() -> None:
    """Negative multiples of 90 wrap to ``[0, 360)``."""
    Gen = PDAppearanceGenerator
    widget = COSDictionary()
    widget.set_item(COSName.get_pdf_name("MK"), _make_mk(R=-90))
    assert Gen._resolve_widget_rotation(widget) == 270


def test_wave1374_resolve_widget_rotation_non_canonical_collapses_to_zero() -> None:
    """Non-multiple-of-90 rotations collapse to 0 (matches upstream)."""
    Gen = PDAppearanceGenerator
    widget = COSDictionary()
    widget.set_item(COSName.get_pdf_name("MK"), _make_mk(R=45))
    assert Gen._resolve_widget_rotation(widget) == 0


def test_wave1374_resolve_widget_rotation_no_mk_returns_zero() -> None:
    Gen = PDAppearanceGenerator
    widget = COSDictionary()
    assert Gen._resolve_widget_rotation(widget) == 0


def test_wave1374_calculate_matrix_identity_for_zero_rotation() -> None:
    Gen = PDAppearanceGenerator
    assert Gen._calculate_matrix(100.0, 50.0, 0) == (
        1.0, 0.0, 0.0, 1.0, 0.0, 0.0,
    )


def test_wave1374_calculate_matrix_ninety_translates_y_to_x() -> None:
    Gen = PDAppearanceGenerator
    # 90 deg rotation about origin then translate so rotated content stays
    # in the bbox.
    m = Gen._calculate_matrix(50.0, 100.0, 90)
    # cos(90)=0, sin(90)=1 (with floating-point noise)
    assert m[0] == pytest.approx(0.0, abs=1e-9)
    assert m[1] == pytest.approx(1.0, abs=1e-9)
    assert m[2] == pytest.approx(-1.0, abs=1e-9)
    assert m[3] == pytest.approx(0.0, abs=1e-9)
    # tx = bbox_height (rotated y dim is now x), ty = 0
    assert m[4] == pytest.approx(100.0)
    assert m[5] == pytest.approx(0.0)


def test_wave1374_calculate_matrix_one_eighty() -> None:
    Gen = PDAppearanceGenerator
    m = Gen._calculate_matrix(80.0, 40.0, 180)
    assert m[0] == pytest.approx(-1.0, abs=1e-9)
    assert m[3] == pytest.approx(-1.0, abs=1e-9)
    assert m[4] == pytest.approx(80.0)
    assert m[5] == pytest.approx(40.0)


def test_wave1374_calculate_matrix_two_seventy() -> None:
    Gen = PDAppearanceGenerator
    m = Gen._calculate_matrix(50.0, 100.0, 270)
    assert m[0] == pytest.approx(0.0, abs=1e-9)
    assert m[1] == pytest.approx(-1.0, abs=1e-9)
    assert m[2] == pytest.approx(1.0, abs=1e-9)
    assert m[3] == pytest.approx(0.0, abs=1e-9)
    assert m[4] == pytest.approx(0.0)
    assert m[5] == pytest.approx(50.0)


def test_wave1374_text_widget_rotation_writes_matrix_and_swaps_bbox() -> None:
    """A /MK /R 90 rotation swaps bbox width/height and sets /Matrix."""
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 30))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    # /MK /R = 90 on the widget.
    widget_cos = tf.get_widgets()[0].get_cos_object()
    widget_cos.set_item(COSName.get_pdf_name("MK"), _make_mk(R=90))

    tf.set_value("ok", regenerate_appearance=True)

    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    bbox = n.get_dictionary_object(_BBOX)
    # Rotated bbox: original width=200, height=30 -> bbox should now be 30 x 200.
    assert bbox.get_object(2).value == pytest.approx(30.0)
    assert bbox.get_object(3).value == pytest.approx(200.0)
    matrix = n.get_dictionary_object(COSName.get_pdf_name("Matrix"))
    assert matrix is not None


def test_wave1374_text_widget_no_rotation_has_no_matrix() -> None:
    """Widgets without /MK /R keep an identity bbox and skip /Matrix."""
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 200, 30))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")

    tf.set_value("ok", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    matrix = n.get_dictionary_object(COSName.get_pdf_name("Matrix"))
    # /Matrix is omitted for the identity case (upstream parity).
    assert matrix is None


def test_wave1374_iterative_auto_size_returns_max_for_empty_text() -> None:
    """Empty text bypasses the shrink loop and uses the height clamp only."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    Gen = PDAppearanceGenerator
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    # height=30 -> height*0.7=21 -> clamped to AUTO_FONT_SIZE_MAX=12.
    assert Gen._iterative_auto_size(font, "", 100.0, 30.0) == 12.0


def test_wave1374_iterative_auto_size_shrinks_overflowing_text() -> None:
    """Very long text in a narrow rect shrinks below the height clamp."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    Gen = PDAppearanceGenerator
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    # At 12pt Helvetica, "OVERFLOW" is ~ 8 * 500 * 12 / 1000 = 48 user units.
    # A 10pt-wide rect cannot fit it, forcing shrink-to-fit.
    size = Gen._iterative_auto_size(font, "OVERFLOWING", 10.0, 30.0)
    # Final size must be smaller than the unshrunk candidate (12.0).
    assert size < 12.0
    # And must never drop below MINIMUM_FONT_SIZE.
    assert size >= Gen.MINIMUM_FONT_SIZE


def test_wave1374_iterative_auto_size_floor_at_minimum() -> None:
    """An impossibly narrow rect drops the size to MINIMUM_FONT_SIZE."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    Gen = PDAppearanceGenerator
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    # 0.1pt-wide rect — no font size, even MINIMUM_FONT_SIZE, will fit.
    size = Gen._iterative_auto_size(font, "huge text value", 0.1, 30.0)
    assert size == Gen.MINIMUM_FONT_SIZE


def test_wave1374_iterative_auto_size_fits_at_starting_size() -> None:
    """Text already fitting the rect returns the starting candidate."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    Gen = PDAppearanceGenerator
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    # "hi" at 12pt is roughly 12 user units; rect of 100pt easily fits.
    size = Gen._iterative_auto_size(font, "hi", 100.0, 20.0)
    assert size == Gen._auto_size(20.0)


def test_wave1374_iterative_auto_size_non_positive_width_uses_clamp() -> None:
    """Non-positive widths fall back to the height-only clamp."""
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    Gen = PDAppearanceGenerator
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    size = Gen._iterative_auto_size(font, "anything", 0.0, 10.0)
    # height=10 -> 7.0 (between 4 and 12) — same as _auto_size.
    assert size == 7.0


def test_wave1374_unsigned_signature_uses_click_to_sign_label() -> None:
    """Wave 1374 — unsigned sigs render "Click to sign" not "Sign here"."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig = PDSignatureField(form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    PDAppearanceGenerator().generate(sig)

    widget_cos = sig.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"Click to sign" in body
    assert b"Sign here" not in body


def test_wave1374_unsigned_signature_honours_mk_bg_fill() -> None:
    """/MK /BG fills the unsigned-sig background before the border."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig = PDSignatureField(form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    widget_cos = sig.get_widgets()[0].get_cos_object()
    bg_array = COSArray(
        [COSFloat(0.9), COSFloat(0.95), COSFloat(1.0)]
    )
    mk = COSDictionary()
    mk.set_item(COSName.get_pdf_name("BG"), bg_array)
    widget_cos.set_item(COSName.get_pdf_name("MK"), mk)

    PDAppearanceGenerator().generate(sig)

    body = (
        widget_cos.get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    # The background fill emits the BG color as a non-stroking ``rg`` operator
    # followed by ``re`` + ``f``.
    assert b"0.9 0.95 1 rg" in body
    assert b"f\n" in body


def test_wave1374_unsigned_signature_honours_mk_bc_stroke() -> None:
    """/MK /BC overrides the default black border on unsigned sigs."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    form = PDAcroForm()
    sig = PDSignatureField(form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    widget_cos = sig.get_widgets()[0].get_cos_object()
    bc_array = COSArray(
        [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0)]
    )
    mk = COSDictionary()
    mk.set_item(COSName.get_pdf_name("BC"), bc_array)
    widget_cos.set_item(COSName.get_pdf_name("MK"), mk)

    PDAppearanceGenerator().generate(sig)

    body = (
        widget_cos.get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    # 1 0 0 RG = red stroke (RG is the stroking-color operator).
    assert b"1 0 0 RG" in body


def test_wave1374_button_widget_rotation_swaps_bbox() -> None:
    """Check-box widget /MK /R 90 swaps the on-stream bbox dimensions."""
    from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

    form = PDAcroForm()
    cb = PDCheckBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 40, 20))
    widget_cos = cb.get_widgets()[0].get_cos_object()
    widget_cos.set_item(COSName.get_pdf_name("MK"), _make_mk(R=90))

    PDAppearanceGenerator().generate(cb)

    n_subdict = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    # On-state stream — pick the first non-Off entry.
    for key in n_subdict.key_set():
        if key.name != "Off":
            on_stream = n_subdict.get_dictionary_object(key)
            break
    bbox = on_stream.get_dictionary_object(_BBOX)
    # Rotated bbox: 20 x 40 (was 40 x 20).
    assert bbox.get_object(2).value == pytest.approx(20.0)
    assert bbox.get_object(3).value == pytest.approx(40.0)
    matrix = on_stream.get_dictionary_object(COSName.get_pdf_name("Matrix"))
    assert matrix is not None


def test_wave1374_push_button_long_caption_shrinks_below_clamp() -> None:
    """A long /MK /CA caption in a narrow push-button shrinks to fit."""
    from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton

    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 30, 20))  # narrow rect
    widget_cos = pb.get_widgets()[0].get_cos_object()
    mk = COSDictionary()
    mk.set_string(COSName.get_pdf_name("CA"), "Click Me Now Please!!")
    widget_cos.set_item(COSName.get_pdf_name("MK"), mk)

    PDAppearanceGenerator().generate(pb)

    body = (
        widget_cos.get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    # Caption is in the body, but the Tf size emitted is below the 12pt
    # clamp (iterative shrink kicked in).
    assert b"Click Me Now Please!!" in body
    assert b"12 Tf" not in body
