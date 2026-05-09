from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont, read_charset, read_encoding


class _Strings:
    strings = [b"customGlyph", bytearray(b"arrayGlyph"), "strGlyph"]


class _FontSet:
    fontNames = ["Wave425Base"]  # noqa: N815
    strings = _Strings()


class _Private:
    defaultWidthX = 500
    nominalWidthX = 25
    Subrs = [object()]
    rawDict = {"defaultWidthX": 500}


class _Top:
    FontMatrix = [0.002, 0, 0, 0.002, 0, 0]
    GlobalSubrs = [object()]
    Private = _Private()
    rawDict = {"FontBBox": [0, -10, 200, 300]}
    charset = [".notdef", "customGlyph", "cid00042", "draws", "broken"]

    def __init__(self, charstrings: object) -> None:
        self.CharStrings = charstrings


class _CharStrings(dict[str, object]):
    def keys(self):  # type: ignore[no-untyped-def]
        return super().keys()


class _Drawable:
    def draw(self, pen: object) -> None:
        pen.moveTo((1, 2))
        pen.lineTo((3, 4))
        pen.curveTo((5, 6), (7, 8), (9, 10))
        pen.closePath()


class _BrokenDrawable:
    def draw(self, pen: object) -> None:
        del pen
        raise ValueError("cannot draw")


def _font() -> CFFFont:
    font = CFFFont()
    font._fontset = _FontSet()  # noqa: SLF001
    font._top = _Top(  # noqa: SLF001
        _CharStrings(
            {
                ".notdef": object(),
                "customGlyph": object(),
                "cid00042": object(),
                "draws": _Drawable(),
                "broken": _BrokenDrawable(),
            }
        )
    )
    return font


def test_wave425_private_string_index_resolves_bytes_bytearray_and_str() -> None:
    font = _font()

    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS) == "customGlyph"
    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS + 1) == "arrayGlyph"
    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS + 2) == "strGlyph"
    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS + 99) == ""
    assert font.get_sid("customGlyph") == CFFFont.NUM_STANDARD_STRINGS
    assert font.get_sid("arrayGlyph") == CFFFont.NUM_STANDARD_STRINGS + 1
    assert font.get_gid_for_sid(CFFFont.NUM_STANDARD_STRINGS) == 1


def test_wave425_standard_sid_boundaries_and_missing_string_table() -> None:
    assert CFFFont.is_standard_sid(0) is True
    assert CFFFont.is_standard_sid(CFFFont.NUM_STANDARD_STRINGS - 1) is True
    assert CFFFont.is_standard_sid(-1) is False
    assert CFFFont.is_standard_sid(CFFFont.NUM_STANDARD_STRINGS) is False

    font = CFFFont()
    font._fontset = object()  # noqa: SLF001
    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS) == ""


def test_wave425_cid_gid_helpers_parse_cid_names_and_reject_bad_inputs() -> None:
    font = _font()

    assert font.get_cid_for_gid(2) == 42
    assert font.get_cid_for_gid(1) == 1
    assert font.get_gid_for_cid(42) == 2
    assert font.get_gid_for_cid(-1) == 0
    assert font.get_gid_for_cid(99) == 0
    assert font.get_sid_for_gid(999) == 0


def test_wave425_get_path_records_commands_and_swallows_bad_charstrings() -> None:
    font = _font()

    assert font.get_path("draws") == [
        ("moveto", 1.0, 2.0),
        ("lineto", 3.0, 4.0),
        ("curveto", 5.0, 6.0, 7.0, 8.0, 9.0, 10.0),
        ("closepath",),
    ]
    assert font.get_path("broken") == []
    assert font.get_path("missing") == []


def test_wave425_get_width_returns_zero_when_extractor_rejects_stub_charstring() -> None:
    font = _font()

    assert font.get_width("customGlyph") == 0.0
    assert "customGlyph" not in font._widths  # noqa: SLF001
    assert font.get_width("missing") == 0.0


def test_wave425_copy_base_state_makes_independent_mutable_snapshots() -> None:
    base = _font()
    base._font_matrix = [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]  # noqa: SLF001
    base._units_per_em = 500  # noqa: SLF001
    base._widths = {"A": 123.0}  # noqa: SLF001
    base._data = b"cff"  # noqa: SLF001
    base.add_value_to_top_dict("Synthetic", 7)
    base.set_name("CopiedName")

    copied = CFFFont()
    copied._copy_base_state_from(base)  # noqa: SLF001

    base._font_matrix.append(1.0)  # noqa: SLF001
    base._widths["A"] = 999.0  # noqa: SLF001
    base.add_value_to_top_dict("Synthetic", 8)
    assert copied.get_font_matrix() == [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]
    assert copied.units_per_em == 500
    assert copied.get_glyph_widths()["A"] == 123.0
    assert copied.get_data() == b"cff"
    assert copied.get_property("Synthetic") == 7
    assert copied.get_name() == "CopiedName"


def test_wave425_repr_includes_summary_fields_without_dumping_charstrings() -> None:
    font = _font()
    font.set_name("Wave425")

    text = repr(font)

    assert text.startswith("CFFFont[name=Wave425,")
    assert "charset=['.notdef', 'customGlyph', 'cid00042', 'draws', 'broken']" in text
    assert "charStrings=5]" in text


def test_wave425_read_charset_edge_cases_and_errors() -> None:
    assert read_charset(io.BytesIO(b""), 0) == []
    assert read_charset(io.BytesIO(b"\x00\x22"), 2, fmt=0) == [0, 34]
    assert read_charset(io.BytesIO(b"\x00\x0a\x00\x02"), 3, fmt=2) == [0, 10, 11]

    with pytest.raises(ValueError, match="Unknown CFF charset format"):
        read_charset(io.BytesIO(b""), 2, fmt=99)
    with pytest.raises(EOFError, match="Card16"):
        read_charset(io.BytesIO(b"\x00"), 2, fmt=0)


def test_wave425_read_encoding_format1_supplement_and_errors() -> None:
    charset = [0, 34, 35, 36]
    encoding, supplement = read_encoding(
        io.BytesIO(bytes([1, 0x40, 2, 1, 0x41, 0x02, 0xBC])),
        charset,
        fmt_byte=0x81,
    )

    assert encoding[0x40] == 34
    assert encoding[0x41] == 700
    assert encoding[0x42] == 36
    assert supplement == [(0x41, 700)]
    with pytest.raises(ValueError, match="Unknown CFF encoding format"):
        read_encoding(io.BytesIO(b""), charset, fmt_byte=2)
