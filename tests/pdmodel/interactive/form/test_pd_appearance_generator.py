from __future__ import annotations

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
    assert b"0.6 0.75 0.85" in body
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
    assert b"0.6 0.75 0.85" in body


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
    # Unsigned widgets show the "Sign here" placeholder.
    assert b"Sign here" in body
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
    # Signed widgets do NOT use the placeholder.
    assert b"Sign here" not in body
    # Solid border (no dash array).
    assert b"[3 3] 0 d" not in body
