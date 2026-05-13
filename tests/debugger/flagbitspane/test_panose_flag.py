"""Tests for :class:`PanoseFlag`."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.debugger.flagbitspane.panose_flag import PanoseFlag

_PANOSE = COSName.get_pdf_name("Panose")


# Twelve-byte block: 2-byte sFamilyClass header + 10-byte PANOSE.
# All zeros means every byte = "Any" in its respective lookup table.
_PANOSE_BLOCK_ALL_ZEROS = bytes(12)

# A more interesting block — choose values that land in defined slots
# (avoids out-of-range IndexError, since upstream tables aren't padded).
_PANOSE_BLOCK_LATIN = bytes(
    [
        0x00,  # sFamilyClass high
        0x00,  # sFamilyClass low
        0x02,  # FamilyKind   == "Latin Text"
        0x0F,  # SerifStyle   == "Rounded"
        0x05,  # Weight       == "Book"
        0x03,  # Proportion   == "Modern"
        0x06,  # Contrast     == "Medium"
        0x04,  # StrokeVar    == "Gradual/Transitional"
        0x02,  # ArmStyle     == "Straight Arms/Horizontal"
        0x01,  # Letterform   == "No Fit"
        0x0D,  # Midline      == "Low/Serifed"
        0x07,  # XHeight      == "Ducking/Large"
    ]
)


def _panose_dict(block: bytes) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_PANOSE, COSString(block))
    return d


def test_flag_type():
    assert (
        PanoseFlag(_panose_dict(_PANOSE_BLOCK_ALL_ZEROS)).get_flag_type()
        == "Panose classification"
    )


def test_column_names_override():
    pf = PanoseFlag(_panose_dict(_PANOSE_BLOCK_ALL_ZEROS))
    assert pf.get_column_names() == [
        "Byte Position",
        "Name",
        "Byte Value",
        "Value",
    ]


def test_flag_value_uses_hex_string():
    # 12 zero bytes hex-encoded is "000000000000000000000000".
    pf = PanoseFlag(_panose_dict(_PANOSE_BLOCK_ALL_ZEROS))
    value = pf.get_flag_value()
    assert value.startswith("Panose byte :")
    hex_payload = value[len("Panose byte :") :]
    # 12 bytes -> 24 hex chars
    assert hex_payload.lower().replace("<", "").replace(">", "") == "00" * 12


def test_all_zero_rows_have_any_value():
    pf = PanoseFlag(_panose_dict(_PANOSE_BLOCK_ALL_ZEROS))
    rows = pf.get_flag_bits()
    # 10 byte positions starting at byte 2
    assert [r[0] for r in rows] == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for _, _, byte_value, description in rows:
        assert byte_value == 0
        assert description == "Any"


def test_known_lookup_values():
    pf = PanoseFlag(_panose_dict(_PANOSE_BLOCK_LATIN))
    rows = pf.get_flag_bits()
    by_name = {row[1]: (row[2], row[3]) for row in rows}
    assert by_name["Family Kind"] == (2, "Latin Text")
    assert by_name["Serif Style"] == (15, "Rounded")
    assert by_name["Weight"] == (5, "Book")
    assert by_name["Proportion"] == (3, "Modern")
    assert by_name["Contrast"] == (6, "Medium")
    assert by_name["Stroke Variation"] == (4, "Gradual/Transitional")
    assert by_name["Arm Style"] == (2, "Straight Arms/Horizontal")
    assert by_name["Letterform"] == (1, "No Fit")
    assert by_name["Midline"] == (13, "Low/Serifed")
    assert by_name["X-height"] == (7, "Ducking/Large")


def test_get_panose_bytes_static_helper():
    d = _panose_dict(_PANOSE_BLOCK_LATIN)
    assert PanoseFlag.get_panose_bytes(d) == _PANOSE_BLOCK_LATIN


def test_non_string_panose_raises():
    d = COSDictionary()
    d.set_item(_PANOSE, COSName.get_pdf_name("oops"))
    with pytest.raises(TypeError):
        PanoseFlag(d)
