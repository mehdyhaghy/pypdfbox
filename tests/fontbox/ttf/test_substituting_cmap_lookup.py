"""Tests for :class:`SubstitutingCmapLookup`."""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.substituting_cmap_lookup import SubstitutingCmapLookup


class _FakeCmap:
    """Minimal :class:`CmapSubtable` stand-in for parity testing."""

    def __init__(
        self,
        cp_to_gid: dict[int, int],
        gid_to_codes: dict[int, list[int]] | None = None,
    ) -> None:
        self._cp_to_gid = cp_to_gid
        self._gid_to_codes = gid_to_codes or {}

    def get_glyph_id(self, cp: int) -> int:
        return self._cp_to_gid.get(cp, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return self._gid_to_codes.get(gid)


class _FakeGsub:
    """Captures the script-tag and feature list each call uses."""

    def __init__(self, gid_subs: dict[int, int]) -> None:
        self._subs = gid_subs
        # Reverse table built from ``gid_subs`` so ``get_unsubstitution``
        # can flip a substituted gid back to its original.
        self._reverse = {v: k for k, v in gid_subs.items()}
        self.calls: list[tuple[int, Any, Any]] = []

    def get_substitution(
        self,
        gid: int,
        script_tags: Any,
        enabled_features: Any,
    ) -> int:
        self.calls.append((gid, script_tags, enabled_features))
        return self._subs.get(gid, gid)

    def get_unsubstitution(self, sgid: int) -> int:
        return self._reverse.get(sgid, sgid)


def test_lookup_inherits_cmap_lookup_interface() -> None:
    lookup = SubstitutingCmapLookup(_FakeCmap({}), _FakeGsub({}), [])
    assert isinstance(lookup, CmapLookup)


def test_get_glyph_id_pipes_through_gsub() -> None:
    cmap = _FakeCmap({0x0041: 10})  # 'A' -> gid 10
    gsub = _FakeGsub({10: 99})  # 10 -> 99
    lookup = SubstitutingCmapLookup(cmap, gsub, ["liga"])
    assert lookup.get_glyph_id(0x0041) == 99


def test_get_glyph_id_passes_script_tags() -> None:
    cmap = _FakeCmap({0x0041: 5})
    gsub = _FakeGsub({})
    lookup = SubstitutingCmapLookup(cmap, gsub, ["liga"])
    lookup.get_glyph_id(0x0041)
    # 'A' is Latin → ('latn',)
    assert gsub.calls[0][1] == ["latn"]
    assert gsub.calls[0][2] == ["liga"]


def test_get_char_codes_walks_through_unsubstitution() -> None:
    cmap = _FakeCmap({}, {10: [0x0041]})
    gsub = _FakeGsub({10: 99})
    lookup = SubstitutingCmapLookup(cmap, gsub, [])
    # gid 99 → original 10 → codepoint 0x0041.
    assert lookup.get_char_codes(99) == [0x0041]


def test_none_enabled_features_forwarded_as_none() -> None:
    cmap = _FakeCmap({0x0041: 5})
    gsub = _FakeGsub({})
    SubstitutingCmapLookup(cmap, gsub, None).get_glyph_id(0x0041)
    assert gsub.calls[0][2] is None


def test_enabled_features_copied_not_shared() -> None:
    # The constructor must store an internal copy so the caller can
    # mutate the original list afterwards without affecting subsequent
    # lookups (mirrors the immutability guarantee of upstream's
    # ``final List<String> enabledFeatures`` field semantics).
    cmap = _FakeCmap({0x0041: 5})
    gsub = _FakeGsub({})
    features = ["liga"]
    lookup = SubstitutingCmapLookup(cmap, gsub, features)
    features.append("kern")
    lookup.get_glyph_id(0x0041)
    assert gsub.calls[-1][2] == ["liga"]


def test_inherited_codepoint_forwards_inherited_tag() -> None:
    # 0x0300 = COMBINING GRAVE ACCENT (Inherited script).
    cmap = _FakeCmap({0x0300: 1})
    gsub = _FakeGsub({})
    SubstitutingCmapLookup(cmap, gsub, []).get_glyph_id(0x0300)
    # OpenTypeScript returns the literal "Inherited" string, not "DFLT".
    assert gsub.calls[0][1] == ["Inherited"]
