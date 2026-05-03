"""PDVariableText round-out — predicate helpers, /RV stream payload, and
None-clearing semantics.

Hand-written tests covering remaining gaps on the variable-text base:
``has_*`` predicates for ``/DA`` / ``/DS`` / ``/Q`` / ``/RV``, the protected
``_get_string_or_stream`` helper (mirrors upstream
``PDVariableText.getStringOrStream``), and the None-clearing branches of
``set_default_style_string`` / ``set_rich_text_value``.
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
_KIDS: COSName = COSName.get_pdf_name("Kids")
_FT: COSName = COSName.get_pdf_name("FT")


# ---------- QUADDING constants (sanity / spec mirror) ----------


def test_quadding_constants_match_pdf_spec() -> None:
    """The /Q values are spec-defined; mirrors PDFBox QUADDING_LEFT=0,
    QUADDING_CENTERED=1, QUADDING_RIGHT=2."""
    assert PDVariableText.QUADDING_LEFT == 0
    assert PDVariableText.QUADDING_CENTERED == 1
    assert PDVariableText.QUADDING_RIGHT == 2


# ---------- has_default_appearance ----------


def test_has_default_appearance_false_when_unset() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.has_default_appearance() is False


def test_has_default_appearance_true_after_set() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_default_appearance("/Helv 12 Tf 0 g")
    assert tf.has_default_appearance() is True


def test_has_default_appearance_local_only_not_inherited() -> None:
    """Predicate checks the field's own dict — does NOT walk the inheritable
    chain (use ``get_default_appearance`` for the resolved value)."""
    form = PDAcroForm()
    form.get_cos_object().set_string(_DA, "/Helv 12 Tf 0 g")

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    tf = PDTextField(form, field)

    # Inherited from AcroForm but not local
    assert tf.get_default_appearance() == "/Helv 12 Tf 0 g"
    assert tf.has_default_appearance() is False


def test_has_default_appearance_after_clearing_with_none() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_default_appearance("/Helv 12 Tf 0 g")
    assert tf.has_default_appearance() is True
    tf.set_default_appearance(None)
    assert tf.has_default_appearance() is False


# ---------- has_default_style_string ----------


def test_has_default_style_string_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.has_default_style_string() is False
    tf.set_default_style_string("font: Helvetica; font-size:12pt")
    assert tf.has_default_style_string() is True
    assert tf.get_default_style_string() == "font: Helvetica; font-size:12pt"


def test_set_default_style_string_none_removes_entry() -> None:
    """Mirrors upstream ``setDefaultStyleString(null)`` — removes /DS."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_default_style_string("font: Helvetica")
    assert tf.has_default_style_string() is True

    tf.set_default_style_string(None)
    assert tf.has_default_style_string() is False
    assert tf.get_default_style_string() is None


# ---------- has_q ----------


def test_has_q_default_unset() -> None:
    """``get_q`` returns 0 (QUADDING_LEFT) by default; ``has_q`` distinguishes
    "not set" from "explicitly set to 0"."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.has_q() is False
    assert tf.get_q() == PDVariableText.QUADDING_LEFT


def test_has_q_true_after_explicit_zero() -> None:
    """Setting /Q=0 is a real value, not a default — predicate returns True."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_q(PDVariableText.QUADDING_LEFT)
    assert tf.has_q() is True
    assert tf.get_q() == 0


def test_has_q_true_after_centered() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_q(PDVariableText.QUADDING_CENTERED)
    assert tf.has_q() is True
    assert tf.get_q() == PDVariableText.QUADDING_CENTERED


def test_has_q_local_only_not_inherited() -> None:
    """Predicate checks the field's own dict — does NOT walk the inheritable
    chain. Caller must use ``get_q`` to read the effective value."""
    form = PDAcroForm()
    form.get_cos_object().set_int(_Q, PDVariableText.QUADDING_RIGHT)

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    tf = PDTextField(form, field)

    # Inherited from AcroForm
    assert tf.get_q() == PDVariableText.QUADDING_RIGHT
    assert tf.has_q() is False


# ---------- /RV (rich text value) ----------


