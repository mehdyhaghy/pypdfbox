"""Round-out coverage for ``CMapParser``.

Each test feeds a synthetic, minimal CMap snippet exercising one
directive so regressions in tokenizer / dispatch logic surface against
a single operator, not the whole pipeline.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapParser


def _parse(snippet: bytes) -> CMap:
    return CMapParser().parse(snippet)


# ---------- usecmap ----------


def test_usecmap_cascades_codespaces_and_unicode_from_referenced_cmap() -> None:
    # /Identity-H is built programmatically, so this exercises the
    # usecmap directive without depending on the bundled resource set.
    cmap = _parse(
        b"""
        /Identity-H usecmap
        1 beginbfchar
        <0041> <0061>
        endbfchar
        endcmap
        """
    )
    # Codespace and CID range inherited from Identity-H.
    assert cmap.to_cid_bytes(b"\x12\x34") == 0x1234
    # Local bfchar still wins.
    assert cmap.to_unicode_bytes(b"\x00\x41") == "a"


# ---------- begincodespacerange ----------


def test_codespacerange_multibyte() -> None:
    cmap = _parse(
        b"""
        2 begincodespacerange
        <00> <7F>
        <8140> <9FFC>
        endcodespacerange
        endcmap
        """
    )
    # Both codespaces are visible — leading-byte heuristic agrees.
    assert cmap.code_length_at(0x40) == 1
    assert cmap.code_length_at(0x81) == 2
    assert cmap.code_length_at(0x9F) == 2


# ---------- beginbfchar ----------


def test_bfchar_one_to_one_unicode() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        3 beginbfchar
        <41> <0041>
        <42> <0042>
        <43> <0043>
        endbfchar
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x41") == "A"
    assert cmap.to_unicode_bytes(b"\x42") == "B"
    assert cmap.to_unicode_bytes(b"\x43") == "C"


# ---------- beginbfrange ----------


def test_bfrange_count_form_increments_dst() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <41> <43> <0041>
        endbfrange
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x41") == "A"
    assert cmap.to_unicode_bytes(b"\x42") == "B"
    assert cmap.to_unicode_bytes(b"\x43") == "C"


def test_bfrange_array_form_takes_explicit_targets() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <01> <03> [<0041> <0058> <00FF>]
        endbfrange
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x01") == "A"
    assert cmap.to_unicode_bytes(b"\x02") == "X"
    assert cmap.to_unicode_bytes(b"\x03") == "ÿ"


def test_bfrange_corrupt_end_lt_start_aborts_block() -> None:
    # PDFBOX-4550: end < start → bail without crashing.
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <44> <42> <0041>
        endbfrange
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x42") is None
    assert cmap.to_unicode_bytes(b"\x44") is None


# ---------- begincidchar ----------


def test_cidchar_single_mapping() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        2 begincidchar
        <41> 100
        <42> 101
        endcidchar
        endcmap
        """
    )
    assert cmap.to_cid_bytes(b"\x41") == 100
    assert cmap.to_cid_bytes(b"\x42") == 101


# ---------- begincidrange ----------


def test_cidrange_range_form() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <0000> <FFFF> endcodespacerange
        1 begincidrange
        <0001> <0003> 100
        endcidrange
        endcmap
        """
    )
    assert cmap.to_cid_bytes(b"\x00\x01") == 100
    assert cmap.to_cid_bytes(b"\x00\x02") == 101
    assert cmap.to_cid_bytes(b"\x00\x03") == 102


def test_cidrange_collapses_single_value_into_mapping() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <0000> <FFFF> endcodespacerange
        1 begincidrange
        <0042> <0042> 200
        endcidrange
        endcmap
        """
    )
    assert cmap.to_cid_bytes(b"\x00\x42") == 200


def test_cidrange_mismatched_byte_lengths_raises() -> None:
    with pytest.raises(OSError):
        _parse(
            b"""
            1 begincodespacerange <0000> <FFFF> endcodespacerange
            1 begincidrange
            <01> <0003> 100
            endcidrange
            endcmap
            """
        )


# ---------- beginnotdefchar ----------


def test_notdefchar_registers_substitute_cid() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        2 beginnotdefchar
        <01> 999
        <02> 888
        endnotdefchar
        endcmap
        """
    )
    assert cmap.to_cid_bytes(b"\x01") == 999
    assert cmap.to_cid_bytes(b"\x02") == 888


# ---------- beginnotdefrange ----------


def test_notdefrange_registers_substitute_cid_for_range() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <0000> <FFFF> endcodespacerange
        1 beginnotdefrange
        <0001> <0003> 999
        endnotdefrange
        endcmap
        """
    )
    # All three codes resolve to the same .notdef substitute CID.
    assert cmap.to_cid_bytes(b"\x00\x01") == 999
    assert cmap.to_cid_bytes(b"\x00\x02") == 999
    assert cmap.to_cid_bytes(b"\x00\x03") == 999


def test_notdefrange_collapses_single_value_into_mapping() -> None:
    cmap = _parse(
        b"""
        1 begincodespacerange <0000> <FFFF> endcodespacerange
        1 beginnotdefrange
        <0099> <0099> 777
        endnotdefrange
        endcmap
        """
    )
    assert cmap.to_cid_bytes(b"\x00\x99") == 777


def test_notdefrange_mismatched_byte_lengths_raises() -> None:
    with pytest.raises(OSError):
        _parse(
            b"""
            1 begincodespacerange <0000> <FFFF> endcodespacerange
            1 beginnotdefrange
            <01> <0003> 999
            endnotdefrange
            endcmap
            """
        )


# ---------- WMode ----------


def test_wmode_horizontal_default_zero() -> None:
    cmap = _parse(b"endcmap")
    assert cmap.get_wmode() == 0


def test_wmode_zero_explicit() -> None:
    cmap = _parse(b"/WMode 0 def endcmap")
    assert cmap.get_wmode() == 0


def test_wmode_one_vertical() -> None:
    cmap = _parse(b"/WMode 1 def endcmap")
    assert cmap.get_wmode() == 1


# ---------- CMapName / Registry / Ordering / Supplement ----------


def test_cmap_name_directive() -> None:
    cmap = _parse(b"/CMapName /Adobe-Identity-UCS def endcmap")
    assert cmap.get_name() == "Adobe-Identity-UCS"


def test_registry_ordering_supplement_directives() -> None:
    cmap = _parse(
        b"""
        /CIDSystemInfo
        << /Registry (Adobe) /Ordering (UCS) /Supplement 3 >> def
        /CMapName /Test def
        endcmap
        """
    )
    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "UCS"
    assert cmap.get_supplement() == 3
    assert cmap.get_name() == "Test"


def test_cmap_type_and_version_directives() -> None:
    cmap = _parse(
        b"""
        /CMapType 1 def
        /CMapVersion 2 def
        endcmap
        """
    )
    assert cmap.get_type() == 1
    assert cmap.get_version() == "2"
