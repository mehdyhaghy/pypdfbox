from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapParser, CodespaceRange
from pypdfbox.io import RandomAccessReadBuffer


def test_parser_handles_comments_tabs_and_basic_mappings() -> None:
    cmap = CMapParser().parse(
        b"""
        /CMapName /Test def
        /WMode 1 def
        1 % comment between count and operator
        begincodespacerange
        <00>\t<ff>
        endcodespacerange
        1 beginbfchar
        <41> <0041>
        endbfchar
        1 begincidchar
        <41> 65
        endcidchar
        endcmap
        """
    )

    assert cmap.get_name() == "Test"
    assert cmap.get_wmode() == 1
    assert cmap.to_unicode_bytes(b"A") == "A"
    assert cmap.to_cid_bytes(b"A") == 65


def test_parser_ignores_comments_inside_mapping_blocks() -> None:
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        % comment before codespace row
        <00> <ff>
        endcodespacerange
        1 beginbfchar
        % comment before bfchar row
        <20> <0020>
        endbfchar
        1 beginbfrange
        % comment before bfrange row
        <42> <43> [
          <0042>
          % comment between array targets
          <0043>
        ]
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b" ") == " "
    assert cmap.to_unicode_bytes(b"B") == "B"
    assert cmap.to_unicode_bytes(b"C") == "C"


