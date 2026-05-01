"""Tests for ``pypdfbox.fontbox.cmap.cmap_manager.CMapManager``.

Predefined CMap loader/cache parity with upstream
``org.apache.pdfbox.pdmodel.font.CMapManager``.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapManager


@pytest.fixture(autouse=True)
def _clear_predefined_cache():
    """Drop the process-wide cache before/after each test so parity
    assertions are not contaminated by neighbouring tests."""
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


# ---------------------------------------------------------------------- #
# Identity-H — programmatic / round-trip                                 #
# ---------------------------------------------------------------------- #


class TestIdentityH:
    def test_loads_by_name(self):
        cmap = CMapManager.get_predefined_cmap("Identity-H")
        assert cmap is not None
        assert isinstance(cmap, CMap)
        assert cmap.get_name() == "Identity-H"

    def test_metadata(self):
        cmap = CMapManager.get_predefined_cmap("Identity-H")
        assert cmap is not None
        assert cmap.get_registry() == "Adobe"
        assert cmap.get_ordering() == "Identity"
        assert cmap.get_supplement() == 0
        assert cmap.get_wmode() == 0

    def test_round_trips_two_byte_codes(self):
        cmap = CMapManager.get_predefined_cmap("Identity-H")
        assert cmap is not None
        # Identity mapping over the full 16-bit range.
        for code in (0x0000, 0x0042, 0x00FF, 0x1234, 0xABCD, 0xFFFF):
            assert cmap.to_cid(code) == code

    def test_read_code_from_stream(self):
        cmap = CMapManager.get_predefined_cmap("Identity-H")
        assert cmap is not None
        # Two-byte code 0x1234 followed by 0xABCD.
        stream = BytesIO(bytes([0x12, 0x34, 0xAB, 0xCD]))
        first = cmap.read_code(stream)
        second = cmap.read_code(stream)
        assert first == 0x1234
        assert second == 0xABCD

    def test_read_code_bytes_form(self):
        cmap = CMapManager.get_predefined_cmap("Identity-H")
        assert cmap is not None
        data = bytes([0x12, 0x34, 0xAB, 0xCD])
        code, length = cmap.read_code(data, 0)
        assert code == 0x1234
        assert length == 2
        code, length = cmap.read_code(data, 2)
        assert code == 0xABCD
        assert length == 2


# ---------------------------------------------------------------------- #
# Identity-V — vertical writing mode                                     #
# ---------------------------------------------------------------------- #


class TestIdentityV:
    def test_loads_by_name(self):
        cmap = CMapManager.get_predefined_cmap("Identity-V")
        assert cmap is not None
        assert cmap.get_name() == "Identity-V"

    def test_wmode_is_vertical(self):
        cmap = CMapManager.get_predefined_cmap("Identity-V")
        assert cmap is not None
        assert cmap.get_wmode() == 1


# ---------------------------------------------------------------------- #
# Adobe-Japan1-UCS2 — known JIS->Unicode mappings                        #
# ---------------------------------------------------------------------- #


class TestAdobeJapan1UCS2:
    def test_loads_by_name(self):
        cmap = CMapManager.get_predefined_cmap("Adobe-Japan1-UCS2")
        assert cmap is not None
        assert cmap.get_name() == "Adobe-Japan1-UCS2"

    def test_has_unicode_mappings(self):
        cmap = CMapManager.get_predefined_cmap("Adobe-Japan1-UCS2")
        assert cmap is not None
        assert cmap.has_unicode_mappings()

    def test_known_yen_sign_mapping(self):
        # First bfchar entry in the upstream resource:
        #   <003d> <00a5>  -- CID 0x003d (61) -> YEN SIGN U+00A5
        cmap = CMapManager.get_predefined_cmap("Adobe-Japan1-UCS2")
        assert cmap is not None
        assert cmap.to_unicode(0x003D) == "¥"

    def test_known_broken_bar_mapping(self):
        # Second bfchar entry: <005d> <00a6>  -- CID 0x005d -> BROKEN BAR.
        cmap = CMapManager.get_predefined_cmap("Adobe-Japan1-UCS2")
        assert cmap is not None
        assert cmap.to_unicode(0x005D) == "¦"

    def test_unmapped_cid_returns_none(self):
        cmap = CMapManager.get_predefined_cmap("Adobe-Japan1-UCS2")
        assert cmap is not None
        # CID 0 is the .notdef sentinel but it does map to U+FFFD here:
        #   <0000> <fffd>
        assert cmap.to_unicode(0x0000) == "�"


# ---------------------------------------------------------------------- #
# Other bundled CJK UCS2 maps — smoke-load each                          #
# ---------------------------------------------------------------------- #


class TestOtherBundledCMaps:
    @pytest.mark.parametrize(
        "name",
        [
            "Adobe-CNS1-UCS2",
            "Adobe-GB1-UCS2",
            "Adobe-Korea1-UCS2",
        ],
    )
    def test_load_smoke(self, name):
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None
        assert cmap.get_name() == name
        assert cmap.has_unicode_mappings()


# ---------------------------------------------------------------------- #
# Cache + missing-CMap behaviour                                         #
# ---------------------------------------------------------------------- #


class TestCacheAndMissing:
    def test_unknown_returns_none(self):
        assert CMapManager.get_predefined_cmap("NoSuchCMap-XYZ") is None

    def test_strict_snake_case_alias_preserves_missing_none_contract(self):
        assert CMapManager.get_predefined_c_map("NoSuchCMap-XYZ") is None

    def test_cache_returns_same_instance(self):
        first = CMapManager.get_predefined_cmap("Identity-H")
        second = CMapManager.get_predefined_cmap("Identity-H")
        assert first is second

    def test_strict_snake_case_alias_shares_cache(self):
        first = CMapManager.get_predefined_cmap("Identity-H")
        second = CMapManager.get_predefined_c_map("Identity-H")
        assert first is second

    def test_clear_cache_drops_instance(self):
        first = CMapManager.get_predefined_cmap("Identity-H")
        CMapManager.clear_cache()
        second = CMapManager.get_predefined_cmap("Identity-H")
        # New instance after clear_cache.
        assert first is not second
        # But still semantically equivalent.
        assert second is not None
        assert second.get_name() == "Identity-H"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            CMapManager()


# ---------------------------------------------------------------------- #
# Bundled CJK encoding CMaps — H/V pairs (Wave 32)                       #
#                                                                        #
# Each entry asserts: the CMap loads, has the expected metadata          #
# (registry / ordering / supplement / wmode), the codespace structure    #
# is right (via ``code_length_at`` on a representative leading byte),    #
# and a known multi-byte code resolves to the expected CID. Probe codes  #
# were chosen to be stable upstream-published mappings (e.g. ASCII / CJK #
# Unified Ideograph U+4E00 / first GB / Big5 / Shift_JIS / KSC code).    #
# ---------------------------------------------------------------------- #


_ENCODING_CMAP_METADATA = {
    # name: (registry, ordering, supplement, wmode)
    "UniCNS-UTF16-H": ("Adobe", "CNS1", 6, 0),
    "UniCNS-UTF16-V": ("Adobe", "CNS1", 6, 1),
    "UniGB-UTF16-H": ("Adobe", "GB1", 5, 0),
    "UniGB-UTF16-V": ("Adobe", "GB1", 5, 1),
    "UniJIS-UTF16-H": ("Adobe", "Japan1", 6, 0),
    "UniJIS-UTF16-V": ("Adobe", "Japan1", 6, 1),
    "UniKS-UTF16-H": ("Adobe", "Korea1", 1, 0),
    "UniKS-UTF16-V": ("Adobe", "Korea1", 1, 1),
    "GB-EUC-H": ("Adobe", "GB1", 0, 0),
    "GB-EUC-V": ("Adobe", "GB1", 0, 1),
    "B5pc-H": ("Adobe", "CNS1", 0, 0),
    "B5pc-V": ("Adobe", "CNS1", 0, 1),
    "90ms-RKSJ-H": ("Adobe", "Japan1", 2, 0),
    "90ms-RKSJ-V": ("Adobe", "Japan1", 2, 1),
    "KSC-EUC-H": ("Adobe", "Korea1", 0, 0),
    "KSC-EUC-V": ("Adobe", "Korea1", 0, 1),
}


class TestBundledEncodingCMaps:
    @pytest.mark.parametrize("name", list(_ENCODING_CMAP_METADATA.keys()))
    def test_loads_with_expected_name(self, name):
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None
        assert cmap.get_name() == name

    @pytest.mark.parametrize(
        "name,expected", list(_ENCODING_CMAP_METADATA.items())
    )
    def test_metadata(self, name, expected):
        registry, ordering, supplement, wmode = expected
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None
        assert cmap.get_registry() == registry
        assert cmap.get_ordering() == ordering
        assert cmap.get_supplement() == supplement
        assert cmap.get_wmode() == wmode


class TestUniCNSUTF16H:
    """``UniCNS-UTF16-H`` — UTF-16 → Adobe-CNS1 (Traditional Chinese)."""

    def test_codespace_is_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("UniCNS-UTF16-H")
        assert cmap is not None
        # Full UTF-16 plane: every leading byte yields a 2-byte code.
        assert cmap.code_length_at(0x21) == 2
        assert cmap.code_length_at(0xA1) == 2
        assert cmap.code_length_at(0x4E) == 2

    def test_ascii_space_maps_to_cid_1(self):
        cmap = CMapManager.get_predefined_cmap("UniCNS-UTF16-H")
        assert cmap is not None
        # Adobe-CNS1: U+0020 → CID 1.
        assert cmap.to_cid(0x0020) == 1

    def test_cjk_ideograph_one_maps(self):
        cmap = CMapManager.get_predefined_cmap("UniCNS-UTF16-H")
        assert cmap is not None
        # U+4E00 (一) → CID 595 in Adobe-CNS1.
        assert cmap.to_cid(0x4E00) == 595


class TestUniGBUTF16H:
    """``UniGB-UTF16-H`` — UTF-16 → Adobe-GB1 (Simplified Chinese)."""

    def test_codespace_is_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("UniGB-UTF16-H")
        assert cmap is not None
        assert cmap.code_length_at(0x21) == 2

    def test_cjk_ideograph_one_maps(self):
        cmap = CMapManager.get_predefined_cmap("UniGB-UTF16-H")
        assert cmap is not None
        # U+4E00 (一) → CID 4162 in Adobe-GB1.
        assert cmap.to_cid(0x4E00) == 4162


class TestUniJISUTF16H:
    """``UniJIS-UTF16-H`` — UTF-16 → Adobe-Japan1."""

    def test_codespace_is_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("UniJIS-UTF16-H")
        assert cmap is not None
        assert cmap.code_length_at(0x21) == 2

    def test_cjk_ideograph_one_maps(self):
        cmap = CMapManager.get_predefined_cmap("UniJIS-UTF16-H")
        assert cmap is not None
        # U+4E00 → CID 1200 in Adobe-Japan1.
        assert cmap.to_cid(0x4E00) == 1200


class TestUniKSUTF16H:
    """``UniKS-UTF16-H`` — UTF-16 → Adobe-Korea1."""

    def test_codespace_is_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("UniKS-UTF16-H")
        assert cmap is not None
        assert cmap.code_length_at(0x21) == 2

    def test_cjk_ideograph_one_maps(self):
        cmap = CMapManager.get_predefined_cmap("UniKS-UTF16-H")
        assert cmap is not None
        # U+4E00 → CID 6460 in Adobe-Korea1.
        assert cmap.to_cid(0x4E00) == 6460


class TestGBEUCH:
    """``GB-EUC-H`` — GB 2312-80 EUC encoding → Adobe-GB1."""

    def test_codespace_is_mixed_one_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("GB-EUC-H")
        assert cmap is not None
        # ASCII range: 1 byte; high-byte lead 0xA1 starts a 2-byte code.
        assert cmap.code_length_at(0x21) == 1
        assert cmap.code_length_at(0xA1) == 2

    def test_first_gb_two_byte_code(self):
        cmap = CMapManager.get_predefined_cmap("GB-EUC-H")
        assert cmap is not None
        # GB-EUC: 0xA1A1 (full-width space) → CID 96.
        assert cmap.to_cid(0xA1A1) == 96
        # 0xA1A2 → CID 97 (sequential mapping).
        assert cmap.to_cid(0xA1A2) == 97


class TestB5pcH:
    """``B5pc-H`` — Big5 (Mac OS Traditional Chinese) → Adobe-CNS1."""

    def test_codespace_is_mixed_one_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("B5pc-H")
        assert cmap is not None
        assert cmap.code_length_at(0x21) == 1
        assert cmap.code_length_at(0xA1) == 2

    def test_first_big5_codes(self):
        cmap = CMapManager.get_predefined_cmap("B5pc-H")
        assert cmap is not None
        # Big5 0xA1A1 → CID 162 (first non-ASCII Big5 row leader).
        assert cmap.to_cid(0xA1A1) == 162
        assert cmap.to_cid(0xA1A2) == 163
        # Big5 0xA440 → CID 595 (start of common-use ideographs).
        assert cmap.to_cid(0xA440) == 595


class Test90msRKSJH:
    """``90ms-RKSJ-H`` — Microsoft Shift_JIS → Adobe-Japan1."""

    def test_codespace_includes_shift_jis_lead(self):
        cmap = CMapManager.get_predefined_cmap("90ms-RKSJ-H")
        assert cmap is not None
        # ASCII range: 1 byte.
        assert cmap.code_length_at(0x21) == 1
        # Shift_JIS first lead-byte block 0x81-0x9F: 2 bytes.
        assert cmap.code_length_at(0x81) == 2
        # Half-width katakana 0xA1-0xDF: 1 byte.
        assert cmap.code_length_at(0xA1) == 1

    def test_shift_jis_two_byte_code(self):
        cmap = CMapManager.get_predefined_cmap("90ms-RKSJ-H")
        assert cmap is not None
        # Shift_JIS 0x8140 (full-width space) → CID 633 in Adobe-Japan1.
        assert cmap.to_cid(0x8140) == 633


class TestKSCEUCH:
    """``KSC-EUC-H`` — KS X 1001 EUC → Adobe-Korea1."""

    def test_codespace_is_mixed_one_two_byte(self):
        cmap = CMapManager.get_predefined_cmap("KSC-EUC-H")
        assert cmap is not None
        assert cmap.code_length_at(0x21) == 1
        assert cmap.code_length_at(0xA1) == 2

    def test_first_ksc_two_byte_codes(self):
        cmap = CMapManager.get_predefined_cmap("KSC-EUC-H")
        assert cmap is not None
        # KSC 0xA1A1 → CID 101 (first KS X 1001 row leader).
        assert cmap.to_cid(0xA1A1) == 101
        assert cmap.to_cid(0xA1A2) == 102


class TestVariantsInheritFromHorizontal:
    """V variants ``usecmap`` their H counterparts. Verify a known H
    mapping is reachable through the V cmap (proves usecmap recursion
    succeeded against the bundled resource set)."""

    @pytest.mark.parametrize(
        "v_name,probe_code,expected_cid",
        [
            ("UniCNS-UTF16-V", 0x4E00, 595),
            ("UniGB-UTF16-V", 0x4E00, 4162),
            ("UniJIS-UTF16-V", 0x4E00, 1200),
            ("UniKS-UTF16-V", 0x4E00, 6460),
            ("GB-EUC-V", 0xA1A1, 96),
            ("B5pc-V", 0xA1A1, 162),
            ("90ms-RKSJ-V", 0x8140, 633),
            ("KSC-EUC-V", 0xA1A1, 101),
        ],
    )
    def test_inherited_h_mapping(self, v_name, probe_code, expected_cid):
        cmap = CMapManager.get_predefined_cmap(v_name)
        assert cmap is not None
        assert cmap.to_cid(probe_code) == expected_cid


# ---------------------------------------------------------------------- #
# parse_cmap — arbitrary-input parser hook                               #
# ---------------------------------------------------------------------- #


class TestParseCMap:
    def test_returns_none_for_none_source(self):
        assert CMapManager.parse_cmap(None) is None

    def test_strict_snake_case_alias_returns_none_for_none_source(self):
        assert CMapManager.parse_c_map(None) is None

    def test_parses_minimal_bytes(self):
        # Minimal CMap fragment with just enough to populate name + a
        # codespace range. Exercises the bytes-input coercion path.
        data = (
            b"/CMapName /Test-CMap def\n"
            b"1 begincodespacerange\n"
            b"<00> <FF>\n"
            b"endcodespacerange\n"
            b"endcmap\n"
        )
        cmap = CMapManager.parse_cmap(data)
        assert cmap is not None
        assert cmap.get_name() == "Test-CMap"

    def test_strict_snake_case_alias_parses_minimal_bytes(self):
        data = (
            b"/CMapName /Alias-Test-CMap def\n"
            b"1 begincodespacerange\n"
            b"<00> <FF>\n"
            b"endcodespacerange\n"
            b"endcmap\n"
        )
        cmap = CMapManager.parse_c_map(data)
        assert cmap is not None
        assert cmap.get_name() == "Alias-Test-CMap"
