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

    def test_cache_returns_same_instance(self):
        first = CMapManager.get_predefined_cmap("Identity-H")
        second = CMapManager.get_predefined_cmap("Identity-H")
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
# parse_cmap — arbitrary-input parser hook                               #
# ---------------------------------------------------------------------- #


class TestParseCMap:
    def test_returns_none_for_none_source(self):
        assert CMapManager.parse_cmap(None) is None

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
