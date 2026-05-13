"""Tests for :class:`EncryptFlag`."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.debugger.flagbitspane.encrypt_flag import EncryptFlag
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission

_P = COSName.get_pdf_name("P")


def _enc_dict(p_value: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_P, COSInteger.get(p_value))
    return d


def test_flag_type():
    assert EncryptFlag(_enc_dict(-1)).get_flag_type() == "Encrypt flag"


def test_flag_value_no_space_before_colon():
    # Upstream uses "Flag value:" with no space — verify the verbatim port.
    assert EncryptFlag(_enc_dict(-4)).get_flag_value() == "Flag value:-4"


def test_table_shape_owner():
    rows = EncryptFlag(_enc_dict(-1)).get_flag_bits()
    positions = [r[0] for r in rows]
    names = [r[1] for r in rows]
    assert positions == [3, 4, 5, 6, 9, 10, 11, 12]
    assert names == [
        "can print",
        "can modify",
        "can extract content",
        "can modify annotations",
        "can fill in form fields",
        "can extract for accessibility",
        "can assemble document",
        "can print faithful",
    ]
    # Owner (-1 == all bits set) should be True for every right.
    assert all(r[2] for r in rows)


def test_matches_access_permission():
    # Pick a /P value mid-spectrum and double-check the third column
    # exactly matches AccessPermission's decoded booleans.
    p = -1852  # arbitrary signed int similar to real-world /P values
    rows = EncryptFlag(_enc_dict(p)).get_flag_bits()
    ap = AccessPermission(p)
    expected = {
        "can print": ap.can_print(),
        "can modify": ap.can_modify(),
        "can extract content": ap.can_extract_content(),
        "can modify annotations": ap.can_modify_annotations(),
        "can fill in form fields": ap.can_fill_in_form(),
        "can extract for accessibility": ap.can_extract_for_accessibility(),
        "can assemble document": ap.can_assemble_document(),
        "can print faithful": ap.can_print_faithful(),
    }
    for _bit, name, value in rows:
        assert value is expected[name], name
