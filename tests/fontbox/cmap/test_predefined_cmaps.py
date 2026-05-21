"""Predefined-CMap coverage tests.

Hand-written enumeration of every predefined CMap name pypdfbox is
expected to resolve through :class:`CMapManager.get_predefined_cmap` —
the 14 ISO 32000-1 §9.7.5.2 GB / Identity / Unicode CMaps in particular,
plus the bundled Adobe-* UCS2 helpers and the CJK encoding CMaps
covering Adobe-CNS1, Adobe-Japan1 and Adobe-Korea1.

Names not currently bundled (full Adobe predefined catalog runs ~50
files / tens of MB) are exercised through the negative path: missing
resources must fall back to ``None`` rather than raising. The
:class:`CHANGES.md` row "fontbox/cmap predefined resource set is
curated" documents the intentional gap.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMapManager


@pytest.fixture(autouse=True)
def _clear_predefined_cache():
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


# --------------------------------------------------------------------- #
# ISO 32000-1 §9.7.5.2 — bundled predefined CMaps                       #
#                                                                       #
# Every entry below is bundled in ``pypdfbox/fontbox/cmap/resources/``  #
# and must resolve. Probes assert the upstream-published                #
# Registry/Ordering/Supplement triple and write-mode flag.              #
# --------------------------------------------------------------------- #


_BUNDLED_PREDEFINED = {
    # Identity (algorithmic — no resource lookup needed).
    "Identity-H": ("Adobe", "Identity", 0, 0),
    "Identity-V": ("Adobe", "Identity", 0, 1),
    # Adobe-* UCS2 — CID -> Unicode mapping helpers. Note these CMaps
    # carry their own ``Adobe_<font>_UCS2`` ordering string (distinct
    # from the encoding CMaps' bare ``CNS1`` / ``GB1`` / ``Japan1`` /
    # ``Korea1`` orderings) — that is the upstream metadata as shipped.
    "Adobe-CNS1-UCS2": ("Adobe", "Adobe_CNS1_UCS2", 5, 0),
    "Adobe-GB1-UCS2": ("Adobe", "Adobe_GB1_UCS2", 5, 0),
    "Adobe-Japan1-UCS2": ("Adobe", "Adobe_Japan1_UCS2", 6, 0),
    "Adobe-Korea1-UCS2": ("Adobe", "Adobe_Korea1_UCS2", 2, 0),
    # CJK encoding CMaps — H + V pairs.
    "UniCNS-UTF16-H": ("Adobe", "CNS1", 6, 0),
    "UniCNS-UTF16-V": ("Adobe", "CNS1", 6, 1),
    "UniGB-UTF16-H": ("Adobe", "GB1", 5, 0),
    "UniGB-UTF16-V": ("Adobe", "GB1", 5, 1),
    "UniJIS-UTF16-H": ("Adobe", "Japan1", 6, 0),
    "UniJIS-UTF16-V": ("Adobe", "Japan1", 6, 1),
    "UniJIS-UCS2-H": ("Adobe", "Japan1", 4, 0),
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


class TestEveryBundledPredefinedCMapResolves:
    @pytest.mark.parametrize("name", sorted(_BUNDLED_PREDEFINED))
    def test_load_returns_named_cmap(self, name):
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None, f"{name!r} must be resolvable"
        assert cmap.get_name() == name

    @pytest.mark.parametrize(
        "name,expected", sorted(_BUNDLED_PREDEFINED.items())
    )
    def test_cid_system_info_triple(self, name, expected):
        registry, ordering, supplement, wmode = expected
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None
        assert cmap.get_registry() == registry
        assert cmap.get_ordering() == ordering
        assert cmap.get_supplement() == supplement
        assert cmap.get_wmode() == wmode

    @pytest.mark.parametrize("name", sorted(_BUNDLED_PREDEFINED))
    def test_typed_cid_system_info_dict(self, name):
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None
        info = cmap.get_cid_system_info()
        assert info is not None
        assert info["Registry"] == cmap.get_registry()
        assert info["Ordering"] == cmap.get_ordering()
        assert info["Supplement"] == cmap.get_supplement()

    @pytest.mark.parametrize(
        "name,expected", sorted(_BUNDLED_PREDEFINED.items())
    )
    def test_combined_name(self, name, expected):
        registry, ordering, supplement, _wmode = expected
        cmap = CMapManager.get_predefined_cmap(name)
        assert cmap is not None
        assert cmap.get_combined_name() == f"{registry}-{ordering}-{supplement}"


# --------------------------------------------------------------------- #
# Caching — same instance must be returned across calls                 #
# --------------------------------------------------------------------- #


class TestCachingAcrossPredefinedNames:
    @pytest.mark.parametrize(
        "name",
        sorted(set(_BUNDLED_PREDEFINED) - {"Identity-H", "Identity-V"}),
    )
    def test_cache_returns_same_instance(self, name):
        first = CMapManager.get_predefined_cmap(name)
        second = CMapManager.get_predefined_cmap(name)
        assert first is not None
        assert first is second


# --------------------------------------------------------------------- #
# Negative path — predefined names not bundled                          #
#                                                                       #
# These names are part of the upstream Adobe predefined CMap catalog    #
# but are NOT bundled with pypdfbox (CHANGES.md notes the intentional   #
# gap). They must resolve to ``None`` rather than raising — that is the #
# graceful-degradation contract pypdfbox font loaders depend on.        #
# --------------------------------------------------------------------- #


_UNBUNDLED_PREDEFINED = [
    # GB family beyond GB-EUC-H/V and UniGB-UTF16-H/V — not bundled.
    "GBpc-EUC-H",
    "GBpc-EUC-V",
    "GBK-EUC-H",
    "GBK-EUC-V",
    "GBK2K-H",
    "GBK2K-V",
    "UniGB-UCS2-H",
    "UniGB-UCS2-V",
    # CNS1 / Japan1 / Korea1 names that are not in the curated subset.
    "ETen-B5-H",
    "ETen-B5-V",
    "UniCNS-UCS2-H",
    "UniCNS-UCS2-V",
    "83pv-RKSJ-H",
    "EUC-H",
    "EUC-V",
    "UniJIS-UCS2-V",
    "UniJIS-UCS2-HW-H",
    "UniJIS-UCS2-HW-V",
    "UniKS-UCS2-H",
    "UniKS-UCS2-V",
]


class TestUnbundledPredefinedFallsBackToNone:
    @pytest.mark.parametrize("name", _UNBUNDLED_PREDEFINED)
    def test_returns_none(self, name):
        assert CMapManager.get_predefined_cmap(name) is None

    def test_unknown_garbage_name_returns_none(self):
        assert CMapManager.get_predefined_cmap("definitely-not-a-cmap") is None
