"""Oracle-independent regression pins for predefined-CMap ``to_cid`` /
``read_code`` byte-length, ``usecmap`` override precedence, and the
out-of-codespace recovery path.

The sibling ``tests/fontbox/cmap/oracle/*`` files reconstruct these values live
against Apache PDFBox 3.0.7 and therefore only run when the oracle harness is
present (``@requires_oracle``). This module hard-codes the literal values that
those probes returned (verified live against PDFBox 3.0.7 in wave 1482) so the
contract is enforced on every CI run, with no JVM required.

Facets pinned here that the metadata-only ``test_predefined_cmaps.py`` does not
cover:

* **Identity-H / Identity-V** — the programmatic 2-byte identity builders:
  ``to_cid(code) == code`` over the whole ``<0000>..<FFFF>`` range and
  ``read_code`` always commits to 2 bytes, with the -V variant only differing
  in WMode.
* **``usecmap`` override precedence.** ``90ms-RKSJ-V`` chains
  ``/90ms-RKSJ-H usecmap`` and then re-declares a subset of cidranges with
  vertical CIDs. So ``<8340>`` maps to **925** under -H but **7928** under -V
  (the V cidrange *overrides* the inherited H mapping), while ``<8140>`` maps
  to **633** under *both* (inherited from the H base, never overridden) — the
  precise signature of correct usecmap inheritance + override.
* **Mixed-width codespace.** ``GBK-EUC-H``: a leading byte ``0x00..0x80`` opens
  a 1-byte code, ``0x81..0xFE`` a 2-byte code, so ``read_code`` consumes a
  variable number of bytes.
* **``to_cid`` for a code outside every cidrange → 0.** ``UniGB-UCS2-H``'s
  ``<FFFF>`` and every code under ``Adobe-Japan1-UCS2`` (a UCS2 CMap with *no*
  CID mappings) resolve to CID 0 — not the raw code.
* **Out-of-codespace recovery.** A code matching no codespace at any length
  (``<FFFF>`` under ``GBK-EUC-H``, whose 2-byte band tops out at ``0xFE??``)
  triggers the ISO-recovery / "Adobe Reader" fallback: ``read_code`` rewinds
  and commits to ``min_code_length`` bytes, so the consumed length is 1 and the
  returned code is the single leading byte (``0xFF`` → 255).

Every literal below was produced by ``oracle/probes/PredefCMapProbe.java``
against ``pdfbox-app-3.0.7.jar``.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_manager import CMapManager
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser


@pytest.fixture(autouse=True)
def _clear_predefined_cache():
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


def _to_int(hexcode: str) -> int:
    value = 0
    for b in bytes.fromhex(hexcode):
        value = (value << 8) | (b & 0xFF)
    return value


def _read_len(cmap: CMap, hexcode: str) -> tuple[int, int]:
    """Return ``(code, byte_length)`` for ``read_code`` over the hex bytes."""
    return cmap.read_code(bytes.fromhex(hexcode), 0)


# (name, hexcode) -> (expected_cid, expected_read_code_value, expected_length)
_PREDEF_CID_LEN: dict[tuple[str, str], tuple[int, int, int]] = {
    # Identity-H / -V: code == CID, always 2-byte codespace.
    ("Identity-H", "0000"): (0, 0x0000, 2),
    ("Identity-H", "0041"): (65, 0x0041, 2),
    ("Identity-H", "ABCD"): (43981, 0xABCD, 2),
    ("Identity-H", "FFFF"): (65535, 0xFFFF, 2),
    ("Identity-V", "0000"): (0, 0x0000, 2),
    ("Identity-V", "0041"): (65, 0x0041, 2),
    ("Identity-V", "ABCD"): (43981, 0xABCD, 2),
    ("Identity-V", "FFFF"): (65535, 0xFFFF, 2),
    # 90ms-RKSJ-H base.
    ("90ms-RKSJ-H", "8340"): (925, 0x8340, 2),
    ("90ms-RKSJ-H", "8140"): (633, 0x8140, 2),
    ("90ms-RKSJ-H", "2121"): (0, 0x21, 1),  # 0x21 is a 1-byte code
    # 90ms-RKSJ-V — usecmap override: 8340 differs (7928 vs 925),
    # 8140 inherited unchanged (633).
    ("90ms-RKSJ-V", "8340"): (7928, 0x8340, 2),
    ("90ms-RKSJ-V", "8140"): (633, 0x8140, 2),
    ("90ms-RKSJ-V", "2121"): (0, 0x21, 1),
    # GBK-EUC-H — mixed-width codespace.
    ("GBK-EUC-H", "41"): (846, 0x41, 1),
    ("GBK-EUC-H", "8140"): (10072, 0x8140, 2),
    ("GBK-EUC-H", "A1A1"): (96, 0xA1A1, 2),
    ("GBK-EUC-H", "FE40"): (4697, 0xFE40, 2),
    ("GBK-EUC-H", "80"): (0, 0x80, 1),  # 0x80 in the 1-byte band
    # to_cid outside every cidrange -> 0.
    ("UniGB-UCS2-H", "0041"): (34, 0x0041, 2),
    ("UniGB-UCS2-H", "FFFF"): (0, 0xFFFF, 2),
    # Adobe-Japan1-UCS2: no CID mappings, every code -> CID 0.
    ("Adobe-Japan1-UCS2", "0041"): (0, 0x0041, 2),
    ("Adobe-Japan1-UCS2", "3042"): (0, 0x3042, 2),
    ("Adobe-Japan1-UCS2", "FFFF"): (0, 0xFFFF, 2),
}


@pytest.mark.parametrize(
    "name,hexcode,expected",
    [(n, h, v) for (n, h), v in _PREDEF_CID_LEN.items()],
    ids=[f"{n}-{h}" for (n, h) in _PREDEF_CID_LEN],
)
def test_predefined_to_cid_and_read_len(
    name: str, hexcode: str, expected: tuple[int, int, int]
) -> None:
    """``to_cid`` and ``read_code`` byte-length pinned to the PDFBox 3.0.7
    oracle literals (no JVM needed)."""
    exp_cid, exp_code, exp_len = expected
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None, f"bundled CMap failed to load: {name}"
    assert cmap.to_cid(_to_int(hexcode)) == exp_cid
    code, length = _read_len(cmap, hexcode)
    assert (code, length) == (exp_code, exp_len)


def test_usecmap_override_precedence_90ms_rksj() -> None:
    """``90ms-RKSJ-V`` re-declares a vertical cidrange that overrides the
    ``usecmap``-inherited ``90ms-RKSJ-H`` mapping for ``<8340>`` while leaving
    ``<8140>`` inherited unchanged — the defining signature of usecmap
    inheritance + override precedence."""
    horiz = CMapManager.get_predefined_cmap("90ms-RKSJ-H")
    vert = CMapManager.get_predefined_cmap("90ms-RKSJ-V")
    assert horiz is not None and vert is not None

    # Overridden by the V cidrange.
    assert horiz.to_cid(0x8340) == 925
    assert vert.to_cid(0x8340) == 7928
    assert horiz.to_cid(0x8340) != vert.to_cid(0x8340)

    # Inherited from the H base, identical under both.
    assert horiz.to_cid(0x8140) == 633
    assert vert.to_cid(0x8140) == 633

    # WMode is the one metadata field the V variant flips.
    assert horiz.get_wmode() == 0
    assert vert.get_wmode() == 1

    # The inherited codespace assigns the same byte length under both.
    assert vert.get_min_code_length() == horiz.get_min_code_length()
    assert vert.get_max_code_length() == horiz.get_max_code_length()


def test_identity_builder_metadata_and_identity_mapping() -> None:
    """``CMapParser.parse_predefined`` builds Identity-H/V programmatically:
    Adobe-Identity-0, 2-byte codespace, ``to_cid(code) == code`` everywhere,
    -V differing only in WMode."""
    for name, wmode in (("Identity-H", 0), ("Identity-V", 1)):
        cmap = CMapParser.parse_predefined(name)
        assert cmap.get_name() == name
        assert cmap.get_registry() == "Adobe"
        assert cmap.get_ordering() == "Identity"
        assert cmap.get_supplement() == 0
        assert cmap.get_wmode() == wmode
        assert cmap.get_min_code_length() == 2
        assert cmap.get_max_code_length() == 2
        for code in (0x0000, 0x0041, 0x1234, 0xABCD, 0xFFFF):
            assert cmap.to_cid(code) == code


def test_out_of_codespace_recovery_returns_min_length_prefix() -> None:
    """A code matching no codespace at any length triggers the ISO / Adobe
    Reader recovery: ``read_code`` rewinds and commits to ``min_code_length``
    bytes. ``GBK-EUC-H``'s 2-byte band tops out at ``0xFE??`` so ``<FFFF>``
    matches nothing — the consumed length is 1 and the code is the single
    leading byte ``0xFF`` (255). ``to_cid`` of the full value is 0."""
    cmap = CMapManager.get_predefined_cmap("GBK-EUC-H")
    assert cmap is not None
    code, length = cmap.read_code(bytes.fromhex("FFFF"), 0)
    assert (code, length) == (0xFF, 1)
    assert cmap.to_cid(0xFFFF) == 0
