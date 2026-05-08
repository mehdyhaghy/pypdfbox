from __future__ import annotations

from pypdfbox.fontbox.cmap import CMapParser


def test_parse_accepts_memoryview_source() -> None:
    cmap = CMapParser().parse(
        memoryview(
            b"""
            1 begincodespacerange
            <00> <ff>
            endcodespacerange
            1 beginbfchar
            <41> <0041>
            endbfchar
            endcmap
            """
        )
    )

    assert cmap.to_unicode_bytes(b"A") == "A"


def test_malformed_utf16_target_uses_replacement_character() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <00> <ff>
        endcodespacerange
        1 beginbfchar
        <01> <D800>
        endbfchar
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x01") == "\ufffd"


def test_malformed_utf16_bfrange_target_does_not_abort_block() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <00> <ff>
        endcodespacerange
        2 beginbfrange
        <01> <01> <D800>
        <02> <02> <0042>
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x01") == "\ufffd"
    assert cmap.to_unicode_bytes(b"\x02") == "B"
