"""Round-out tests for ``PDActionResetForm`` — covers Wave 221 additions:
the public ``FLAG_INCLUDE_EXCLUDE`` constant, ``get_field_names``
extractor (PDF 32000-1 §12.7.5.3), and the extended ``set_fields``
overloads accepting :class:`PDField` / :class:`COSBase` lists."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_reset_form import (
    PDActionResetForm,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


_FIELDS = COSName.get_pdf_name("Fields")
_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")


# ---------- FLAG_INCLUDE_EXCLUDE constant ----------


def test_flag_include_exclude_constant_is_bit_one() -> None:
    """The public ``FLAG_INCLUDE_EXCLUDE`` constant is bit 1
    (PDF 32000-1 §12.7.5.3 Table 239) — value ``1``."""
    assert PDActionResetForm.FLAG_INCLUDE_EXCLUDE == 1


def test_flag_include_exclude_round_trips_via_get_flags() -> None:
    """Setting ``FLAG_INCLUDE_EXCLUDE`` directly via :meth:`set_flags`
    flips :meth:`is_include` (parity with the typed flag setter)."""
    action = PDActionResetForm()
    action.set_flags(PDActionResetForm.FLAG_INCLUDE_EXCLUDE)
    assert action.is_include() is True
    action.set_flags(0)
    assert action.is_include() is False


# ---------- get_field_names ----------


def test_get_field_names_empty_when_fields_absent() -> None:
    """No ``/Fields`` entry → :meth:`get_field_names` returns ``[]``."""
    action = PDActionResetForm()
    assert action.get_field_names() == []


def test_get_field_names_extracts_only_string_entries() -> None:
    """Partial / fully-qualified names (``COSString``) are returned in
    array order; dictionary entries are skipped (PDF 32000-1 §12.7.5.3
    permits all three forms — this helper surfaces only the string
    forms which are most commonly consumed at runtime)."""
    action = PDActionResetForm()
    field_dict = COSDictionary()
    array = COSArray(
        [
            COSString("first_name"),
            field_dict,
            COSString("address.zip"),
            COSString("notes"),
        ]
    )
    action.set_fields(array)
    assert action.get_field_names() == ["first_name", "address.zip", "notes"]


def test_get_field_names_returns_empty_for_dict_only_fields() -> None:
    """An array of pure ``COSDictionary`` entries yields ``[]`` —
    field-dict entries are skipped without raising."""
    action = PDActionResetForm()
    action.set_fields(COSArray([COSDictionary(), COSDictionary()]))
    assert action.get_field_names() == []


def test_get_field_names_when_fields_is_wrong_type() -> None:
    """When ``/Fields`` is present but *not* a ``COSArray`` (malformed
    PDF) :meth:`get_field_names` returns ``[]`` rather than raising.
    Mirrors :meth:`get_fields`'s lenient ``None`` return for the same
    case."""
    action = PDActionResetForm()
    # Force a non-array entry to simulate malformed input.
    action.get_cos_object().set_item(_FIELDS, COSString("not-an-array"))
    assert action.get_field_names() == []


# ---------- set_fields list overloads ----------


def test_set_fields_accepts_pd_field_list() -> None:
    """``set_fields`` accepts a list of :class:`PDField` instances;
    the underlying COS dictionaries are stored as the ``/Fields``
    array entries (parity with :class:`PDActionSubmitForm`)."""
    form = PDAcroForm()

    text_dict = COSDictionary()
    text_dict.set_item(_FT, COSName.get_pdf_name("Tx"))
    text_dict.set_string(_T, "user.name")
    text_field = PDTextField(form, text_dict, None)

    action = PDActionResetForm()
    action.set_fields([text_field])

    raw = action.get_fields()
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    assert raw.get_object(0) is text_dict


def test_set_fields_accepts_mixed_cos_base_list() -> None:
    """A list of raw ``COSBase`` entries — including ``COSString``
    field-name references — is wrapped into a ``COSArray`` preserving
    order and identity."""
    name_a = COSString("alpha")
    name_b = COSString("beta")
    field_dict = COSDictionary()

    action = PDActionResetForm()
    action.set_fields([name_a, field_dict, name_b])

    raw = action.get_fields()
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    assert raw.get_object(0) is name_a
    assert raw.get_object(1) is field_dict
    assert raw.get_object(2) is name_b


def test_set_fields_rejects_non_cos_entries() -> None:
    """Passing a list with a non-``COSBase``/non-``PDField`` entry
    raises :class:`TypeError` — guards against silently coercing
    unexpected Python types into the ``/Fields`` array."""
    action = PDActionResetForm()
    with pytest.raises(TypeError):
        action.set_fields(["bare-string"])  # type: ignore[list-item]


def test_set_fields_empty_list_writes_empty_array() -> None:
    """``set_fields([])`` writes an empty ``COSArray`` (distinct from
    ``set_fields(None)`` which removes ``/Fields`` entirely)."""
    action = PDActionResetForm()
    action.set_fields([])

    raw = action.get_fields()
    assert isinstance(raw, COSArray)
    assert raw.size() == 0
    # Round-trip — the entry is *present*, just empty.
    assert action.get_cos_object().get_dictionary_object(_FIELDS) is raw
