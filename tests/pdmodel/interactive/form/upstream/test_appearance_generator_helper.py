"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/AppearanceGeneratorHelperTest.java``
(PDFBox 3.0.x).

Upstream tests focus on parity of the rendered appearance content stream:
they sign-off on the operator sequence emitted for representative field
configurations (single-line text, multi-line text, comb, password, list-box
selection, push-button captions, signature placeholders).

Java-specific plumbing (``getResourceAsStream``, ``Loader.loadPDF``) is
swapped for direct ``COSDictionary`` construction; the lite port has no
PDF-loading round-trip that mirrors upstream's fixture-based setup. Tests
that only exercise that plumbing are skipped with a one-line comment per
the porting conventions in CLAUDE.md.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT: COSName = COSName.get_pdf_name("Rect")
_DA: COSName = COSName.get_pdf_name("DA")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_AS: COSName = COSName.get_pdf_name("AS")
_OFF: COSName = COSName.get_pdf_name("Off")
_MK: COSName = COSName.get_pdf_name("MK")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


@pytest.fixture
def acro_form() -> PDAcroForm:
    """Equivalent of upstream ``setUp()`` — a blank ``PDAcroForm`` to host
    the field under test. Upstream loads a fixture PDF via
    ``Loader.loadPDF(getClass().getResourceAsStream(...))``; the lite port
    uses an in-memory COS object graph instead.
    """
    return PDAcroForm()


# ---------- text field — single line ----------


def test_set_value_creates_appearance(acro_form: PDAcroForm) -> None:
    """testSetValueCreatesAppearance — set_value() with regenerate flag
    populates /AP/N with a flat appearance stream."""
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 12 Tf 0 g")
    tf.set_value("PDFBox", regenerate_appearance=True)

    n = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
    )
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    assert b"PDFBox" in body
    assert b"/Tx BMC" in body


def test_empty_value_emits_no_show_text(acro_form: PDAcroForm) -> None:
    """testEmptyValue — clearing /V keeps the appearance stream but
    omits the show-text operator."""
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 12 Tf 0 g")
    tf.set_value("", regenerate_appearance=True)

    body = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"Tj" not in body


def test_default_appearance_inherited_from_acroform(
    acro_form: PDAcroForm,
) -> None:
    """testDefaultAppearance — when the field has no /DA, the AcroForm's
    /DA is used (inheritable)."""
    acro_form.set_default_appearance("/Helv 14 Tf 0 g")
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 30))
    tf.set_value("inherited", regenerate_appearance=True)

    body = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"14 Tf" in body


# ---------- text field — multi-line ----------


def test_multiline_field_wraps(acro_form: PDAcroForm) -> None:
    """testMultilineField — multi-line content emits multiple Tj ops with
    per-line Td advance."""
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 60))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_multiline(True)
    tf.set_value("alpha\nbeta\ngamma", regenerate_appearance=True)

    body = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert body.count(b"Tj") == 3
    assert b"Td" in body


# ---------- text field — comb ----------


def test_comb_field_emits_one_show_per_cell(
    acro_form: PDAcroForm,
) -> None:
    """testCombField — /Comb mode emits one Tj per cell."""
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_comb(True)
    tf.set_max_len(4)
    tf.set_value("WXYZ", regenerate_appearance=True)

    body = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert body.count(b"Tj") == 4


# ---------- text field — password ----------


def test_password_field_masks_content(acro_form: PDAcroForm) -> None:
    """testPasswordField — visible glyphs are asterisks, never the value."""
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_password(True)
    tf.set_value("topsecret", regenerate_appearance=True)

    body = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"topsecret" not in body
    assert b"*********" in body


# ---------- list-box ----------


def test_listbox_renders_all_options(acro_form: PDAcroForm) -> None:
    """testListBox — list boxes lay out every option, not just the
    selected ones, scrolled by /TI."""
    lb = PDListBox(acro_form)
    lb.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 80))
    lb.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["alpha", "beta", "gamma"])
    lb.set_value("beta", regenerate_appearance=True)

    body = (
        lb.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"alpha" in body
    assert b"beta" in body
    assert b"gamma" in body
    # selection highlight — upstream HIGHLIGHT_COLOR is {153/255, 193/255, 215/255}
    # emitted to 4 decimal places: the appearance content stream extends
    # PDAbstractContentStream (formatDecimal max-fraction-digits=4), not the
    # 5-digit PDPageContentStream. Oracle-confirmed: "0.6 0.7569 0.8431 rg".
    assert b"0.6 0.7569 0.8431" in body


# ---------- combo box ----------


def test_combo_box_renders_selected_value(acro_form: PDAcroForm) -> None:
    cb = PDComboBox(acro_form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 20))
    cb.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    cb.set_options(["x", "y", "z"])
    cb.set_value("y", regenerate_appearance=True)

    body = (
        cb.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"y" in body


# ---------- check box / radio ----------


def test_check_box_two_state_subdict(acro_form: PDAcroForm) -> None:
    """testCheckBoxAppearance — check-box widget gets a two-state /AP/N."""
    cb = PDCheckBox(acro_form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 16, 16))
    PDAppearanceGenerator().generate(cb)
    n = (
        cb.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
    )
    assert isinstance(n, COSDictionary)
    keys = {k.name for k in n.key_set()}
    assert "Yes" in keys
    assert "Off" in keys


def test_radio_button_filled_circle(acro_form: PDAcroForm) -> None:
    rb = PDRadioButton(acro_form)
    rb.get_cos_object().set_item(_RECT, _rect(0, 0, 16, 16))
    PDAppearanceGenerator().generate(rb)
    n = (
        rb.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
    )
    yes_stream = n.get_dictionary_object(COSName.get_pdf_name("Yes"))
    body = yes_stream.create_input_stream().read()
    assert b" c\n" in body  # cubic bezier curves drawn for the circle
    assert b"f\n" in body  # filled


# ---------- push button ----------


def test_push_button_with_caption(acro_form: PDAcroForm) -> None:
    pb = PDPushButton(acro_form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 30))
    mk = COSDictionary()
    mk.set_string(COSName.get_pdf_name("CA"), "Submit")
    cos.set_item(_MK, mk)

    PDAppearanceGenerator().generate(pb)

    body = (
        pb.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"Submit" in body


# ---------- signature field ----------


def test_unsigned_signature_placeholder(acro_form: PDAcroForm) -> None:
    """Empty sig widget gets the "Click to sign" placeholder + dashed border."""
    sig = PDSignatureField(acro_form)
    sig.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    PDAppearanceGenerator().generate(sig)

    body = (
        sig.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    # Wave 1374 — placeholder updated from "Sign here" to "Click to sign"
    # to match upstream ``PDVisibleSigBuilder`` prompt.
    assert b"Click to sign" in body


# Skipped upstream tests (Java plumbing not relevant to lite port):
# - testCustomFont — requires PDF-loading + custom-font /DR resolution.
# - testFontSelection — same; needs a /Resources walk we haven't ported.
