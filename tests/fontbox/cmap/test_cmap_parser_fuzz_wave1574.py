"""Wave 1574 fuzz/parity tests for the PostScript CMap text parser.

Hammers ``CMapParser`` over the full PostScript Type0 CMap surface and
pins behaviour against Apache PDFBox / fontbox ``CMapParser`` 3.0.7:

* ``begincodespacerange`` — 1-byte / 2-byte / mixed-width ranges, and
  the min/max code-length determination that drives ``read_code``.
* ``begincidrange`` — code->CID with the dst CID incrementing across
  the range (offset arithmetic), single-value collapse, and the
  mismatched-byte-length error.
* ``begincidchar`` — single code->CID entries.
* ``beginbfchar`` — byte->unicode (hex dst, name dst, empty ``<>`` dst).
* ``beginbfrange`` — incremental dst (last-byte increment, including
  cross-byte-boundary carry) AND the array-destination form
  ``<lo> <hi> [<u1> <u2> ...]`` with one explicit dst per code.
* ``usecmap`` — inheritance, with a predefined CMap (Identity-H) and a
  custom in-memory base CMap folded in via ``parse_chunk``.
* ``/WMode`` 0 vs 1, ``/CMapName``, ``/Registry`` / ``/Ordering`` /
  ``/Supplement``.
* hex token parsing (whitespace inside ``< >``, odd nibble count,
  multi-byte split), and malformed entries (count mismatch, bad hex,
  reversed range).

These are pypdfbox-authored differential cases (not a 1:1 JUnit port);
the upstream JUnit port lives in
``tests/fontbox/cmap/upstream/test_cmap_parser.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapParser


def _parse(body: bytes) -> CMap:
    """Wrap a CMap body with the standard begincmap/endcmap envelope and
    parse it. The envelope is optional for the parser (it stops at
    ``endcmap`` or EOF) but keeps the fixtures readable."""
    src = b"begincmap\n" + body + b"\nendcmap\n"
    return CMapParser().parse(src)


# --------------------------------------------------------------------------
# codespacerange
# --------------------------------------------------------------------------


def test_codespacerange_one_byte_sets_lengths() -> None:
    cmap = _parse(b"1 begincodespacerange\n<00> <FF>\nendcodespacerange")
    assert cmap.get_min_code_length() == 1
    assert cmap.get_max_code_length() == 1


def test_codespacerange_two_byte_sets_lengths() -> None:
    cmap = _parse(b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange")
    assert cmap.get_min_code_length() == 2
    assert cmap.get_max_code_length() == 2


def test_codespacerange_mixed_widths_min_and_max() -> None:
    cmap = _parse(
        b"2 begincodespacerange\n<00> <80>\n<8140> <9FFC>\nendcodespacerange"
    )
    assert cmap.get_min_code_length() == 1
    assert cmap.get_max_code_length() == 2
    # Leading-byte dispatch: low byte resolves to 1-byte, high to 2-byte.
    assert cmap.code_length_at(0x10) == 1
    assert cmap.code_length_at(0x81) == 2


def test_codespacerange_registers_each_range() -> None:
    cmap = _parse(
        b"2 begincodespacerange\n<00> <80>\n<8140> <9FFC>\nendcodespacerange"
    )
    assert len(cmap.get_codespace_ranges()) == 2


def test_codespacerange_early_endoperator_stops() -> None:
    # Claims 3 entries, provides 1 then the end operator -> stop, no error.
    cmap = _parse(
        b"3 begincodespacerange\n<00> <FF>\nendcodespacerange"
    )
    assert cmap.get_max_code_length() == 1


# --------------------------------------------------------------------------
# cidrange / cidchar
# --------------------------------------------------------------------------


def test_cidrange_increments_dst_with_offset() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"1 begincidrange\n<0000> <00FF> 1\nendcidrange"
    )
    assert cmap.to_cid(0x0000) == 1
    assert cmap.to_cid(0x0001) == 2
    assert cmap.to_cid(0x00FF) == 256
    # Outside the range -> 0 (no-mapping sentinel).
    assert cmap.to_cid(0x0100) == 0


def test_cidrange_single_value_collapses() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"1 begincidrange\n<0041> <0041> 99\nendcidrange"
    )
    assert cmap.to_cid(0x0041) == 99
    assert cmap.to_cid(0x0042) == 0


def test_cidrange_mismatched_byte_lengths_raises() -> None:
    with pytest.raises(OSError, match="cidrange"):
        _parse(b"1 begincidrange\n<0041> <FF> 1\nendcidrange")


def test_cidchar_single_entries() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"2 begincidchar\n<0041> 10\n<0042> 20\nendcidchar"
    )
    assert cmap.to_cid(0x0041) == 10
    assert cmap.to_cid(0x0042) == 20


def test_cidchar_one_byte_code() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 begincidchar\n<41> 7\nendcidchar"
    )
    assert cmap.to_cid(0x41) == 7


def test_cidrange_early_end_operator_stops() -> None:
    # Declares 5 entries, gives 1 then endcidrange -> no error, 1 mapping.
    cmap = _parse(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"5 begincidrange\n<0010> <0010> 3\nendcidrange"
    )
    assert cmap.to_cid(0x0010) == 3


# --------------------------------------------------------------------------
# bfchar
# --------------------------------------------------------------------------


def test_bfchar_hex_destination() -> None:
    cmap = _parse(b"1 beginbfchar\n<41> <0041>\nendbfchar")
    assert cmap.to_unicode(0x41) == "A"


def test_bfchar_two_byte_input() -> None:
    cmap = _parse(b"1 beginbfchar\n<0041> <0041>\nendbfchar")
    assert cmap.to_unicode_with_length(0x0041, 2) == "A"


def test_bfchar_name_destination() -> None:
    cmap = _parse(b"1 beginbfchar\n<41> /euro\nendbfchar")
    assert cmap.to_unicode(0x41) == "euro"


def test_bfchar_empty_destination_yields_nul() -> None:
    # Upstream getMapping(new byte[0]) -> "".
    cmap = _parse(b"1 beginbfchar\n<01> <>\nendbfchar")
    assert cmap.to_unicode(0x01) == "\x00"


def test_bfchar_count_mismatch_stops_at_end_operator() -> None:
    cmap = _parse(b"3 beginbfchar\n<41> <0041>\nendbfchar")
    assert cmap.to_unicode(0x41) == "A"


def test_bfchar_bad_hex_raises() -> None:
    with pytest.raises(OSError, match="hex"):
        _parse(b"1 beginbfchar\n<4G> <0041>\nendbfchar")


# --------------------------------------------------------------------------
# bfrange — incremental destination
# --------------------------------------------------------------------------


def test_bfrange_incremental_destination() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<00> <02> <0041>\nendbfrange"
    )
    assert cmap.to_unicode(0x00) == "A"
    assert cmap.to_unicode(0x01) == "B"
    assert cmap.to_unicode(0x02) == "C"
    assert cmap.to_unicode(0x03) is None


def test_bfrange_incremental_crosses_low_byte_boundary() -> None:
    # dst starts at 0x00FF; the last byte rolls over with carry.
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<00> <02> <00FF>\nendbfrange"
    )
    assert ord(cmap.to_unicode(0x00)) == 0x00FF
    assert ord(cmap.to_unicode(0x01)) == 0x0100
    assert ord(cmap.to_unicode(0x02)) == 0x0101


def test_bfrange_reversed_range_is_skipped() -> None:
    # end < start -> PDFBOX-4550 bail-out, no mappings registered.
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<05> <02> <0041>\nendbfrange"
    )
    assert not cmap.has_unicode_mappings()


def test_bfrange_identity_full_range_pdfbox4720() -> None:
    # <0000> <FFFF> <0000> is treated as a 65k identity mapping.
    cmap = _parse(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"1 beginbfrange\n<0000> <FFFF> <0000>\nendbfrange"
    )
    assert ord(cmap.to_unicode_with_length(0x0041, 2)) == 0x0041
    assert ord(cmap.to_unicode_with_length(0x4142, 2)) == 0x4142


# --------------------------------------------------------------------------
# bfrange — array destination
# --------------------------------------------------------------------------


def test_bfrange_array_destination() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<00> <02> [<0041> <0042> <0043>]\nendbfrange"
    )
    assert cmap.to_unicode(0x00) == "A"
    assert cmap.to_unicode(0x01) == "B"
    assert cmap.to_unicode(0x02) == "C"
    assert cmap.to_unicode(0x03) is None


def test_bfrange_array_single_entry() -> None:
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<00> <00> [<0041>]\nendbfrange"
    )
    assert cmap.to_unicode(0x00) == "A"


def test_bfrange_array_surrogate_pair() -> None:
    # 4-byte UTF-16BE dst decodes to a single astral codepoint.
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<00> <00> [<D83DDE00>]\nendbfrange"
    )
    assert cmap.to_unicode(0x00) == "\U0001f600"


def test_bfrange_array_too_short_is_ignored() -> None:
    # array.size() < (end - start) guard: 1 entry for a 3-code range -> skip.
    cmap = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfrange\n<00> <05> [<0041>]\nendbfrange"
    )
    assert not cmap.has_unicode_mappings()


# --------------------------------------------------------------------------
# usecmap inheritance
# --------------------------------------------------------------------------


def test_usecmap_identity_h_provides_cid_ranges() -> None:
    src = (
        b"/Identity-H usecmap\nbegincmap\n"
        b"1 beginbfchar\n<41> <0041>\nendbfchar\nendcmap\n"
    )
    cmap = CMapParser().parse(src)
    # Identity CID range from the base CMap is inherited.
    assert cmap.to_cid(0x4142) == 0x4142
    # Own bfchar mapping is present.
    assert cmap.to_unicode(0x41) == "A"
    # Codespace inherited from Identity-H is 2-byte.
    assert cmap.get_max_code_length() == 2


def test_usecmap_merges_custom_base_via_parse_chunk() -> None:
    base = _parse(
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfchar\n<41> <0041>\nendbfchar"
    )
    parser = CMapParser()
    child_src = b"begincmap\n1 beginbfchar\n<42> <0042>\nendbfchar\nendcmap\n"
    merged = parser.parse_chunk(child_src, base)
    # Both the base and the child mappings are visible.
    assert merged.to_unicode(0x41) == "A"
    assert merged.to_unicode(0x42) == "B"


# --------------------------------------------------------------------------
# WMode / metadata literals
# --------------------------------------------------------------------------


@pytest.mark.parametrize("wmode", [0, 1])
def test_wmode_horizontal_and_vertical(wmode: int) -> None:
    body = (
        f"/WMode {wmode} def\n1 begincodespacerange\n<00> <FF>\n"
        "endcodespacerange"
    ).encode("utf-8")
    cmap = _parse(body)
    assert cmap.get_wmode() == wmode
    assert cmap.is_vertical() == (wmode == 1)
    assert cmap.is_horizontal() == (wmode == 0)


def test_cmap_name_literal() -> None:
    cmap = _parse(b"/CMapName /Adobe-Japan1-UCS2 def\nendcmap")
    assert cmap.get_name() == "Adobe-Japan1-UCS2"


def test_registry_ordering_supplement_literals() -> None:
    cmap = _parse(
        b"/Registry (Adobe) def\n/Ordering (Japan1) def\n/Supplement 6 def"
    )
    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Japan1"
    assert cmap.get_supplement() == 6
    assert cmap.get_combined_name() == "Adobe-Japan1-6"


def test_cid_system_info_dict_form() -> None:
    cmap = _parse(
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) "
        b"/Supplement 4 >> def"
    )
    info = cmap.get_cid_system_info()
    assert info == {"Registry": "Adobe", "Ordering": "GB1", "Supplement": 4}


# --------------------------------------------------------------------------
# hex token parsing
# --------------------------------------------------------------------------


def test_hex_token_whitespace_inside_brackets() -> None:
    # Whitespace between nibbles is skipped; <00 41> == <0041>.
    cmap = _parse(b"1 beginbfchar\n<41> <00 41>\nendbfchar")
    assert cmap.to_unicode(0x41) == "A"


def test_hex_token_odd_nibble_count_keeps_high_nibble() -> None:
    # <415> -> bytes 0x41 0x50 (last lone nibble shifted into high nibble).
    cmap = _parse(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"1 begincidchar\n<415> 1\nendcidchar"
    )
    # Stored under the 2-byte key 0x4150.
    assert cmap.to_cid_with_length(0x4150, 2) == 1


def test_hex_token_two_byte_split_is_big_endian() -> None:
    cmap = _parse(b"1 beginbfchar\n<4142> <0041>\nendbfchar")
    # Input code 0x4142 (big-endian) maps to "A".
    assert cmap.to_unicode_with_length(0x4142, 2) == "A"


def test_max_codespace_byte_length_from_longest_range() -> None:
    cmap = _parse(
        b"3 begincodespacerange\n<00> <80>\n<8140> <9FFC>\n"
        b"<818140> <9F9FFC>\nendcodespacerange"
    )
    assert cmap.get_min_code_length() == 1
    assert cmap.get_max_code_length() == 3
