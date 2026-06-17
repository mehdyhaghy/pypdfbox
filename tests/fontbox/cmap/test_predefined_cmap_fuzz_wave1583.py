"""Fuzz / parity tests for predefined CMap resource loading (wave 1583).

Hammers the predefined-CMap resolution path that ``PDType0Font`` relies
on when a font's ``/Encoding`` is a named CMap (``Identity-H``,
``UniGB-UCS2-H``, ``90ms-RKSJ-H``, ...):

* the special-cased programmatic ``Identity-H`` / ``Identity-V`` builders
  (full 2-byte identity, WMode 0 vs 1),
* file-backed loads of bundled Adobe predefined CMaps by name,
* ``usecmap`` chaining — every bundled ``*-V`` CMap ``usecmap``s its
  ``*-H`` sibling, so the V CMap must inherit the H codespace ranges and
  code->CID mappings while overriding WMode to 1,
* unknown names (``parse_predefined`` raises ``OSError`` /
  ``CMapManager.get_predefined_cmap`` returns ``None``),
* WMode reporting and ``is_vertical`` derivation,
* code->CID lookups against a loaded predefined CMap,
* caching — repeated loads return the same cached instance, and
  ``clear_cache`` drops *both* predefined caches.

Cross-checked against upstream ``CMapParser.parsePredefined`` /
``CMap.useCmap`` semantics: ``useCmap`` copies codespace ranges + maps
but never WMode, so the V file's own ``/WMode 1 def`` is what sets WMode.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.cmap import CMapManager
from pypdfbox.fontbox.cmap import cmap_parser as _cmap_parser_mod
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser

_RESOURCES_DIR = Path(_cmap_parser_mod.__file__).parent / "resources"


@pytest.fixture(autouse=True)
def _clear_predefined_cache():
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


def _bundled_names() -> list[str]:
    return sorted(p.name for p in _RESOURCES_DIR.iterdir() if p.is_file())


# --------------------------------------------------------------------- #
# Identity-H / Identity-V                                               #
# --------------------------------------------------------------------- #


def test_identity_h_wmode_is_zero():
    cmap = CMapParser.parse_predefined("Identity-H")
    assert cmap.get_wmode() == 0
    assert cmap.get_w_mode() == 0
    assert cmap.get_name() == "Identity-H"


def test_identity_v_wmode_is_one():
    cmap = CMapParser.parse_predefined("Identity-V")
    assert cmap.get_wmode() == 1
    assert cmap.get_name() == "Identity-V"


def test_identity_h_is_horizontal_writing():
    cmap = CMapParser.parse_predefined("Identity-H")
    assert cmap.is_horizontal()
    assert not cmap.is_vertical()


def test_identity_v_is_vertical_writing():
    cmap = CMapParser.parse_predefined("Identity-V")
    assert cmap.is_vertical()
    assert not cmap.is_horizontal()


@pytest.mark.parametrize(
    "code",
    [0x0000, 0x0001, 0x0020, 0x0041, 0x1234, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF],
)
def test_identity_h_cid_equals_code(code):
    cmap = CMapParser.parse_predefined("Identity-H")
    assert cmap.to_cid(code) == code


@pytest.mark.parametrize(
    "code",
    [0x0000, 0x0041, 0x4E00, 0xABCD, 0xFFFF],
)
def test_identity_v_cid_equals_code(code):
    cmap = CMapParser.parse_predefined("Identity-V")
    assert cmap.to_cid(code) == code


def test_identity_h_registry_ordering_supplement():
    cmap = CMapParser.parse_predefined("Identity-H")
    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Identity"


def test_identity_programmatic_matches_bundled_file():
    # The programmatic Identity-H builder must produce identical to_cid
    # results as parsing the bundled Identity-H resource file.
    prog = CMapParser.parse_predefined("Identity-H")
    file_bytes = (_RESOURCES_DIR / "Identity-H").read_bytes()
    from_file = CMapParser(strict_mode=False).parse(file_bytes)
    for code in (0x0000, 0x0100, 0x1FFF, 0x8000, 0xC000, 0xFFFF):
        assert prog.to_cid(code) == from_file.to_cid(code)
    assert prog.get_wmode() == from_file.get_wmode()
    assert prog.get_name() == from_file.get_name()


# --------------------------------------------------------------------- #
# Bundled predefined CMaps by name                                      #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    ["UniGB-UCS2-H", "UniCNS-UCS2-H", "90ms-RKSJ-H", "B5pc-H", "GB-EUC-H"],
)
def test_bundled_h_cmap_loads_with_wmode_zero(name):
    cmap = CMapParser.parse_predefined(name)
    assert cmap is not None
    assert cmap.get_name() == name
    assert cmap.get_wmode() == 0
    assert len(cmap._codespace_ranges) >= 1


@pytest.mark.parametrize(
    "name",
    [
        "UniGB-UCS2-V",
        "UniCNS-UCS2-V",
        "90ms-RKSJ-V",
        "B5pc-V",
        "GB-EUC-V",
        "KSC-EUC-V",
    ],
)
def test_bundled_v_cmap_has_wmode_one(name):
    # Every bundled *-V CMap declares /WMode 1 def and usecmaps its
    # *-H sibling. useCmap must NOT clobber the WMode back to the H's 0.
    cmap = CMapParser.parse_predefined(name)
    assert cmap.get_wmode() == 1
    assert cmap.is_vertical()


def test_every_bundled_resource_parses():
    # Smoke: every file under resources/ must load without raising and
    # carry at least one codespace range.
    for name in _bundled_names():
        cmap = CMapParser.parse_predefined(name)
        assert cmap is not None, name
        assert len(cmap._codespace_ranges) >= 1, name


# --------------------------------------------------------------------- #
# usecmap chaining                                                      #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("v_name", "h_name"),
    [
        ("UniGB-UCS2-V", "UniGB-UCS2-H"),
        ("90ms-RKSJ-V", "90ms-RKSJ-H"),
        ("B5pc-V", "B5pc-H"),
        ("GB-EUC-V", "GB-EUC-H"),
    ],
)
def test_usecmap_inherits_codespace(v_name, h_name):
    h = CMapParser.parse_predefined(h_name)
    v = CMapParser.parse_predefined(v_name)
    # The V file defines no codespace of its own — it inherits all of the
    # H codespace ranges through usecmap.
    assert len(v._codespace_ranges) >= len(h._codespace_ranges)


@pytest.mark.parametrize(
    ("v_name", "h_name"),
    [
        ("90ms-RKSJ-V", "90ms-RKSJ-H"),
        ("UniGB-UCS2-V", "UniGB-UCS2-H"),
    ],
)
def test_usecmap_inherits_cid_ranges(v_name, h_name):
    h = CMapParser.parse_predefined(h_name)
    v = CMapParser.parse_predefined(v_name)
    # V folds in H's CID ranges (then may append its own vertical
    # overrides), so it has at least as many as H.
    assert len(v._code_to_cid_ranges) >= len(h._code_to_cid_ranges)


def test_usecmap_shared_code_maps_identically():
    # A 2-byte code that H maps to a CID and that V does not override
    # must resolve to the same CID through the usecmap chain.
    h = CMapParser.parse_predefined("90ms-RKSJ-H")
    v = CMapParser.parse_predefined("90ms-RKSJ-V")
    assert v.to_cid_bytes(b"\x81\x40") == h.to_cid_bytes(b"\x81\x40")


def test_identity_v_usecmaps_identity_h_codespace():
    # Identity-V's bundled file usecmaps Identity-H. The programmatic
    # builder reproduces the same full 2-byte codespace.
    v = CMapParser.parse_predefined("Identity-V")
    assert len(v._codespace_ranges) >= 1
    assert v.to_cid(0xABCD) == 0xABCD


# --------------------------------------------------------------------- #
# Unknown names                                                         #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    ["NoSuchCMap-H", "", "Identity", "identity-h", "UniGB-UCS2", "../etc"],
)
def test_unknown_name_parse_predefined_raises(name):
    with pytest.raises(OSError):
        CMapParser.parse_predefined(name)


@pytest.mark.parametrize(
    "name",
    ["NoSuchCMap-H", "Identity", "identity-h", "Totally-Fake-V"],
)
def test_unknown_name_manager_returns_none(name):
    assert CMapManager.get_predefined_cmap(name) is None


@pytest.mark.parametrize("name", ["NoSuchCMap-H", "Bogus"])
def test_unknown_name_get_cmap_for_name_returns_none(name):
    assert CMapParser.get_cmap_for_name(name) is None


# --------------------------------------------------------------------- #
# WMode derivation                                                      #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "expected_wmode"),
    [
        ("Identity-H", 0),
        ("Identity-V", 1),
        ("UniGB-UCS2-H", 0),
        ("UniGB-UCS2-V", 1),
        ("90ms-RKSJ-H", 0),
        ("90ms-RKSJ-V", 1),
    ],
)
def test_wmode_from_loaded_cmap(name, expected_wmode):
    cmap = CMapParser.parse_predefined(name)
    assert cmap.get_wmode() == expected_wmode
    assert cmap.is_vertical() == (expected_wmode == 1)


# --------------------------------------------------------------------- #
# code -> CID lookups                                                   #
# --------------------------------------------------------------------- #


def test_rksj_single_byte_lookup():
    cmap = CMapParser.parse_predefined("90ms-RKSJ-H")
    # Single-byte ASCII code resolves to a positive CID.
    cid = cmap.to_cid_bytes(b"\x20")
    assert isinstance(cid, int)
    assert cid >= 0


def test_rksj_double_byte_lookup():
    cmap = CMapParser.parse_predefined("90ms-RKSJ-H")
    cid = cmap.to_cid_bytes(b"\x81\x40")
    assert cid > 0


def test_unigb_ucs2_lookup_roundtrips():
    cmap = CMapParser.parse_predefined("UniGB-UCS2-H")
    # A 2-byte UCS2 code in the codespace resolves to a CID.
    cid = cmap.to_cid_bytes(b"\x4e\x00")
    assert isinstance(cid, int)


# --------------------------------------------------------------------- #
# Caching                                                               #
# --------------------------------------------------------------------- #


def test_manager_caches_same_instance():
    a = CMapManager.get_predefined_cmap("UniGB-UCS2-H")
    b = CMapManager.get_predefined_cmap("UniGB-UCS2-H")
    assert a is b


def test_get_cmap_for_name_caches_same_instance():
    a = CMapParser.get_cmap_for_name("90ms-RKSJ-H")
    b = CMapParser.get_cmap_for_name("90ms-RKSJ-H")
    assert a is b


def test_clear_cache_drops_manager_cache():
    first = CMapManager.get_predefined_cmap("UniGB-UCS2-H")
    CMapManager.clear_cache()
    second = CMapManager.get_predefined_cmap("UniGB-UCS2-H")
    assert first is not second


def test_clear_cache_drops_parser_predefined_cache():
    # Regression (wave 1583): CMapManager.clear_cache() must also drop the
    # CMapParser.get_cmap_for_name cache, otherwise a stale instance
    # survives the "drop all cached predefined CMaps" reset.
    first = CMapParser.get_cmap_for_name("UniGB-UCS2-H")
    CMapManager.clear_cache()
    second = CMapParser.get_cmap_for_name("UniGB-UCS2-H")
    assert first is not second


def test_clear_predefined_cache_directly():
    first = CMapParser.get_cmap_for_name("B5pc-H")
    CMapParser.clear_predefined_cache()
    second = CMapParser.get_cmap_for_name("B5pc-H")
    assert first is not second


def test_identity_not_clobbered_across_manager_loads():
    # Loading H then V (which share the Identity registry/ordering) must
    # not contaminate each other's WMode through any shared cache key.
    h = CMapManager.get_predefined_cmap("Identity-H")
    v = CMapManager.get_predefined_cmap("Identity-V")
    assert h.get_wmode() == 0
    assert v.get_wmode() == 1
