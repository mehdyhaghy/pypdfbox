from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSName, COSStream
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


class _SyntheticCIDCFF(CFFCIDFont):
    @property
    def units_per_em(self) -> int:
        return 1000

    def get_charset(self) -> list[str]:
        return [".notdef", "cid00007", "cid00009"]

    def has_glyph(self, name: str) -> bool:
        return name in self.get_charset()

    def get_width(self, name: str) -> float:
        return {".notdef": 0.0, "cid00007": 700.0, "cid00009": 900.0}[name]

    def get_type2_char_string(self, gid: int) -> tuple[str, int]:
        return ("gid", gid)


class _Glyph:
    def draw(self, pen: Any) -> None:
        pen.moveTo((10, 20))
        pen.lineTo((30, 40))
        pen.closePath()


class _TTInner:
    def __contains__(self, key: str) -> bool:
        return key == "glyf"

    def __getitem__(self, key: str) -> dict[str, Any]:
        if key != "glyf":
            raise KeyError(key)
        return {".notdef": type("_Box", (), {"yMin": -10, "yMax": 50})()}

    def getGlyphOrder(self) -> list[str]:  # noqa: N802
        return [".notdef"]

    def getGlyphName(self, gid: int) -> str:  # noqa: N802
        assert gid == 0
        return ".notdef"

    def getGlyphSet(self) -> dict[str, _Glyph]:  # noqa: N802
        return {".notdef": _Glyph()}


class _TTF:
    _tt = _TTInner()
    advance_widths = [500]

    def get_units_per_em(self) -> int:
        return 2000

    def get_advance_width(self, gid: int) -> int:
        assert gid == 0
        return 500


def _descriptor_with_file3(data: bytes, subtype: str = "CIDFontType0C") -> PDFontDescriptor:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(data)
    stream.set_name(COSName.SUBTYPE, subtype)  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    return descriptor


def test_type0_cid_keyed_program_maps_cids_through_charset() -> None:
    font = PDCIDFontType0()
    font.set_cff_font(_SyntheticCIDCFF())

    assert font.code_to_gid(7) == 1
    assert font.code_to_gid(9) == 2
    assert font.code_to_gid(8) == 0
    assert font.get_width_from_font(9) == 900.0
    assert font.get_type2_char_string(9) == ("gid", 2)
    assert font.get_type2_char_string(8) == ("gid", 0)


def test_type0_invalid_font_file3_is_cached_as_damaged() -> None:
    font = PDCIDFontType0()
    font.set_font_descriptor(_descriptor_with_file3(b"not a cff"))

    assert font.is_embedded() is True
    assert font.get_cff_font() is None
    assert font.get_cff_font() is None
    assert font.is_damaged() is True
    assert font._cff is False  # noqa: SLF001


def test_type2_cid_to_gid_map_ignores_trailing_odd_byte_and_reloads() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x00\x04\xff")
    font.set_cid_to_gid_map(stream)

    assert font.has_cid_to_gid_map() is True
    assert font.cid_to_gid(0) == 4
    assert font.cid_to_gid(1) == 0

    font.set_cid_to_gid_map("Identity")
    assert font.has_cid_to_gid_map() is False
    assert font.cid_to_gid(17) == 17


def test_type2_invalid_embedded_program_fallback_is_damaged() -> None:
    font = PDCIDFontType2()
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not a ttf")
    descriptor.set_font_file(stream)
    font.set_font_descriptor(descriptor)

    assert font.is_embedded() is True
    assert font.get_true_type_font() is None
    assert font.is_damaged() is True
    assert font._ttf is False  # noqa: SLF001


def test_type2_embedded_notdef_path_is_drawn_and_scaled() -> None:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _TTF()  # type: ignore[method-assign]
    font.set_font_descriptor(_descriptor_with_file3(b"ignored", "OpenType"))

    assert font.get_width_from_font(0) == 250.0
    assert font.get_normalized_path(0) == [
        ("moveto", 5.0, 10.0),
        ("lineto", 15.0, 20.0),
        ("closepath",),
    ]
