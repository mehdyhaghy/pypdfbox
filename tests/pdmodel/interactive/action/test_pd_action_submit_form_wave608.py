from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)


@pytest.mark.parametrize(
    ("mask", "getter_name", "setter_name"),
    [
        (
            PDActionSubmitForm.FLAG_SUBMIT_COORDINATES,
            "is_submit_coordinates",
            "set_submit_coordinates",
        ),
        (
            PDActionSubmitForm.FLAG_INCLUDE_APPEND_SAVES,
            "is_include_append_saves",
            "set_include_append_saves",
        ),
        (
            PDActionSubmitForm.FLAG_INCLUDE_ANNOTATIONS,
            "is_include_annotations",
            "set_include_annotations",
        ),
        (PDActionSubmitForm.FLAG_SUBMIT_PDF, "is_submit_pdf", "set_submit_pdf"),
        (
            PDActionSubmitForm.FLAG_CANONICAL_FORMAT,
            "is_canonical_format",
            "set_canonical_format",
        ),
        (
            PDActionSubmitForm.FLAG_EXCL_NON_USER_ANNOTS,
            "is_excl_non_user_annots",
            "set_excl_non_user_annots",
        ),
        (PDActionSubmitForm.FLAG_EXCL_F_KEY, "is_excl_f_key", "set_excl_f_key"),
    ],
)
def test_wave608_remaining_named_flag_accessors_round_trip(
    mask: int, getter_name: str, setter_name: str
) -> None:
    action = PDActionSubmitForm()
    getter = getattr(action, getter_name)
    setter = getattr(action, setter_name)

    assert getter() is False

    setter(True)

    assert getter() is True
    assert action.get_flags() == mask

    setter(False)

    assert getter() is False
    assert action.get_flags() == 0


def test_wave608_class_flag_constants_match_table_237_bit_masks() -> None:
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
    assert PDActionSubmitForm.FLAG_EMBED_FORM == 1 << 13


def test_wave608_has_flag_requires_every_requested_bit() -> None:
    action = PDActionSubmitForm()
    action.set_flags(
        PDActionSubmitForm.FLAG_SUBMIT_PDF
        | PDActionSubmitForm.FLAG_CANONICAL_FORMAT
    )

    assert action.has_flag(PDActionSubmitForm.FLAG_SUBMIT_PDF) is True
    assert (
        action.has_flag(
            PDActionSubmitForm.FLAG_SUBMIT_PDF
            | PDActionSubmitForm.FLAG_CANONICAL_FORMAT
        )
        is True
    )
    assert (
        action.has_flag(
            PDActionSubmitForm.FLAG_SUBMIT_PDF
            | PDActionSubmitForm.FLAG_EXCL_F_KEY
        )
        is False
    )


def test_wave608_set_flag_clears_combined_mask_without_disturbing_other_bits() -> None:
    action = PDActionSubmitForm()
    action.set_flags(
        PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE
        | PDActionSubmitForm.FLAG_SUBMIT_PDF
        | PDActionSubmitForm.FLAG_EXCL_F_KEY
    )

    action.set_flag(
        PDActionSubmitForm.FLAG_SUBMIT_PDF | PDActionSubmitForm.FLAG_EXCL_F_KEY,
        False,
    )

    assert action.get_flags() == PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE
    assert action.is_include() is True
    assert action.is_submit_pdf() is False
    assert action.is_excl_f_key() is False
