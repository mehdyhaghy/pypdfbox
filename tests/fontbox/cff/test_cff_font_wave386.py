from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont, read_encoding


class _Private:
    defaultWidthX = 321
    nominalWidthX = -25


class _Top:
    FontMatrix = [0, 0, 0, 0, 0, 0]
    GlobalSubrs: list[object] = []
    Private = _Private()
    rawDict = {"FontBBox": [1, 2, 3, 4]}
    charset = [".notdef", "A", "B", "Missing"]

    def __init__(self, charstrings: object | None = None) -> None:
        self.CharStrings = charstrings if charstrings is not None else {}


class _FontSet:
    fontNames = ["StubFont"]  # noqa: N815


class _BytecodeEntry:
    bytecode = b"from-bytecode"


class _CompilesToBytecode:
    bytecode = None

    def compile(self) -> None:
        self.bytecode = b"compiled"


class _CompileFails:
    bytecode = None

    def compile(self) -> None:
        msg = "cannot compile"
        raise ValueError(msg)


def test_wave386_get_top_dict_tolerates_top_without_raw_dict() -> None:
    class _TopWithoutRawDict:
        pass

    font = CFFFont()
    font._top = _TopWithoutRawDict()  # noqa: SLF001
    font.add_value_to_top_dict("Synthetic", 42)

    assert font.get_top_dict() == {"Synthetic": 42}


def test_wave386_private_accessors_tolerate_missing_and_rawless_private_dicts() -> None:
    class _TopWithoutPrivate:
        pass

    class _TopWithRawlessPrivate:
        Private = object()

    font = CFFFont()
    font._top = _TopWithoutPrivate()  # noqa: SLF001
    assert font.get_private_dict() == {}
    assert font.get_default_width_x() == 0.0
    assert font.get_nominal_width_x() == 0.0

    font._top = _TopWithRawlessPrivate()  # noqa: SLF001
    assert font.get_private_dict() == {}


def test_wave386_global_subr_index_normalises_mixed_entries() -> None:
    font = CFFFont()
    top = _Top()
    top.GlobalSubrs = [_BytecodeEntry(), b"raw-bytes", bytearray(b"raw-array"), object()]
    font._top = top  # noqa: SLF001

    assert font.get_global_subr_index() == [
        b"from-bytecode",
        b"raw-bytes",
        b"raw-array",
        b"",
    ]


def test_wave386_char_string_bytes_handles_compile_success_failure_and_missing_names() -> None:
    font = CFFFont()
    font._top = _Top(  # noqa: SLF001
        {
            ".notdef": _BytecodeEntry(),
            "A": _CompilesToBytecode(),
            "B": _CompileFails(),
        }
    )

    assert font.get_char_string_bytes() == [
        b"from-bytecode",
        b"compiled",
        b"",
        b"",
    ]


def test_wave386_font_matrix_units_and_bbox_fallbacks_on_stub_top() -> None:
    font = CFFFont()
    font._top = _Top()  # noqa: SLF001

    assert font.get_font_matrix() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert font.units_per_em == 1000
    assert font.get_font_b_box() == [1.0, 2.0, 3.0, 4.0]

    font.add_value_to_top_dict("FontBBox", "bad")
    assert font.get_font_bbox() == [0.0, 0.0, 0.0, 0.0]


def test_wave386_name_property_falls_back_to_fontset_and_can_be_cleared() -> None:
    font = CFFFont()
    font._fontset = _FontSet()  # noqa: SLF001

    assert font.name == "StubFont"
    font.set_name("Override")
    assert font.name == "Override"
    font.set_name(None)
    assert font.get_name() == "StubFont"


def test_wave386_cid_and_property_detection_use_raw_dict_and_attributes() -> None:
    class _CIDTop:
        rawDict = {"ROS": ["Adobe", "Identity", 0]}  # noqa: N815, RUF012
        FullName = "RawDictCID"  # noqa: N815

    class _AttrTop:
        rawDict: dict[str, object] = {}  # noqa: RUF012
        FullName = "AttributeName"  # noqa: N815

    font = CFFFont()
    font._top = _CIDTop()  # noqa: SLF001
    assert font.is_cid_font() is True

    font._top = _AttrTop()  # noqa: SLF001
    assert font.get_property("FullName") == "AttributeName"


def test_wave386_get_type2_char_string_missing_mapping_returns_empty_wrapper() -> None:
    font = CFFFont()
    font._top = _Top({})  # noqa: SLF001
    font.set_name("Wave386")

    charstring = font.get_type2_char_string(1)

    assert charstring.get_name() == "A"
    assert charstring.get_gid() == 1
    assert charstring.get_font_name() == "Wave386"
    assert charstring.get_default_width_x() == 321.0
    assert charstring.get_nominal_width_x() == -25.0


def test_wave386_read_encoding_ignores_gids_missing_from_short_charset() -> None:
    data = bytes([0x01, 0x01, 0x40, 0x03])

    encoding, supplement = read_encoding(io.BytesIO(data), [0, 34])

    assert encoding[0x40] == 34
    assert encoding[0x41] == 0
    assert encoding[0x42] == 0
    assert encoding[0x43] == 0
    assert supplement == []


def test_wave386_from_bytes_rejects_empty_cff_fontset(monkeypatch: pytest.MonkeyPatch) -> None:
    class _EmptyFontSet:
        fontNames: list[str] = []  # noqa: N815

        def decompile(self, stream: object, otFont: object | None = None) -> None:  # noqa: N803
            del stream, otFont

    import fontTools.cffLib

    monkeypatch.setattr(fontTools.cffLib, "CFFFontSet", _EmptyFontSet)

    with pytest.raises(OSError, match="empty"):
        CFFFont.from_bytes(b"\x01\x00\x04\x04")
