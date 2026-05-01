from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_field_factory import PDFieldFactory
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)

_FT = COSName.get_pdf_name("FT")
_FF = COSName.get_pdf_name("Ff")
_DV = COSName.get_pdf_name("DV")
_PARENT = COSName.get_pdf_name("Parent")
_P = COSName.get_pdf_name("P")


# ---------- /DV accessors ----------


def test_non_terminal_get_default_value_absent_returns_none() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    assert nt.get_default_value() is None


def test_non_terminal_set_default_value_round_trip() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    value = COSString("hello")
    nt.set_default_value(value)
    assert nt.get_default_value() is value
    # raw entry on the underlying dictionary
    assert nt.get_cos_object().get_dictionary_object(_DV) is value


def test_non_terminal_set_default_value_none_removes_dv() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_default_value(COSString("x"))
    assert nt.get_default_value() is not None
    nt.set_default_value(None)
    assert nt.get_default_value() is None
    assert _DV not in nt.get_cos_object()


# ---------- /FT non-inheritance ----------


def test_non_terminal_field_type_is_local_only() -> None:
    """PDNonTerminalField.get_field_type returns its OWN /FT only.

    Mirrors upstream — non-terminal fields carry /FT as inheritable
    attribute for descendants but the local accessor doesn't walk up.
    """
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_name(_FT, "Tx")
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()  # no /FT of its own
    child = PDNonTerminalField(form, child_dict, parent)
    # Even though parent has /FT=Tx, child's local field type is None
    assert child.get_field_type() is None
    assert parent.get_field_type() == "Tx"


# ---------- /Ff non-inheritance ----------


def test_non_terminal_field_flags_is_local_only() -> None:
    """PDNonTerminalField.get_field_flags returns its OWN /Ff only."""
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_int(_FF, 12345)
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()
    child = PDNonTerminalField(form, child_dict, parent)
    # Inheritance not consulted: child reports 0
    assert child.get_field_flags() == 0
    assert parent.get_field_flags() == 12345


def test_non_terminal_field_flags_returns_local_int() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_int(_FF, 1 << 5)
    nt = PDNonTerminalField(form, d)
    assert nt.get_field_flags() == 32


# ---------- get_widgets() ----------


def test_non_terminal_widgets_empty_no_kids() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    assert nt.get_widgets() == []


def test_non_terminal_widgets_empty_with_kids() -> None:
    """Even when /Kids is populated, non-terminal fields have no widgets."""
    form = PDAcroForm()
    parent_dict = COSDictionary()
    kids = COSArray()
    child_dict = COSDictionary()
    child_dict.set_string(COSName.get_pdf_name("T"), "child")
    kids.add(child_dict)
    parent_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    nt = PDNonTerminalField(form, parent_dict)
    assert nt.get_widgets() == []


# ---------- PDFieldFactory.find_field_type ----------


def test_find_field_type_local() -> None:
    d = COSDictionary()
    d.set_name(_FT, "Btn")
    assert PDFieldFactory.find_field_type(d) == "Btn"


def test_find_field_type_walks_parent() -> None:
    parent = COSDictionary()
    parent.set_name(_FT, "Tx")
    child = COSDictionary()
    child.set_item(_PARENT, parent)
    assert PDFieldFactory.find_field_type(child) == "Tx"


def test_find_field_type_walks_p_when_no_parent() -> None:
    """Falls back to /P if /Parent is absent (per upstream)."""
    p_dict = COSDictionary()
    p_dict.set_name(_FT, "Sig")
    child = COSDictionary()
    child.set_item(_P, p_dict)
    assert PDFieldFactory.find_field_type(child) == "Sig"


def test_find_field_type_missing_returns_none() -> None:
    d = COSDictionary()
    assert PDFieldFactory.find_field_type(d) is None


def test_find_field_type_cycle_detection() -> None:
    """PDFBOX-5896 — a /Parent cycle must not loop forever."""
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(_PARENT, b)
    b.set_item(_PARENT, a)
    # Neither has /FT — must terminate and return None.
    assert PDFieldFactory.find_field_type(a) is None
    assert PDFieldFactory.find_field_type(b) is None


def test_find_field_type_self_cycle_detection() -> None:
    """A dictionary whose /Parent is itself must terminate."""
    a = COSDictionary()
    a.set_item(_PARENT, a)
    assert PDFieldFactory.find_field_type(a) is None


def test_find_field_type_two_level_chain() -> None:
    grand = COSDictionary()
    grand.set_name(_FT, "Ch")
    parent = COSDictionary()
    parent.set_item(_PARENT, grand)
    child = COSDictionary()
    child.set_item(_PARENT, parent)
    assert PDFieldFactory.find_field_type(child) == "Ch"


# ---------- /Ff value type guard ----------


def test_non_terminal_field_flags_non_int_returns_zero() -> None:
    """Defensive — if /Ff somehow holds a non-COSInteger, fall back to 0."""
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_FF, COSString("nope"))
    nt = PDNonTerminalField(form, d)
    assert nt.get_field_flags() == 0


# ---------- regression — /Ff stored as plain int still works ----------


def test_non_terminal_field_flags_via_cos_integer() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_FF, COSInteger.get(99))
    nt = PDNonTerminalField(form, d)
    assert nt.get_field_flags() == 99