def test_parser_array_bfrange_tolerates_off_by_one() -> None:
    # Upstream guard is `array.size() >= end - start` (not +1) — see
    # CMapParser.java parseBeginbfrange. A 2-entry array against a 3-code
    # range therefore maps the first two codes and silently leaves the
    # last unmapped, rather than dropping the whole range.
    cmap = CMapParser().parse(
        b"""
        1 begincodespacerange
        <01> <03>
        endcodespacerange
        1 beginbfrange
        <01> <03> [<0041> <0042>]
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x01") == "A"
    assert cmap.to_unicode_bytes(b"\x02") == "B"
    assert cmap.to_unicode_bytes(b"\x03") is None


def test_identity_predefined_maps_two_byte_codes_to_cids() -> None:
    cmap = CMapParser.parse_predefined("Identity-H")
    assert cmap.read_cid(__import__("io").BytesIO(b"\x12\x34")) == 0x1234


def test_bundled_predefined_loads_from_disk() -> None:
    # Adobe-Japan1-UCS2 ships in pypdfbox/fontbox/cmap/resources/.
    cmap = CMapParser.parse_predefined("Adobe-Japan1-UCS2")
    assert cmap.get_name() == "Adobe-Japan1-UCS2"
    assert cmap.has_unicode_mappings()


def test_unknown_predefined_raises() -> None:
    with pytest.raises(OSError):
        CMapParser.parse_predefined("NotARealPredefinedCMap-XYZ")


# ---------- direct parity tests for the newly-public surface ----------


def _ras(data: bytes) -> RandomAccessReadBuffer:
    return RandomAccessReadBuffer(data)


def test_is_whitespace_or_eof_matches_upstream_spec() -> None:
    # Java upstream: -1 (EOF), 0x20 (space), 0x0D (CR), 0x0A (LF).
    for b in (-1, 0x20, 0x0D, 0x0A):
        assert CMapParser.is_whitespace_or_eof(b) is True
    for b in (0x09, 0x21, 0x30, 0x41):
        assert CMapParser.is_whitespace_or_eof(b) is False


def test_is_delimiter_matches_upstream_spec() -> None:
    for b in (0x28, 0x29, 0x3C, 0x3E, 0x5B, 0x5D, 0x7B, 0x7D, 0x2F, 0x25):
        assert CMapParser.is_delimiter(b) is True
    for b in (0x20, 0x09, 0x41, 0x30, 0x00):
        assert CMapParser.is_delimiter(b) is False


def test_increment_low_byte_carries_in_lenient_mode() -> None:
    data = bytearray(b"\x01\xFF")
    assert CMapParser.increment(data, 1, False) is True
    assert bytes(data) == b"\x02\x00"


def test_increment_low_byte_overflows_in_strict_mode() -> None:
    data = bytearray(b"\x01\xFF")
    assert CMapParser.increment(data, 1, True) is False
    # Buffer left untouched on overflow refusal.
    assert bytes(data) == b"\x01\xFF"


def test_increment_at_negative_position_returns_false() -> None:
    data = bytearray(b"\x10")
    assert CMapParser.increment(data, -1, False) is False
    assert bytes(data) == b"\x10"


def test_create_string_from_bytes_one_byte_through_latin1() -> None:
    assert CMapParser.create_string_from_bytes(b"\x41") == "A"
    assert CMapParser.create_string_from_bytes(b"\xFF") == "ÿ"


def test_create_string_from_bytes_multibyte_utf16be() -> None:
    assert CMapParser.create_string_from_bytes(b"\x00\x41") == "A"
    assert CMapParser.create_string_from_bytes(b"\x00\x41\x00\x42") == "AB"


def test_parse_next_token_returns_integer_for_digits() -> None:
    parser = CMapParser()
    ras = _ras(b"42 ")
    assert parser.parse_next_token(ras) == 42


def test_parse_next_token_returns_float_for_decimal() -> None:
    parser = CMapParser()
    ras = _ras(b"3.14 ")
    assert parser.parse_next_token(ras) == 3.14


def test_parse_next_token_returns_bytes_for_hex() -> None:
    parser = CMapParser()
    assert parser.parse_next_token(_ras(b"<41 42>")) == b"AB"


def test_parse_integer_rejects_non_int_token() -> None:
    parser = CMapParser()
    with pytest.raises(OSError):
        parser.parse_integer(_ras(b"<41>"))


def test_parse_byte_array_rejects_non_bytes_token() -> None:
    parser = CMapParser()
    with pytest.raises(OSError):
        parser.parse_byte_array(_ras(b"42"))


def test_read_string_collects_until_closing_paren() -> None:
    # Caller has already consumed '(' before invoking read_string.
    ras = _ras(b"hello)")
    assert CMapParser.read_string(ras) == "hello"


def test_read_array_returns_inner_tokens() -> None:
    parser = CMapParser()
    # Caller has already consumed '['.
    out = parser.read_array(_ras(b"<41> <42> ]"))
    assert out == [b"A", b"B"]


def test_check_expected_operator_passes_on_match() -> None:
    # Indirect: build an Operator via a synthetic snippet then dispatch
    # through parse_begincodespacerange — failure path raises OSError.
    parser = CMapParser()
    parser.parse(b"1 begincodespacerange <00> <FF> endcodespacerange endcmap")


def test_check_expected_operator_rejects_wrong_terminator() -> None:
    # ``count`` over-states the body length, so the parser hits the
    # closing operator before exhausting the loop. A non-matching
    # terminator must raise an OSError per upstream's
    # ``checkExpectedOperator``.
    with pytest.raises(OSError):
        CMapParser().parse(
            b"2 begincodespacerange <00> <FF> endbfchar endcmap"
        )


def test_add_mapping_frombfrange_count_form_increments_dst() -> None:
    parser = CMapParser()
    cmap = CMap()
    cmap.add_codespace_range(CodespaceRange(b"\x00", b"\xFF"))
    start = bytearray(b"\x01")
    dst = bytearray(b"\x00\x41")  # "A"
    parser.add_mapping_frombfrange(cmap, start, 3, dst)
    assert cmap.to_unicode_bytes(b"\x01") == "A"
    assert cmap.to_unicode_bytes(b"\x02") == "B"
    assert cmap.to_unicode_bytes(b"\x03") == "C"


def test_add_mapping_frombfrange_list_form_takes_explicit_targets() -> None:
    parser = CMapParser()
    cmap = CMap()
    cmap.add_codespace_range(CodespaceRange(b"\x00", b"\xFF"))
    start = bytearray(b"\x10")
    parser.add_mapping_frombfrange(cmap, start, [b"\x00\x41", b"\x00\x42"])
    assert cmap.to_unicode_bytes(b"\x10") == "A"
    assert cmap.to_unicode_bytes(b"\x11") == "B"


def test_get_external_c_map_raises_for_unknown_resource() -> None:
    parser = CMapParser()
    with pytest.raises(OSError, match="Could not find referenced cmap stream"):
        parser.get_external_c_map("DefinitelyNotBundled")
