from __future__ import annotations

from pypdfbox.fontbox.cmap import CMapParser


def test_wave327_parser_treats_pdf_whitespace_as_token_separators() -> None:
    cmap = CMapParser().parse(
        b"1\x00begincodespacerange\x0c<00>\x00<ff>\x0cendcodespacerange"
        b"\x001\x0cbeginbfchar\x00<41>\x0c<0041>\x00endbfchar\x0cendcmap"
    )

    assert cmap.code_length_at(0x41) == 1
    assert cmap.to_unicode_bytes(b"A") == "A"


def test_wave327_parser_treats_pdf_whitespace_inside_hex_strings() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <00> <ff>
        endcodespacerange
        1 beginbfchar
        <4\x001> <00\x0c41>
        endbfchar
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"A") == "A"
