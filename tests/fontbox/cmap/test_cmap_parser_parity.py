from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapParser


# ---------- parse_predefined ----------


def test_parse_predefined_identity_h_returns_horizontal_cmap() -> None:
    cmap = CMapParser.parse_predefined("Identity-H")
    assert isinstance(cmap, CMap)
    assert cmap.get_name() == "Identity-H"
    assert cmap.get_wmode() == 0
    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Identity"


def test_parse_predefined_identity_v_returns_vertical_cmap() -> None:
    cmap = CMapParser.parse_predefined("Identity-V")
    assert isinstance(cmap, CMap)
    assert cmap.get_name() == "Identity-V"
    assert cmap.get_wmode() == 1


def test_parse_predefined_unknown_raises() -> None:
    with pytest.raises(OSError):
        # Adobe-CNS1-H is not in the bundled subset (the upstream resource
        # is the 1-byte→CID horizontal CMap; pypdfbox only ships the UCS2
        # and a curated set of encoding CMaps).
        CMapParser.parse_predefined("Adobe-CNS1-H")


# ---------- get_cmap_for_name ----------


def test_get_cmap_for_name_returns_identity_h() -> None:
    cmap = CMapParser.get_cmap_for_name("Identity-H")
    assert cmap is not None
    assert cmap.get_name() == "Identity-H"


def test_get_cmap_for_name_caches_instance() -> None:
    first = CMapParser.get_cmap_for_name("Identity-H")
    second = CMapParser.get_cmap_for_name("Identity-H")
    assert first is second


def test_get_cmap_for_name_returns_none_for_unknown() -> None:
    assert CMapParser.get_cmap_for_name("not-a-real-cmap") is None


# ---------- parse_unicode_cmap ----------


_TO_UNICODE_CMAP = b"""
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo
<< /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
2 beginbfchar
<41> <0041>
<42> <0042>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""


def test_parse_unicode_cmap_returns_mappings() -> None:
    cmap = CMapParser().parse_unicode_cmap(_TO_UNICODE_CMAP)
    assert cmap.has_unicode_mappings()
    assert cmap.to_unicode_bytes(b"\x41") == "A"
    assert cmap.to_unicode_bytes(b"\x42") == "B"


def test_parse_unicode_cmap_accepts_bytearray() -> None:
    cmap = CMapParser().parse_unicode_cmap(bytearray(_TO_UNICODE_CMAP))
    assert cmap.to_unicode_bytes(b"\x41") == "A"


# ---------- add_codespace_range ----------


def test_add_codespace_range_registers_range_on_cmap() -> None:
    cmap = CMap("Synthetic")
    CMapParser.add_codespace_range(cmap, b"\x00", b"\xff")
    # Range registration enables read_code on a 1-byte stream.
    import io

    assert cmap.read_code(io.BytesIO(b"\x05")) == 0x05


# ---------- parse_chunk ----------


def test_parse_chunk_returns_fresh_cmap_when_target_missing() -> None:
    parser = CMapParser()
    cmap = parser.parse_chunk(_TO_UNICODE_CMAP)
    assert cmap.to_unicode_bytes(b"\x41") == "A"


def test_parse_chunk_merges_into_existing_cmap() -> None:
    parser = CMapParser()
    base = CMapParser.parse_predefined("Identity-H")
    returned = parser.parse_chunk(_TO_UNICODE_CMAP, base)
    assert returned is base
    # The merged-in bfchar mapping is now visible on the base CMap.
    assert base.to_unicode_bytes(b"\x41") == "A"
