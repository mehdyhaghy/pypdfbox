from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.fontbox.cmap import CMapParser
from pypdfbox.io import RandomAccessReadBuffer


def test_wave432_parse_skips_string_token_that_looks_like_comment() -> None:
    cmap = CMapParser().parse(
        b"""
        (%not-a-real-comment-token)
        /CMapName /AfterString def
        endcmap
        """
    )

    assert cmap.get_name() == "AfterString"


def test_wave432_parse_accepts_random_access_read_source() -> None:
    source = RandomAccessReadBuffer(
        b"""
        /CMapName /FromRandomAccess def
        1 beginbfchar
        <41> <0041>
        endbfchar
        endcmap
        """
    )

    cmap = CMapParser().parse(source)

    assert cmap.get_name() == "FromRandomAccess"
    assert cmap.to_unicode_bytes(b"A") == "A"


@pytest.mark.parametrize(
    "snippet, message",
    [
        (b"1 begincodespacerange endcodespacerange endcmap", None),
        (b"1 begincodespacerange /not-bytes <ff> endcodespacerange", "start range missing"),
        (
            b"1 begincodespacerange <01> <0002> endcodespacerange",
            "different lengths",
        ),
        (b"1 beginbfchar endbfchar endcmap", None),
        (b"1 beginbfchar /not-bytes <0041> endbfchar", "input code missing"),
        (
            b"1 beginbfchar <41> 99 endbfchar",
            "expected\\{COSString or COSName\\}",
        ),
        (b"1 begincidrange endcidrange endcmap", None),
        (b"1 begincidrange /not-bytes <02> 7 endcidrange", "start code missing"),
        (b"1 begincidchar endcidchar endcmap", None),
        (b"1 begincidchar /not-bytes 7 endcidchar", "input code missing"),
        (b"1 beginnotdefchar endnotdefchar endcmap", None),
        (b"1 beginnotdefchar /not-bytes 7 endnotdefchar", "input code missing"),
        (b"1 beginnotdefrange endnotdefrange endcmap", None),
        (b"1 beginnotdefrange /not-bytes <02> 7 endnotdefrange", "start code missing"),
        (b"1 beginbfrange endbfrange endcmap", None),
        (b"1 beginbfrange /not-bytes <02> <0041> endbfrange", "start code missing"),
        (b"1 beginbfrange <02> endbfrange endcmap", None),
        (b"1 beginbfrange <01> /not-bytes <0041> endbfrange", "end code missing"),
    ],
)
def test_wave432_mapping_blocks_handle_early_end_and_bad_token_types(
    snippet: bytes,
    message: str | None,
) -> None:
    if message is None:
        CMapParser().parse(snippet)
    else:
        with pytest.raises(OSError, match=message):
            CMapParser().parse(snippet)


def test_wave432_typed_readers_report_missing_values() -> None:
    with pytest.raises(OSError, match="expected integer value is missing"):
        CMapParser().parse(b"1 begincidchar <41>")

    with pytest.raises(OSError, match="expected byte\\[\\] value is missing"):
        CMapParser().parse(b"1 begincodespacerange <00>")


def test_wave432_parser_reads_arrays_until_eof() -> None:
    cmap = CMapParser().parse(
        b"""
        1 beginbfrange
        <01> <02> [<0041> <0042>
        """
    )

    assert cmap.to_unicode_bytes(b"\x01") == "A"
    assert cmap.to_unicode_bytes(b"\x02") == "B"


def test_wave432_string_and_literal_name_keep_latin1_and_delimiter_boundaries() -> None:
    cmap = CMapParser().parse(
        b"""
        /Registry (Ad\xffbe) def
        /CMapName/NameWithoutWhitespace def
        endcmap
        """
    )

    assert cmap.get_registry() == "Adÿbe"
    assert cmap.get_name() == "NameWithoutWhitespace"


def test_wave432_operator_without_whitespace_rewinds_before_count() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <00> <ff>
        endcodespacerange1 beginbfchar
        <41> <0041>
        endbfchar
        endcmap
        """
    )

    assert cmap.code_length_at(0x41) == 1
    assert cmap.to_unicode_bytes(b"A") == "A"


def test_wave432_invalid_dotted_number_raises_oserror() -> None:
    with pytest.raises(OSError, match="Invalid number '1.2.3'"):
        CMapParser().parse(b"1.2.3 beginbfchar endbfchar")


def test_wave432_hex_strings_accept_lowercase_and_whitespace() -> None:
    cmap = CMapParser().parse(
        b"""
        1 beginbfchar
        <4 1> <00 61>
        endbfchar
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"A") == "a"


def test_wave432_strict_bfrange_stops_when_target_overflows() -> None:
    cmap = CMapParser(strict_mode=True).parse(
        b"""
        1 beginbfrange
        <01> <03> <00ff>
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x01") == "ÿ"
    assert cmap.to_unicode_bytes(b"\x02") is None
    assert cmap.to_unicode_bytes(b"\x03") is None


def test_wave432_identity_bfrange_special_case_builds_full_mapping() -> None:
    cmap = CMapParser().parse(
        b"""
        1 beginbfrange
        <0000> <FFFF> <0000>
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x00\x00") == "\x00"
    assert cmap.to_unicode_bytes(b"\x00A") == "A"
    assert cmap.to_unicode_bytes(b"\xff\xff") == "\uffff"


def test_wave432_coerce_rejects_unsupported_source_type() -> None:
    with pytest.raises(TypeError, match="unsupported source type: object"):
        CMapParser().parse(object())


def test_wave432_parse_accepts_memoryview_and_file_like_sources() -> None:
    payload = b"1 beginbfchar <41> <0041> endbfchar endcmap"

    assert CMapParser().parse(memoryview(payload)).to_unicode_bytes(b"A") == "A"
    assert CMapParser().parse(BytesIO(payload)).to_unicode_bytes(b"A") == "A"
