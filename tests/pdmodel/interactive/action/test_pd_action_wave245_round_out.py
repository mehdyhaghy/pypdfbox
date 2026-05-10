"""Wave 245 round-out — small remaining gaps on
:class:`PDActionSubmitForm` (public flag-bit constants, ``add_field``,
``clear_flags``, ``has_flag`` / ``set_flag``) and
:class:`PDActionEmbeddedGoTo` (``set_open_in_new_window(None)`` removing
``/NewWindow`` to mirror upstream ``setOpenInNewWindow(null)``)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_F = COSName.get_pdf_name("F")
_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")
_FIELDS = COSName.get_pdf_name("Fields")
_FLAGS = COSName.get_pdf_name("Flags")
_NEW_WINDOW = COSName.get_pdf_name("NewWindow")


# ---------- PDActionSubmitForm flag-bit class constants ----------


def test_flag_constants_match_table_237_bit_positions() -> None:
    """The class-level ``FLAG_*`` constants must match Table 237 bit
    positions exactly (1 << (bit - 1))."""
    assert PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE == 1 << 0
    assert PDActionSubmitForm.FLAG_INCLUDE_NO_VALUE_FIELDS == 1 << 1
    assert PDActionSubmitForm.FLAG_EXPORT_FORMAT == 1 << 2
    assert PDActionSubmitForm.FLAG_GET_METHOD == 1 << 3
    assert PDActionSubmitForm.FLAG_SUBMIT_COORDINATES == 1 << 4
    assert PDActionSubmitForm.FLAG_XFDF == 1 << 5
    assert PDActionSubmitForm.FLAG_INCLUDE_APPEND_SAVES == 1 << 6
    assert PDActionSubmitForm.FLAG_INCLUDE_ANNOTATIONS == 1 << 7
    assert PDActionSubmitForm.FLAG_SUBMIT_PDF == 1 << 8
    assert PDActionSubmitForm.FLAG_CANONICAL_FORMAT == 1 << 9
    assert PDActionSubmitForm.FLAG_EXCL_NON_USER_ANNOTS == 1 << 10
    assert PDActionSubmitForm.FLAG_EXCL_F_KEY == 1 << 11
    # Bit 13 (index 12) is reserved per the spec — skipped.
    assert PDActionSubmitForm.FLAG_EMBED_FORM == 1 << 13


def test_flag_constants_are_distinct() -> None:
    """No two flag constants share a bit."""
    constants = [
        PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE,
        PDActionSubmitForm.FLAG_INCLUDE_NO_VALUE_FIELDS,
        PDActionSubmitForm.FLAG_EXPORT_FORMAT,
        PDActionSubmitForm.FLAG_GET_METHOD,
        PDActionSubmitForm.FLAG_SUBMIT_COORDINATES,
        PDActionSubmitForm.FLAG_XFDF,
        PDActionSubmitForm.FLAG_INCLUDE_APPEND_SAVES,
        PDActionSubmitForm.FLAG_INCLUDE_ANNOTATIONS,
        PDActionSubmitForm.FLAG_SUBMIT_PDF,
        PDActionSubmitForm.FLAG_CANONICAL_FORMAT,
        PDActionSubmitForm.FLAG_EXCL_NON_USER_ANNOTS,
        PDActionSubmitForm.FLAG_EXCL_F_KEY,
        PDActionSubmitForm.FLAG_EMBED_FORM,
    ]
    assert len(set(constants)) == len(constants)


def test_flag_constants_drive_named_accessors() -> None:
    """The class-level constants are the same masks the named predicates
    flip — composing flags via the constants must be observable through
    the named accessors."""
    action = PDActionSubmitForm()
    action.set_flags(
        PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE
        | PDActionSubmitForm.FLAG_XFDF
        | PDActionSubmitForm.FLAG_EMBED_FORM
    )
    assert action.is_include() is True
    assert action.is_xfdf() is True
    assert action.is_embed_form() is True
    assert action.is_export_format() is False
    assert action.is_get_method() is False


# ---------- PDActionSubmitForm.has_flag / set_flag ----------


def test_has_flag_returns_false_when_bit_clear() -> None:
    action = PDActionSubmitForm()
    assert action.has_flag(PDActionSubmitForm.FLAG_GET_METHOD) is False


def test_has_flag_returns_true_when_bit_set() -> None:
    action = PDActionSubmitForm()
    action.set_get_method(True)
    assert action.has_flag(PDActionSubmitForm.FLAG_GET_METHOD) is True


def test_has_flag_requires_all_bits_in_mask() -> None:
    """``has_flag`` returns ``True`` only when *all* bits in the mask are
    set — partial overlap returns ``False``."""
    action = PDActionSubmitForm()
    action.set_include(True)  # bit 1 only
    mask = (
        PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE
        | PDActionSubmitForm.FLAG_XFDF
    )
    assert action.has_flag(mask) is False
    action.set_xfdf(True)
    assert action.has_flag(mask) is True


def test_set_flag_public_round_trip() -> None:
    """The public ``set_flag`` is observable via ``has_flag`` and the
    named predicates."""
    action = PDActionSubmitForm()
    action.set_flag(PDActionSubmitForm.FLAG_SUBMIT_PDF, True)
    assert action.has_flag(PDActionSubmitForm.FLAG_SUBMIT_PDF) is True
    assert action.is_submit_pdf() is True
    action.set_flag(PDActionSubmitForm.FLAG_SUBMIT_PDF, False)
    assert action.has_flag(PDActionSubmitForm.FLAG_SUBMIT_PDF) is False


def test_set_flag_combined_mask_sets_all_bits() -> None:
    """A combined mask flips every bit in it at once."""
    action = PDActionSubmitForm()
    mask = (
        PDActionSubmitForm.FLAG_EXPORT_FORMAT
        | PDActionSubmitForm.FLAG_GET_METHOD
        | PDActionSubmitForm.FLAG_INCLUDE_ANNOTATIONS
    )
    action.set_flag(mask, True)
    assert action.is_export_format() is True
    assert action.is_get_method() is True
    assert action.is_include_annotations() is True
    # And clearing the same combined mask clears them all.
    action.set_flag(mask, False)
    assert action.is_export_format() is False
    assert action.is_get_method() is False
    assert action.is_include_annotations() is False


# ---------- PDActionSubmitForm.clear_flags ----------


def test_clear_flags_resets_to_zero() -> None:
    """``clear_flags`` zeroes the bit field — every named predicate
    becomes ``False`` afterwards."""
    action = PDActionSubmitForm()
    action.set_include(True)
    action.set_xfdf(True)
    action.set_embed_form(True)
    assert action.get_flags() != 0

    action.clear_flags()
    assert action.get_flags() == 0
    assert action.is_include() is False
    assert action.is_xfdf() is False
    assert action.is_embed_form() is False


def test_clear_flags_writes_zero_into_underlying_dict() -> None:
    """``clear_flags`` sets ``/Flags = 0`` rather than removing the entry
    (mirrors upstream ``setFlags(0)``)."""
    action = PDActionSubmitForm()
    action.set_flags(0xFF)
    action.clear_flags()
    assert action.get_cos_object().get_int(_FLAGS, -1) == 0


# ---------- PDActionSubmitForm.add_field ----------


def test_add_field_creates_array_when_absent() -> None:
    """Calling ``add_field`` on an action with no ``/Fields`` creates the
    array on demand."""
    action = PDActionSubmitForm()
    assert action.get_cos_fields() is None

    form = PDAcroForm()
    fd = COSDictionary()
    fd.set_item(_FT, COSName.get_pdf_name("Tx"))
    fd.set_string(_T, "first")
    field = PDTextField(form, fd, None)

    action.add_field(field)
    fields = action.get_cos_fields()
    assert isinstance(fields, COSArray)
    assert fields.size() == 1
    assert fields.get_object(0) is fd


def test_add_field_appends_to_existing_array() -> None:
    """Successive ``add_field`` calls accumulate in the same array."""
    action = PDActionSubmitForm()

    form = PDAcroForm()
    fd1 = COSDictionary()
    fd1.set_item(_FT, COSName.get_pdf_name("Tx"))
    fd1.set_string(_T, "first")
    fd2 = COSDictionary()
    fd2.set_item(_FT, COSName.get_pdf_name("Tx"))
    fd2.set_string(_T, "second")

    action.add_field(PDTextField(form, fd1, None))
    action.add_field(PDTextField(form, fd2, None))

    fields = action.get_cos_fields()
    assert isinstance(fields, COSArray)
    assert fields.size() == 2
    assert fields.get_object(0) is fd1
    assert fields.get_object(1) is fd2


def test_add_field_accepts_cos_string_for_qualified_name() -> None:
    """PDF 32000-1 §12.7.5.2 permits fully-qualified field names in
    ``/Fields`` — ``add_field`` accepts a ``COSString`` verbatim."""
    action = PDActionSubmitForm()
    qualified = COSString("ChildForm.username")
    action.add_field(qualified)
    fields = action.get_cos_fields()
    assert isinstance(fields, COSArray)
    assert fields.size() == 1
    assert fields.get_object(0) is qualified


def test_add_field_rejects_invalid_type() -> None:
    """``add_field`` rejects non-PDField / non-COSBase entries with a
    clear ``TypeError``."""
    import pytest

    action = PDActionSubmitForm()
    with pytest.raises(TypeError, match="PDField or COSBase"):
        action.add_field("plain-string-not-cosstring")  # type: ignore[arg-type]


def test_add_field_after_explicit_set_fields_round_trips() -> None:
    """``set_fields`` then ``add_field`` extends the same array."""
    action = PDActionSubmitForm()

    form = PDAcroForm()
    fd1 = COSDictionary()
    fd1.set_item(_FT, COSName.get_pdf_name("Tx"))
    fd1.set_string(_T, "first")
    fd2 = COSDictionary()
    fd2.set_item(_FT, COSName.get_pdf_name("Tx"))
    fd2.set_string(_T, "second")

    action.set_fields([PDTextField(form, fd1, None)])
    action.add_field(PDTextField(form, fd2, None))

    fields = action.get_cos_fields()
    assert isinstance(fields, COSArray)
    assert fields.size() == 2


# ---------- PDActionEmbeddedGoTo.set_open_in_new_window(None) ----------


def test_set_open_in_new_window_none_removes_entry() -> None:
    """``set_open_in_new_window(None)`` strips ``/NewWindow`` — mirrors
    upstream ``setOpenInNewWindow(null)`` which routes to the same
    "remove the entry to defer to user preference" branch."""
    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(True)
    assert action.get_cos_object().contains_key(_NEW_WINDOW)

    action.set_open_in_new_window(None)
    assert not action.get_cos_object().contains_key(_NEW_WINDOW)
    # And the tri-state observer reports USER_PREFERENCE.
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_set_open_in_new_window_none_idempotent_when_absent() -> None:
    """Calling with ``None`` when ``/NewWindow`` isn't there is a no-op."""
    action = PDActionEmbeddedGoTo()
    assert not action.get_cos_object().contains_key(_NEW_WINDOW)
    action.set_open_in_new_window(None)
    assert not action.get_cos_object().contains_key(_NEW_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_set_open_in_new_window_user_preference_matches_none() -> None:
    """:attr:`OpenMode.USER_PREFERENCE` and ``None`` are equivalent —
    both remove ``/NewWindow``."""
    action_a = PDActionEmbeddedGoTo()
    action_a.set_open_in_new_window(True)
    action_a.set_open_in_new_window(None)

    action_b = PDActionEmbeddedGoTo()
    action_b.set_open_in_new_window(True)
    action_b.set_open_in_new_window(OpenMode.USER_PREFERENCE)

    assert not action_a.get_cos_object().contains_key(_NEW_WINDOW)
    assert not action_b.get_cos_object().contains_key(_NEW_WINDOW)
