from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_field_factory import PDFieldFactory
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDFieldStub
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FT = COSName.get_pdf_name("FT")
_FF = COSName.get_pdf_name("Ff")
_KIDS = COSName.get_pdf_name("Kids")
_T = COSName.get_pdf_name("T")


def _make_field(ft: str | None, ff: int | None = None) -> COSDictionary:
    d = COSDictionary()
    if ft is not None:
        d.set_name(_FT, ft)
    if ff is not None:
        d.set_int(_FF, ff)
    return d


# ---------- /FT dispatch ----------


def test_dispatch_text_field() -> None:
    form = PDAcroForm()
    field = _make_field("Tx")
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDTextField)


def test_dispatch_button_no_flags_is_check_box() -> None:
    form = PDAcroForm()
    field = _make_field("Btn")
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDCheckBox)
    assert not isinstance(result, (PDPushButton, PDRadioButton))


def test_dispatch_button_pushbutton_bit_17() -> None:
    form = PDAcroForm()
    # bit 17 (1-indexed) == 1 << 16 == 65536
    assert PDButton.FLAG_PUSHBUTTON == 1 << 16 == 65536
    field = _make_field("Btn", ff=PDButton.FLAG_PUSHBUTTON)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDPushButton)


def test_dispatch_button_radio_bit_16() -> None:
    form = PDAcroForm()
    # bit 16 (1-indexed) == 1 << 15 == 32768
    assert PDButton.FLAG_RADIO == 1 << 15 == 32768
    field = _make_field("Btn", ff=PDButton.FLAG_RADIO)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDRadioButton)


def test_dispatch_choice_no_flags_is_list_box() -> None:
    form = PDAcroForm()
    field = _make_field("Ch")
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDListBox)
    assert not isinstance(result, PDComboBox)


def test_dispatch_choice_combo_bit_18() -> None:
    form = PDAcroForm()
    # bit 18 (1-indexed) == 1 << 17 == 131072
    assert PDChoice.FLAG_COMBO == 1 << 17 == 131072
    field = _make_field("Ch", ff=PDChoice.FLAG_COMBO)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDComboBox)


def test_dispatch_signature_field() -> None:
    form = PDAcroForm()
    field = _make_field("Sig")
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDSignatureField)


# ---------- inheritable /FT ----------


def test_dispatch_child_inherits_ft_from_parent() -> None:
    """A child field with no own /FT should inherit /FT from /Parent."""
    form = PDAcroForm()
    parent_dict = _make_field("Tx")
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()  # no /FT of its own
    result = PDFieldFactory.create_field(form, child_dict, parent)
    assert isinstance(result, PDTextField)


def test_dispatch_child_inherits_ft_through_non_terminal_parent() -> None:
    """A terminal child inherits /FT through local-less non-terminal ancestors."""
    form = PDAcroForm()
    grandparent = PDNonTerminalField(form, _make_field("Tx"))
    parent = PDNonTerminalField(form, COSDictionary(), grandparent)
    child_dict = COSDictionary()

    result = PDFieldFactory.create_field(form, child_dict, parent)

    assert isinstance(result, PDTextField)


def test_dispatch_child_inherits_ft_from_form_through_parent() -> None:
    """The AcroForm dictionary remains the inheritance fallback with a parent."""
    form = PDAcroForm()
    form.get_cos_object().set_name(_FT, "Tx")
    parent = PDNonTerminalField(form, COSDictionary())
    child_dict = COSDictionary()

    result = PDFieldFactory.create_field(form, child_dict, parent)

    assert isinstance(result, PDTextField)


def test_dispatch_child_inherits_btn_ft_with_combo_flag_irrelevant() -> None:
    """Child inherits /FT /Btn from parent; without /Ff bits → checkbox."""
    form = PDAcroForm()
    parent_dict = _make_field("Btn")
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()
    result = PDFieldFactory.create_field(form, child_dict, parent)
    assert isinstance(result, PDCheckBox)


def test_dispatch_child_inherits_choice_with_combo_flag() -> None:
    """Child inherits /FT and /Ff (combo bit) from parent → combo box."""
    form = PDAcroForm()
    parent_dict = _make_field("Ch", ff=PDChoice.FLAG_COMBO)
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()
    result = PDFieldFactory.create_field(form, child_dict, parent)
    assert isinstance(result, PDComboBox)


# ---------- non-terminal vs unknown fallback ----------


def test_dispatch_no_ft_no_parent_no_kids_falls_back_to_stub() -> None:
    """No /FT, no parent /FT, no /Kids → unknown → fallback PDFieldStub."""
    form = PDAcroForm()
    field = COSDictionary()
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDFieldStub)


def test_dispatch_no_ft_with_field_kids_returns_non_terminal() -> None:
    """No /FT but has /Kids whose entries carry /T (a partial name) → PDNonTerminalField."""
    form = PDAcroForm()
    field = COSDictionary()
    kids = COSArray()
    child = COSDictionary()
    child.set_string(_T, "child")
    kids.add(child)
    field.set_item(_KIDS, kids)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDNonTerminalField)


def test_dispatch_none_field_returns_none() -> None:
    form = PDAcroForm()
    assert PDFieldFactory.create_field(form, None) is None


# ---------- non-terminal kid detection — /T presence (matches upstream) ----------


def test_dispatch_kids_without_t_does_not_classify_as_non_terminal() -> None:
    """Kids that are widget annotations only (no /T) must not turn the parent
    into a non-terminal field. Mirrors upstream's
    ``getString(COSName.T) != null`` check.
    """
    form = PDAcroForm()
    field = _make_field("Tx")  # parent is itself a text field with widget kids
    kids = COSArray()
    widget = COSDictionary()
    widget.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    # No /T on the widget
    kids.add(widget)
    field.set_item(_KIDS, kids)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDTextField)
    assert not isinstance(result, PDNonTerminalField)


