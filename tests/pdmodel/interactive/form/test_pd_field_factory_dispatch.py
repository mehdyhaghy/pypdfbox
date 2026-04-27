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
    """No /FT but has /Kids whose entries are field-like (no /Subtype) → PDNonTerminalField."""
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
