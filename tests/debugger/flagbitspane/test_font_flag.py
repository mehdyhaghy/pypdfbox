"""Tests for :class:`FontFlag`."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.debugger.flagbitspane.font_flag import FontFlag

_FLAGS = COSName.get_pdf_name("Flags")


def _font_desc_dict(flags: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_FLAGS, COSInteger.get(flags))
    return d


def test_flag_type():
    assert FontFlag(_font_desc_dict(0)).get_flag_type() == "Font flag"


def test_flag_value_no_space_before_colon():
    # Upstream uses "Flag value:" with no space — verify the verbatim port.
    assert FontFlag(_font_desc_dict(34)).get_flag_value() == "Flag value:34"


def test_table_shape():
    rows = FontFlag(_font_desc_dict(0)).get_flag_bits()
    assert [r[0] for r in rows] == [1, 2, 3, 4, 6, 7, 17, 18, 19]
    assert [r[1] for r in rows] == [
        "FixedPitch",
        "Serif",
        "Symbolic",
        "Script",
        "NonSymbolic",
        "Italic",
        "AllCap",
        "SmallCap",
        "ForceBold",
    ]


def test_only_serif_set():
    # bit 2 == Serif
    rows = FontFlag(_font_desc_dict(1 << 1)).get_flag_bits()
    flags = {r[1]: r[2] for r in rows}
    assert flags["Serif"] is True
    assert flags["FixedPitch"] is False
    assert flags["Symbolic"] is False


def test_symbolic_and_italic_set():
    # Bit 3 (Symbolic), bit 7 (Italic)
    rows = FontFlag(_font_desc_dict((1 << 2) | (1 << 6))).get_flag_bits()
    flags = {r[1]: r[2] for r in rows}
    assert flags["Symbolic"] is True
    assert flags["Italic"] is True
    assert flags["FixedPitch"] is False