def test_dispatch_merged_widget_field_kid_with_t_is_non_terminal() -> None:
    """A kid carrying both /Subtype/Widget AND /T is a (merged) field — the
    parent must be classified as non-terminal. Pypdfbox previously checked
    /Subtype absence and would miss this case.
    """
    form = PDAcroForm()
    field = COSDictionary()  # no /FT
    kids = COSArray()
    merged = COSDictionary()
    merged.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    merged.set_string(_T, "merged_kid")
    kids.add(merged)
    field.set_item(_KIDS, kids)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDNonTerminalField)


def test_dispatch_kids_with_empty_string_t_still_classified_as_field() -> None:
    """Even an empty-string /T qualifies as ``not null`` upstream — pypdfbox
    must agree (``get_string`` returns ``""``, which is not ``None``).
    """
    form = PDAcroForm()
    field = COSDictionary()
    kids = COSArray()
    child = COSDictionary()
    child.set_string(_T, "")
    kids.add(child)
    field.set_item(_KIDS, kids)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDNonTerminalField)


def test_dispatch_kids_first_without_t_then_with_t_still_non_terminal() -> None:
    """Detection iterates over /Kids — ANY kid with /T flips the parent to
    non-terminal even when the first kid is widget-only."""
    form = PDAcroForm()
    field = COSDictionary()
    kids = COSArray()
    widget = COSDictionary()
    widget.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    real_kid = COSDictionary()
    real_kid.set_string(_T, "child")
    kids.add(widget)
    kids.add(real_kid)
    field.set_item(_KIDS, kids)
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDNonTerminalField)


def test_dispatch_empty_kids_array_does_not_classify_as_non_terminal() -> None:
    form = PDAcroForm()
    field = _make_field("Tx")
    field.set_item(_KIDS, COSArray())  # empty
    result = PDFieldFactory.create_field(form, field)
    assert isinstance(result, PDTextField)
    assert not isinstance(result, PDNonTerminalField)


# ---------- find_field_type / is_known_field_type ----------


def test_find_field_type_returns_local_ft() -> None:
    field = _make_field("Tx")
    assert PDFieldFactory.find_field_type(field) == "Tx"


def test_find_field_type_walks_parent_chain() -> None:
    grandparent = _make_field("Ch")
    parent = COSDictionary()
    parent.set_item(COSName.get_pdf_name("Parent"), grandparent)
    child = COSDictionary()
    child.set_item(COSName.get_pdf_name("Parent"), parent)
    assert PDFieldFactory.find_field_type(child) == "Ch"


def test_find_field_type_walks_p_when_no_parent() -> None:
    """If /Parent is absent, fall back to /P (matches upstream
    ``getCOSDictionary(PARENT, P)``)."""
    parent = _make_field("Sig")
    child = COSDictionary()
    child.set_item(COSName.get_pdf_name("P"), parent)
    assert PDFieldFactory.find_field_type(child) == "Sig"


def test_find_field_type_returns_none_when_chain_has_no_ft() -> None:
    parent = COSDictionary()
    child = COSDictionary()
    child.set_item(COSName.get_pdf_name("Parent"), parent)
    assert PDFieldFactory.find_field_type(child) is None


def test_find_field_type_breaks_self_cycle_pdfbox_5896() -> None:
    """A dictionary referencing itself via /Parent must terminate (no
    StackOverflow). Mirrors PDFBOX-5896."""
    cyclic = COSDictionary()
    cyclic.set_item(COSName.get_pdf_name("Parent"), cyclic)
    assert PDFieldFactory.find_field_type(cyclic) is None


def test_find_field_type_breaks_two_node_cycle() -> None:
    """Two nodes pointing at each other must also terminate."""
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(COSName.get_pdf_name("Parent"), b)
    b.set_item(COSName.get_pdf_name("Parent"), a)
    assert PDFieldFactory.find_field_type(a) is None


def test_field_type_constants_match_pdf_spec() -> None:
    """Class-level constants must match PDF 32000-1 §12.7.4 wire values."""
    assert PDFieldFactory.FIELD_TYPE_TEXT == "Tx"
    assert PDFieldFactory.FIELD_TYPE_BUTTON == "Btn"
    assert PDFieldFactory.FIELD_TYPE_CHOICE == "Ch"
    assert PDFieldFactory.FIELD_TYPE_SIGNATURE == "Sig"


def test_is_known_field_type_accepts_all_four_constants() -> None:
    for ft in (
        PDFieldFactory.FIELD_TYPE_TEXT,
        PDFieldFactory.FIELD_TYPE_BUTTON,
        PDFieldFactory.FIELD_TYPE_CHOICE,
        PDFieldFactory.FIELD_TYPE_SIGNATURE,
    ):
        assert PDFieldFactory.is_known_field_type(ft) is True


def test_is_known_field_type_rejects_unknown() -> None:
    assert PDFieldFactory.is_known_field_type("Foo") is False
    assert PDFieldFactory.is_known_field_type("") is False
    assert PDFieldFactory.is_known_field_type(None) is False


def test_is_known_field_type_is_case_sensitive() -> None:
    """PDF spec field-type names are case-sensitive — ``tx`` is not ``Tx``."""
    assert PDFieldFactory.is_known_field_type("tx") is False
    assert PDFieldFactory.is_known_field_type("BTN") is False
