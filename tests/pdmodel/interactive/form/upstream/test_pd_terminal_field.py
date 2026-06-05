"""Parity-style tests for ``PDTerminalField``.

Upstream PDFBox does not ship a dedicated ``PDTerminalFieldTest.java``;
the behaviour exercised here is taken straight from
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDTerminalField.java``
(and the ``importFDF`` / flag-mutation logic shared with ``PDField``):

* ``getFieldType`` (lines 88-96) — walks self → parent only.
* ``getFieldFlags`` (lines 72-85) — walks self → parent only.
* ``setActions`` (lines 66-69) — typed override.
* ``getWidgets`` / ``setWidgets`` (lines 162-200).
* ``importFDF`` (lines 99-139) + ``PDField.importFDF`` (lines 237-306).
* ``exportFDF`` (lines 142-152).
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import PDNonTerminalField
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDFieldStub
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_V: COSName = COSName.get_pdf_name("V")
_T: COSName = COSName.get_pdf_name("T")


@pytest.fixture
def acro_form() -> PDAcroForm:
    return PDAcroForm()


# ---------- get_field_type — walks self -> parent only ----------


def test_get_field_type_local(acro_form: PDAcroForm) -> None:
    """Upstream PDTerminalField.getFieldType: own ``/FT`` wins."""
    tf = PDTextField(acro_form)
    assert tf.get_field_type() == "Tx"


def test_get_field_type_inherits_from_parent(acro_form: PDAcroForm) -> None:
    parent = PDNonTerminalField(acro_form)
    parent.get_cos_object().set_item(_FT, COSName.get_pdf_name("Btn"))
    tf = PDFieldStub(acro_form, parent=parent)
    assert tf.get_field_type() == "Btn"


def test_get_field_type_none_when_unset(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    assert tf.get_field_type() is None


def test_get_field_type_does_not_walk_into_acro_form(acro_form: PDAcroForm) -> None:
    """Upstream stops at the parent — form-level ``/FT`` is irrelevant
    because the AcroForm dictionary never legitimately carries ``/FT``.
    """
    acro_form.get_cos_object().set_item(_FT, COSName.get_pdf_name("Tx"))
    tf = PDFieldStub(acro_form)
    assert tf.get_field_type() is None


# ---------- get_field_flags — walks self -> parent only ----------


def test_get_field_flags_local(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    tf.set_field_flags(0b1010)
    assert tf.get_field_flags() == 0b1010


def test_get_field_flags_inherits_from_parent(acro_form: PDAcroForm) -> None:
    parent = PDNonTerminalField(acro_form)
    parent.get_cos_object().set_item(_FF, COSInteger(0b0101))
    tf = PDFieldStub(acro_form, parent=parent)
    assert tf.get_field_flags() == 0b0101


def test_get_field_flags_zero_when_unset(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    assert tf.get_field_flags() == 0


# ---------- import_fdf — value branch ----------


def test_import_fdf_string_value(acro_form: PDAcroForm) -> None:
    tf = PDTextField(acro_form)
    fdf = FDFField()
    fdf.set_value("hello")

    tf.import_fdf(fdf)
    assert tf.get_value() == "hello"


def test_import_fdf_name_value_via_button(acro_form: PDAcroForm) -> None:
    """Upstream PDField.importFDF: COSName values become button states."""
    from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

    cb = PDCheckBox(acro_form)
    # Wire a single on-state widget so set_value("Yes") is accepted.
    widget = cb.get_widgets()[0]
    ap = COSDictionary()
    n = COSDictionary()
    # On-state must be COSStream-valued: set_value -> check_value -> on-value
    # discovery filters to stream entries (wave 1488).
    n.set_item(COSName.get_pdf_name("Yes"), COSStream())
    n.set_item(COSName.get_pdf_name("Off"), COSStream())
    ap.set_item(COSName.get_pdf_name("N"), n)
    widget.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)

    fdf = FDFField()
    fdf.set_value(COSName.get_pdf_name("Yes"))

    cb.import_fdf(fdf)
    assert cb.get_value() == "Yes"


def test_import_fdf_no_value_keeps_existing(acro_form: PDAcroForm) -> None:
    """When the FDFField has no ``/V``, the field's existing value is left alone."""
    tf = PDTextField(acro_form)
    tf.set_value("keep me")
    fdf = FDFField()  # no /V

    tf.import_fdf(fdf)
    assert tf.get_value() == "keep me"


# ---------- import_fdf — flag bit mutation ----------


