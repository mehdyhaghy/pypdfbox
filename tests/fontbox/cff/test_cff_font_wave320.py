from __future__ import annotations

from pypdfbox.fontbox.cff.cff_font import CFFFont


class _FakeStrings:
    def __init__(self, strings: list[object]) -> None:
        self.strings = strings


class _FakeFontSet:
    def __init__(self, strings: list[object]) -> None:
        self.strings = _FakeStrings(strings)


def test_wave320_get_string_decodes_private_string_index_bytes() -> None:
    font = CFFFont()
    font._fontset = _FakeFontSet([b"CustomGlyph", "PlainGlyph"])  # noqa: SLF001

    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS) == "CustomGlyph"
    assert font.get_string(CFFFont.NUM_STANDARD_STRINGS + 1) == "PlainGlyph"


def test_wave320_get_sid_matches_private_string_index_bytes() -> None:
    font = CFFFont()
    font._fontset = _FakeFontSet([b"CustomGlyph"])  # noqa: SLF001

    assert font.get_sid("CustomGlyph") == CFFFont.NUM_STANDARD_STRINGS
