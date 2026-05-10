from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMapParser


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