def test_has_rich_text_value_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.has_rich_text_value() is False
    assert tf.get_rich_text_value() is None

    tf.set_rich_text_value("<body>Hi</body>")
    assert tf.has_rich_text_value() is True
    assert tf.get_rich_text_value() == "<body>Hi</body>"


def test_set_rich_text_value_none_removes_entry() -> None:
    """Mirrors upstream ``setRichTextValue(null)`` — removes /RV."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_rich_text_value("<body>Hi</body>")
    assert tf.has_rich_text_value() is True

    tf.set_rich_text_value(None)
    assert tf.has_rich_text_value() is False
    assert tf.get_rich_text_value() is None


def test_get_rich_text_value_from_cos_stream() -> None:
    """``/RV`` admits a COSStream payload (rich text rendered as a stream).
    Mirrors upstream ``getStringOrStream(COSStream)`` branch via
    ``COSStream.toTextString``.
    """
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(_FT, "Tx")

    rv_stream = COSStream()
    body = b"<body>Streamed</body>"
    with rv_stream.create_output_stream() as sink:
        sink.write(body)
    field.set_item(_RV, rv_stream)

    tf = PDTextField(form, field)
    # COSStream.to_text_string wraps in COSString; ASCII payload round-trips.
    assert tf.get_rich_text_value() == "<body>Streamed</body>"
    # Predicate sees the entry regardless of underlying COS type.
    assert tf.has_rich_text_value() is True


def test_get_rich_text_value_inherited_from_parent() -> None:
    """``/RV`` is inheritable per upstream's ``getInheritableAttribute`` walk."""
    form = PDAcroForm()
    form.get_cos_object().set_string(_RV, "<body>Inherited</body>")

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    tf = PDTextField(form, field)

    assert tf.get_rich_text_value() == "<body>Inherited</body>"
    # Local predicate is False even though the value is inherited.
    assert tf.has_rich_text_value() is False


# ---------- _get_string_or_stream helper (protected, but covered) ----------


def test_get_string_or_stream_with_cos_string() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf._get_string_or_stream(COSString("payload")) == "payload"


def test_get_string_or_stream_with_cos_stream() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)

    stream = COSStream()
    with stream.create_output_stream() as sink:
        sink.write(b"streamed payload")
    assert tf._get_string_or_stream(stream) == "streamed payload"


def test_get_string_or_stream_with_none_returns_none() -> None:
    """Pypdfbox keeps explicit ``None`` for missing/unsupported COS types so
    callers can distinguish "no entry" from "empty payload" — see CHANGES.md
    note. Upstream returns ``""`` in both cases.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf._get_string_or_stream(None) is None


def test_get_string_or_stream_with_unsupported_cos_type_returns_none() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    # COSArray is neither COSString nor COSStream — caller gets None, not "".
    assert tf._get_string_or_stream(COSArray()) is None


# ---------- set_default_appearance widget cascade — None branch ----------


def test_set_default_appearance_none_with_no_kids_clears_field_only() -> None:
    """Mirrors upstream ``setDefaultAppearance(null)`` — /DA removed, no kids
    iteration since /Kids is absent."""
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(_FT, "Tx")
    field.set_string(_DA, "/Helv 9 Tf 0 g")

    tf = PDTextField(form, field)
    tf.set_default_appearance(None)

    assert tf.has_default_appearance() is False


def test_set_default_appearance_with_kids_only_overwrites_widgets_with_da() -> None:
    """The kids-cascade path only overwrites widgets that already carry their
    own /DA. Mirrors upstream's PDFBOX-5797 logic."""
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(_FT, "Tx")

    widget_with = COSDictionary()
    widget_with.set_string(_DA, "/Helv 9 Tf 0 g")
    widget_without = COSDictionary()
    field.set_item(_KIDS, COSArray([widget_with, widget_without]))

    tf = PDTextField(form, field)
    tf.set_default_appearance("/F2 14 Tf 1 0 0 rg")

    assert tf.get_default_appearance() == "/F2 14 Tf 1 0 0 rg"
    assert widget_with.get_string(_DA) == "/F2 14 Tf 1 0 0 rg"
    # Widget without its own /DA stays untouched (inherits from field).
    assert not widget_without.contains_key(_DA)
