"""Upstream-parity coverage for ``PDVariableText``.

PDFBox 3.0.x does not ship a dedicated ``PDVariableTextTest.java``; the
class is exercised through ``PDTextField`` / ``PDListBox`` / ``PDComboBox``
suites. This file pins the inheritable-attribute walk, the QUADDING
constants, and the new public ``get_string_or_stream`` helper (mirrors
upstream ``protected final`` ``getStringOrStream``).
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.interactive.form.pd_variable_text import PDVariableText

_DA: COSName = COSName.get_pdf_name("DA")
_DS: COSName = COSName.get_pdf_name("DS")
_Q: COSName = COSName.get_pdf_name("Q")
_RV: COSName = COSName.get_pdf_name("RV")
_FT: COSName = COSName.get_pdf_name("FT")


# ---------- QUADDING constants ----------


def test_quadding_constants() -> None:
    """Mirrors upstream ``PDVariableText.QUADDING_LEFT/CENTERED/RIGHT``."""
    assert PDVariableText.QUADDING_LEFT == 0
    assert PDVariableText.QUADDING_CENTERED == 1
    assert PDVariableText.QUADDING_RIGHT == 2


# ---------- /DA inheritable attribute walk ----------


def test_get_default_appearance_inherited_from_acroform() -> None:
    """Mirrors upstream ``getDefaultAppearance`` walking
    ``getInheritableAttribute(COSName.DA)``."""
    form = PDAcroForm()
    form.get_cos_object().set_string(_DA, "/Helv 0 Tf 0 g")

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    tf = PDTextField(form, field)

    assert tf.get_default_appearance() == "/Helv 0 Tf 0 g"


def test_get_default_appearance_returns_none_when_unset() -> None:
    """Upstream returns ``null`` when /DA is absent and no inheritable
    ancestor sets it; pypdfbox returns ``None``."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_default_appearance() is None


def test_set_default_appearance_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_default_appearance("/Helv 12 Tf 0 g")
    assert tf.get_default_appearance() == "/Helv 12 Tf 0 g"


# ---------- /Q inheritable attribute walk ----------


def test_get_q_default_zero_when_unset() -> None:
    """Mirrors upstream's ``return 0;`` when no /Q is found in the chain."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_q() == 0


def test_get_q_inherited_from_acroform() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_int(_Q, PDVariableText.QUADDING_RIGHT)

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    tf = PDTextField(form, field)

    assert tf.get_q() == PDVariableText.QUADDING_RIGHT


def test_set_q_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_q(PDVariableText.QUADDING_CENTERED)
    assert tf.get_q() == PDVariableText.QUADDING_CENTERED


# ---------- /DS (default style string, NOT inheritable) ----------


def test_default_style_string_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_default_style_string() is None
    tf.set_default_style_string("font: Helvetica; font-size: 12pt")
    assert tf.get_default_style_string() == "font: Helvetica; font-size: 12pt"


def test_set_default_style_string_none_removes_entry() -> None:
    """Upstream's ``setDefaultStyleString(null)`` removes the /DS key."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_default_style_string("body { color: red }")
    tf.set_default_style_string(None)
    assert tf.get_default_style_string() is None


# ---------- /RV (rich text value) ----------


def test_rich_text_value_round_trip_string() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value("<body>Hi</body>")
    assert tf.get_rich_text_value() == "<body>Hi</body>"


def test_rich_text_value_round_trip_stream() -> None:
    """Upstream's ``getStringOrStream`` decodes /RV when stored as a
    ``COSStream`` (PDF spec allows either form)."""
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(_FT, "Tx")
    rv_stream = COSStream()
    with rv_stream.create_output_stream() as sink:
        sink.write(b"<body>Streamed</body>")
    field.set_item(_RV, rv_stream)

    tf = PDTextField(form, field)
    assert tf.get_rich_text_value() == "<body>Streamed</body>"


def test_set_rich_text_value_none_removes_entry() -> None:
    """Upstream's ``setRichTextValue(null)`` removes the /RV key."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value("<body>Hi</body>")
    tf.set_rich_text_value(None)
    assert tf.get_rich_text_value() is None


# ---------- get_string_or_stream (Java protected final) ----------


def test_get_string_or_stream_with_cos_string() -> None:
    """Mirrors upstream ``getStringOrStream(COSString)`` branch."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_string_or_stream(COSString("hello")) == "hello"


def test_get_string_or_stream_with_cos_stream() -> None:
    """Mirrors upstream ``getStringOrStream(COSStream)`` branch."""
    form = PDAcroForm()
    tf = PDTextField(form)
    stream = COSStream()
    with stream.create_output_stream() as sink:
        sink.write(b"streamed")
    assert tf.get_string_or_stream(stream) == "streamed"


def test_get_string_or_stream_other_returns_none() -> None:
    """Upstream returns ``""`` for unsupported types; pypdfbox returns
    ``None`` (see CHANGES.md note covered by the round-out suite)."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_string_or_stream(COSArray()) is None
    assert tf.get_string_or_stream(None) is None


def test_get_string_or_stream_underscore_alias_preserved() -> None:
    """The legacy underscore-prefixed name is kept as a no-op alias so
    pre-rename callers continue to work; both forms must resolve to the
    same underlying function (compare via ``__func__`` since each
    attribute access creates a fresh bound-method wrapper)."""
    assert (
        PDVariableText._get_string_or_stream  # type: ignore[attr-defined]
        is PDVariableText.get_string_or_stream
    )
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf._get_string_or_stream(COSString("ok")) == "ok"
