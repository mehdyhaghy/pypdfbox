from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_reset_form import (
    PDActionResetForm,
)


_FIELDS: COSName = COSName.get_pdf_name("Fields")
_FLAGS: COSName = COSName.get_pdf_name("Flags")
_S: COSName = COSName.get_pdf_name("S")


def test_default_sub_type_is_reset_form() -> None:
    """Constructing without an existing dict stamps ``/S = /ResetForm``."""
    action = PDActionResetForm()
    assert action.get_cos_object().get_name(_S) == "ResetForm"


def test_get_fields_returns_none_when_absent() -> None:
    """``/Fields`` absent yields ``None`` from :meth:`get_fields`."""
    action = PDActionResetForm()
    assert action.get_fields() is None


def test_get_fields_wraps_fields_entries() -> None:
    """:meth:`get_fields` returns the ``/Fields`` ``COSArray`` containing
    the stored entries, preserving order and identity of each entry."""
    field_a = COSDictionary()
    field_b = COSDictionary()
    name_ref = COSString("partial.name")
    fields = COSArray([field_a, field_b, name_ref])

    action = PDActionResetForm()
    action.set_fields(fields)

    resolved = action.get_fields()
    assert resolved is fields
    assert resolved is not None
    assert resolved.size() == 3
    assert resolved.get_object(0) is field_a
    assert resolved.get_object(1) is field_b
    assert resolved.get_object(2) is name_ref


def test_set_fields_none_removes_entry() -> None:
    """Passing ``None`` to :meth:`set_fields` clears ``/Fields``."""
    action = PDActionResetForm()
    action.set_fields(COSArray([COSDictionary()]))
    assert action.get_fields() is not None

    action.set_fields(None)
    assert action.get_fields() is None
    assert action.get_cos_object().get_dictionary_object(_FIELDS) is None


def test_get_flags_default_zero() -> None:
    """``/Flags`` defaults to ``0`` when the entry is absent
    (PDF 32000-1 §12.7.5.3 Table 239)."""
    action = PDActionResetForm()
    assert action.get_flags() == 0


def test_set_flags_round_trip() -> None:
    """:meth:`set_flags` writes ``/Flags`` as an integer that
    :meth:`get_flags` reads back identically."""
    action = PDActionResetForm()

    action.set_flags(0)
    assert action.get_flags() == 0
    raw = action.get_cos_object().get_dictionary_object(_FLAGS)
    assert isinstance(raw, COSInteger)
    assert raw.value == 0

    action.set_flags(7)
    assert action.get_flags() == 7

    action.set_flags(0xDEAD)
    assert action.get_flags() == 0xDEAD


def test_is_include_default_false() -> None:
    """``/Flags`` bit 1 defaults to clear, so :meth:`is_include` is
    ``False`` for a fresh action."""
    action = PDActionResetForm()
    assert action.is_include() is False


def test_is_include_round_trip() -> None:
    """Toggling :meth:`set_include` flips bit 1 of ``/Flags`` while
    leaving the other flag bits untouched."""
    action = PDActionResetForm()

    # Pre-populate other bits to verify they survive the toggle.
    action.set_flags(0b1010)  # bits 2 + 4 set, bit 1 clear
    assert action.is_include() is False

    action.set_include(True)
    assert action.is_include() is True
    assert action.get_flags() == 0b1011  # bit 1 added

    action.set_include(False)
    assert action.is_include() is False
    assert action.get_flags() == 0b1010  # bit 1 cleared, others intact

    # Idempotent.
    action.set_include(False)
    assert action.is_include() is False
    assert action.get_flags() == 0b1010

    action.set_include(True)
    action.set_include(True)
    assert action.is_include() is True
    assert action.get_flags() == 0b1011


def test_construct_from_existing_dictionary_preserves_entries() -> None:
    """When constructed over an existing ``COSDictionary``, the action
    surfaces its existing ``/Fields`` and ``/Flags`` entries verbatim."""
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("ResetForm"))
    fields = COSArray([COSDictionary()])
    raw.set_item(_FIELDS, fields)
    raw.set_int(_FLAGS, 1)  # include/exclude bit set

    action = PDActionResetForm(raw)

    assert action.get_fields() is fields
    assert action.get_flags() == 1
    assert action.is_include() is True
