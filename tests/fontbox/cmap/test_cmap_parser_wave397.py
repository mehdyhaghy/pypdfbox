from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapParser


def test_wave397_parse_chunk_merges_into_existing_cmap() -> None:
    base = CMap("base")
    CMapParser.add_codespace_range(base, b"\x00", b"\xff")

    returned = CMapParser().parse_chunk(
        b"""
        1 beginbfchar
        <41> /Aname
        endbfchar
        endcmap
        """,
        base,
    )

    assert returned is base
    assert base.code_length_at(0x41) == 1
    assert base.to_unicode_bytes(b"A") == "Aname"


def test_wave397_parse_accepts_file_like_source_and_string_metadata() -> None:
    cmap = CMapParser().parse(
        BytesIO(
            b"""
            /Registry (Adobe) def
            /Ordering (Wave) def
            /Supplement 7 def
            /CMapVersion (1.002) def
            endcmap
            """
        )
    )

    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Wave"
    assert cmap.get_supplement() == 7
    assert cmap.get_version() == "1.002"


def test_wave397_odd_hex_digit_is_padded_as_high_nibble() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <F> <F>
        endcodespacerange
        1 beginbfchar
        <F> <0046>
        endbfchar
        endcmap
        """
    )

    assert cmap.code_length_at(0xF0) == 1
    assert cmap.to_unicode_bytes(b"\xf0") == "F"


def test_wave397_bfrange_operator_value_is_ignored_without_mapping() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <00> <ff>
        endcodespacerange
        1 beginbfrange
        <01> <02> null
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x01") is None
    assert cmap.to_unicode_bytes(b"\x02") is None


def test_wave397_unexpected_block_terminator_reports_range_name() -> None:
    with pytest.raises(OSError, match="~bfchar contains an unexpected operator"):
        CMapParser().parse(
            b"""
            1 beginbfchar
            endcidchar
            endcmap
            """
        )


def test_wave397_parse_unicode_cmap_rejects_missing_data() -> None:
    with pytest.raises(OSError, match="ToUnicode CMap data is missing"):
        CMapParser().parse_unicode_cmap(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "snippet, message",
    [
        (b">", "expected the end of a dictionary"),
        (
            b"1 beginbfchar <41> <00ZG> endbfchar endcmap",
            "expected hex character",
        ),
        (
            b"1 begincidchar <41> /not-an-int endcidchar endcmap",
            "invalid type for next token",
        ),
    ],
)
def test_wave397_tokenizer_and_typed_read_errors(
    snippet: bytes, message: str
) -> None:
    with pytest.raises(OSError, match=message):
        CMapParser().parse(snippet)
