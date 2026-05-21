"""CMapManager predefined lookup matrix.

Wave 1369 round-out — exercises the four Adobe predefined CID character
collection UCS2 CMaps (Adobe-GB1, Adobe-CNS1, Adobe-Japan1, Adobe-Korea1)
plus the Identity-H/V and UniXxx-UTF16-H/V encoding-direction variants
bundled with this build. Mirrors the lookup contract of upstream
``CMapManager.getPredefinedCMap``.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_manager import CMapManager


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Cache state shouldn't leak across tests."""
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


# All four Adobe CID-collection UCS2 CMaps are bundled. Each shall load,
# parse, and report a CID-collection (Registry/Ordering) consistent with the
# CMap file's own /CIDSystemInfo entry (which uses the UCS2-suffixed form
# "Adobe_<Collection>_UCS2" — distinct from the CMap *name* "Adobe-<Collection>-UCS2").
@pytest.mark.parametrize(
    "name,registry,ordering",
    [
        ("Adobe-GB1-UCS2", "Adobe", "Adobe_GB1_UCS2"),
        ("Adobe-CNS1-UCS2", "Adobe", "Adobe_CNS1_UCS2"),
        ("Adobe-Japan1-UCS2", "Adobe", "Adobe_Japan1_UCS2"),
        ("Adobe-Korea1-UCS2", "Adobe", "Adobe_Korea1_UCS2"),
    ],
)
def test_predefined_ucs2_cmaps_load(
    name: str, registry: str, ordering: str
) -> None:
    cmap = CMapManager.get_predefined_cmap(name)
    assert isinstance(cmap, CMap)
    assert cmap.get_registry() == registry
    assert cmap.get_ordering() == ordering
    # The parsed CMap name matches the request.
    assert cmap.get_name() == name


@pytest.mark.parametrize("name", ["Identity-H", "Identity-V"])
def test_identity_cmaps_load(name: str) -> None:
    cmap = CMapManager.get_predefined_cmap(name)
    assert isinstance(cmap, CMap)
    # Identity CMaps map every input code straight through.
    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Identity"


@pytest.mark.parametrize("name", ["Identity-H", "Identity-V"])
def test_identity_cmaps_writing_mode(name: str) -> None:
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None
    # Identity-H is horizontal (wmode 0), Identity-V is vertical (wmode 1).
    expected_wmode = 1 if name.endswith("-V") else 0
    assert cmap.get_w_mode() == expected_wmode


@pytest.mark.parametrize(
    "name",
    [
        "UniCNS-UTF16-H",
        "UniGB-UTF16-H",
        "UniJIS-UTF16-H",
        "UniKS-UTF16-H",
    ],
)
def test_uni_utf16_h_variants_load(name: str) -> None:
    cmap = CMapManager.get_predefined_cmap(name)
    assert isinstance(cmap, CMap)
    # H = horizontal (wmode 0).
    assert cmap.get_w_mode() == 0


@pytest.mark.parametrize(
    "name",
    [
        "UniCNS-UTF16-V",
        "UniGB-UTF16-V",
        "UniJIS-UTF16-V",
        "UniKS-UTF16-V",
    ],
)
def test_uni_utf16_v_variants_load(name: str) -> None:
    cmap = CMapManager.get_predefined_cmap(name)
    assert isinstance(cmap, CMap)
    # V = vertical (wmode 1).
    assert cmap.get_w_mode() == 1


def test_unknown_predefined_returns_none() -> None:
    # Missing CMaps (the upstream ships ~50 — we ship a curated subset)
    # return None rather than raising. Mirrors upstream's
    # ``IOException`` → ``None`` convention documented on the loader.
    assert CMapManager.get_predefined_cmap("Not-A-Real-CMap") is None


def test_cache_returns_same_instance() -> None:
    # First call: cold load. Second call: cached.
    first = CMapManager.get_predefined_cmap("Identity-H")
    second = CMapManager.get_predefined_cmap("Identity-H")
    assert first is second


def test_cache_is_keyed_by_resolved_name() -> None:
    # The cache uses the parsed CMap's own ``name`` (which equals the
    # request when the request was a valid predefined). Look both directions.
    a = CMapManager.get_predefined_cmap("Identity-H")
    assert a is not None
    assert a.get_name() == "Identity-H"
    # Re-request via the same name — same singleton.
    assert CMapManager.get_predefined_cmap(a.get_name() or "Identity-H") is a


def test_clear_cache_forces_reload() -> None:
    first = CMapManager.get_predefined_cmap("Identity-H")
    assert first is not None
    CMapManager.clear_cache()
    reloaded = CMapManager.get_predefined_cmap("Identity-H")
    assert reloaded is not None
    # Identity check: after clear_cache the loader produces a fresh instance.
    assert reloaded is not first


def test_get_predefined_c_map_alias() -> None:
    # CMapManager exposes both ``get_predefined_cmap`` (Python-natural) and
    # ``get_predefined_c_map`` (literal upstream camelCase → snake form).
    via_cmap = CMapManager.get_predefined_cmap("Identity-H")
    via_c_map = CMapManager.get_predefined_c_map("Identity-H")
    # Same singleton through either entry point.
    assert via_cmap is via_c_map


def test_parse_cmap_with_none_source_returns_none() -> None:
    # Upstream ``CMapManager.parseCMap(null)`` returns null. The pypdfbox
    # equivalent: ``None`` in, ``None`` out.
    assert CMapManager.parse_cmap(None) is None
    assert CMapManager.parse_c_map(None) is None