def test_import_fdf_set_field_flags_directly(acro_form: PDAcroForm) -> None:
    """``/Ff`` on the FDF wins outright over ``/SetFf`` and ``/ClrFf``."""
    tf = PDFieldStub(acro_form)
    tf.set_field_flags(0b0001)
    fdf = FDFField()
    fdf.set_field_flags(0b1100)
    fdf.set_set_field_flags(0b0010)  # ignored when /Ff present
    fdf.set_clear_field_flags(0b0001)  # ignored when /Ff present

    tf.import_fdf(fdf)
    assert tf.get_field_flags() == 0b1100


def test_import_fdf_set_ff_ors_into_existing(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    tf.set_field_flags(0b0001)
    fdf = FDFField()
    fdf.set_set_field_flags(0b1010)

    tf.import_fdf(fdf)
    assert tf.get_field_flags() == 0b1011


def test_import_fdf_clr_ff_clears_specified_bits(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    tf.set_field_flags(0b1011)
    fdf = FDFField()
    fdf.set_clear_field_flags(0b1101)
    # docF = 1011, clrF = 1101 -> result = 1011 & ~1101 = 0010 (upstream comment)

    tf.import_fdf(fdf)
    assert tf.get_field_flags() == 0b0010


# ---------- import_fdf — widget annotation flag mutation ----------


def test_import_fdf_widget_f_replaces_annotation_flags(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    widget = tf.get_widgets()[0]
    widget.set_annotation_flags(0b0011)

    fdf = FDFField()
    fdf.set_widget_field_flags(0b1000)

    tf.import_fdf(fdf)
    assert tf.get_widgets()[0].get_annotation_flags() == 0b1000


def test_import_fdf_widget_set_f_ors(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    tf.get_widgets()[0].set_annotation_flags(0b0001)

    fdf = FDFField()
    fdf.set_set_widget_field_flags(0b0110)

    tf.import_fdf(fdf)
    assert tf.get_widgets()[0].get_annotation_flags() == 0b0111


def test_import_fdf_widget_clr_f_clears(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    tf.get_widgets()[0].set_annotation_flags(0b1011)

    fdf = FDFField()
    fdf.set_clear_widget_field_flags(0b1101)

    tf.import_fdf(fdf)
    assert tf.get_widgets()[0].get_annotation_flags() == 0b0010


# ---------- export_fdf ----------


def test_export_fdf_copies_partial_name_and_value(acro_form: PDAcroForm) -> None:
    tf = PDTextField(acro_form)
    tf.set_partial_name("my_field")
    tf.set_value("hello")

    fdf = tf.export_fdf()
    assert isinstance(fdf, FDFField)
    assert fdf.get_partial_field_name() == "my_field"
    # /V is copied raw — same COS object identity.
    assert (
        fdf.get_cos_object().get_dictionary_object(_V)
        is tf.get_cos_object().get_dictionary_object(_V)
    )


def test_export_fdf_no_value(acro_form: PDAcroForm) -> None:
    tf = PDTextField(acro_form)
    tf.set_partial_name("empty")

    fdf = tf.export_fdf()
    assert fdf.get_partial_field_name() == "empty"
    assert fdf.get_cos_object().get_dictionary_object(_V) is None


def test_export_fdf_no_partial_name(acro_form: PDAcroForm) -> None:
    tf = PDFieldStub(acro_form)
    tf.get_cos_object().set_item(_V, COSString("abc"))

    fdf = tf.export_fdf()
    assert fdf.get_partial_field_name() is None
    v = fdf.get_cos_object().get_dictionary_object(_V)
    assert isinstance(v, COSString)
    assert v.get_string() == "abc"


# ---------- import_fdf — array value on a non-choice field ----------


def test_import_fdf_array_on_non_choice_writes_raw(acro_form: PDAcroForm) -> None:
    """Upstream throws IOException; we tolerate by writing the raw COSArray."""
    tf = PDFieldStub(acro_form)
    arr = COSArray([COSString("a"), COSString("b")])
    fdf = FDFField()
    fdf.get_cos_object().set_item(_V, arr)

    tf.import_fdf(fdf)
    assert tf.get_cos_object().get_dictionary_object(_V) is arr


# ---------- set_widgets / get_widgets — single-widget-merge fallback ----------


def test_get_widgets_single_widget_merge(acro_form: PDAcroForm) -> None:
    """Mirrors upstream comment 'the field itself is a widget' (line 169)."""
    tf = PDFieldStub(acro_form)
    widgets = tf.get_widgets()
    assert len(widgets) == 1
    assert isinstance(widgets[0], PDAnnotationWidget)
    assert widgets[0].get_cos_object() is tf.get_cos_object()
