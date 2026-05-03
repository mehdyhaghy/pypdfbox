"""Wave 265 round-out tests for :class:`PDActionResetForm` — exclude
predicate, has-* / is-empty / is-valid helpers, and clear-* surface
complementing the existing include/exclude flag accessors."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionResetForm

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_FLAGS: COSName = COSName.get_pdf_name("Flags")
_S: COSName = COSName.get_pdf_name("S")


# ---------- is_exclude / set_exclude ----------


def test_is_exclude_default_false_on_fresh_action() -> None:
    """A freshly-built ResetForm action defaults to the include semantic
    — the exclude predicate is the inverse, so it starts ``False``."""
    action = PDActionResetForm()
    assert action.is_exclude() is False


def test_is_exclude_true_when_flag_bit_set() -> None:
    action = PDActionResetForm()
    action.set_flags(PDActionResetForm.FLAG_INCLUDE_EXCLUDE)
    assert action.is_exclude() is True
    assert action.is_include() is True  # same bit, inverse semantic name


def test_is_exclude_inverse_of_is_include() -> None:
    """``is_exclude`` and ``is_include`` return the same boolean — both
    expose bit 1 of ``/Flags`` (PDF 32000-1 §12.7.5.3 Table 239) under
    different polarity-named accessors so call sites can read either
    direction naturally."""
    action = PDActionResetForm()
    for flag_value in (0, 1, 2, 3, 7):
        action.set_flags(flag_value)
        assert action.is_exclude() == action.is_include()


def test_set_exclude_round_trips_each_polarity() -> None:
    action = PDActionResetForm()

    action.set_exclude(True)
    assert action.is_exclude() is True
    assert (action.get_flags() & PDActionResetForm.FLAG_INCLUDE_EXCLUDE) != 0

    action.set_exclude(False)
    assert action.is_exclude() is False
    assert (action.get_flags() & PDActionResetForm.FLAG_INCLUDE_EXCLUDE) == 0


def test_set_exclude_preserves_other_flag_bits() -> None:
    """Toggling the exclude polarity must not stomp other flag bits — the
    OR/AND-NOT pattern in :meth:`set_include` masks bit 1 only."""
    action = PDActionResetForm()
    action.set_flags(0b1010)  # bits 2 and 4 set, bit 1 clear

    action.set_exclude(True)
    assert action.get_flags() == 0b1011  # bit 1 added, others kept

    action.set_exclude(False)
    assert action.get_flags() == 0b1010  # bit 1 cleared, others kept


# ---------- has_fields ----------


def test_has_fields_false_on_fresh_action() -> None:
    action = PDActionResetForm()
    assert action.has_fields() is False


def test_has_fields_true_when_array_set() -> None:
    action = PDActionResetForm()
    action.set_fields(COSArray())
    assert action.has_fields() is True


def test_has_fields_true_when_array_non_empty() -> None:
    action = PDActionResetForm()
    array = COSArray()
    array.add(COSString("field.name"))
    action.set_fields(array)
    assert action.has_fields() is True


def test_has_fields_false_when_entry_not_array() -> None:
    """``/Fields`` stored as a non-array (spec-invalid) reports as absent
    — :meth:`get_fields` already filters non-array entries to ``None``."""
    action = PDActionResetForm()
    action.get_cos_object().set_string(_FIELDS, "wrong-type")
    assert action.has_fields() is False


# ---------- has_flags ----------


def test_has_flags_false_on_fresh_action() -> None:
    action = PDActionResetForm()
    assert action.has_flags() is False


def test_has_flags_true_after_set_flags() -> None:
    action = PDActionResetForm()
    action.set_flags(0)
    # /Flags = 0 is still an explicitly-present entry.
    assert action.has_flags() is True


def test_get_flags_default_zero_when_absent() -> None:
    """When ``/Flags`` is absent the spec default is 0 — :meth:`get_flags`
    surfaces that even though :meth:`has_flags` is ``False``."""
    action = PDActionResetForm()
    assert action.get_flags() == 0
    assert action.has_flags() is False


# ---------- is_valid ----------


def test_is_valid_true_for_default_construction() -> None:
    action = PDActionResetForm()
    assert action.is_valid() is True


def test_is_valid_false_when_subtype_overwritten() -> None:
    action = PDActionResetForm()
    action.set_sub_type("NotResetForm")
    assert action.is_valid() is False


def test_is_valid_for_existing_dict_with_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "ResetForm")
    action = PDActionResetForm(raw)
    assert action.is_valid() is True


def test_is_valid_false_for_dict_missing_subtype() -> None:
    """The existing-dict constructor branch wraps the dictionary as-is
    without seeding ``/S`` — mirrors upstream ``PDActionResetForm(COSDictionary)``."""
    raw = COSDictionary()
    action = PDActionResetForm(raw)
    assert action.is_valid() is False


# ---------- is_empty ----------


def test_is_empty_true_when_fields_absent() -> None:
    action = PDActionResetForm()
    assert action.is_empty() is True


def test_is_empty_true_when_fields_present_but_empty_array() -> None:
    action = PDActionResetForm()
    action.set_fields(COSArray())
    assert action.is_empty() is True


def test_is_empty_false_when_fields_has_entries() -> None:
    action = PDActionResetForm()
    array = COSArray()
    array.add(COSString("field.first"))
    array.add(COSString("field.second"))
    action.set_fields(array)
    assert action.is_empty() is False


# ---------- clear_fields / clear_flags ----------


def test_clear_fields_removes_entry() -> None:
    action = PDActionResetForm()
    array = COSArray()
    array.add(COSString("field.x"))
    action.set_fields(array)
    assert action.has_fields()

    action.clear_fields()
    assert action.has_fields() is False
    assert action.get_fields() is None


def test_clear_fields_idempotent_when_absent() -> None:
    action = PDActionResetForm()
    action.clear_fields()
    action.clear_fields()
    assert action.has_fields() is False


def test_clear_flags_removes_entry_and_resets_default() -> None:
    action = PDActionResetForm()
    action.set_flags(0b101)
    assert action.has_flags()

    action.clear_flags()
    assert action.has_flags() is False
    assert action.get_flags() == 0


def test_clear_flags_resets_include_exclude_polarity() -> None:
    """Clearing ``/Flags`` reverts to the default include semantic — the
    bit gets dropped along with the entry."""
    action = PDActionResetForm()
    action.set_exclude(True)
    assert action.is_exclude() is True

    action.clear_flags()
    assert action.is_exclude() is False
    assert action.is_include() is False


def test_clear_flags_idempotent_when_absent() -> None:
    action = PDActionResetForm()
    action.clear_flags()
    action.clear_flags()
    assert action.has_flags() is False
