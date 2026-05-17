"""Hand-written tests for :class:`MapBackedScriptFeature`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.model import MapBackedScriptFeature


def test_get_name() -> None:
    feature = MapBackedScriptFeature("liga", {(84, 93): 256})
    assert feature.get_name() == "liga"


def test_get_all_glyph_ids_for_substitution_returns_keys() -> None:
    feature = MapBackedScriptFeature(
        "liga", {(84, 93): 256, (104, 87): 257}
    )
    assert feature.get_all_glyph_ids_for_substitution() == {(84, 93), (104, 87)}


def test_can_replace_glyphs_matches_input_list() -> None:
    feature = MapBackedScriptFeature("liga", {(84, 93): 256})
    assert feature.can_replace_glyphs([84, 93])
    assert not feature.can_replace_glyphs([84, 94])
    assert not feature.can_replace_glyphs([])


def test_get_replacement_for_glyphs_returns_substitute() -> None:
    feature = MapBackedScriptFeature("liga", {(84, 93): 256})
    assert feature.get_replacement_for_glyphs([84, 93]) == 256


def test_get_replacement_for_glyphs_raises_when_missing() -> None:
    feature = MapBackedScriptFeature("liga", {(84, 93): 256})
    with pytest.raises(NotImplementedError):
        feature.get_replacement_for_glyphs([1, 2, 3])


def test_equality_and_hash() -> None:
    a = MapBackedScriptFeature("liga", {(1, 2): 9})
    b = MapBackedScriptFeature("liga", {(1, 2): 9})
    c = MapBackedScriptFeature("ccmp", {(1, 2): 9})
    d = MapBackedScriptFeature("liga", {(1, 2): 10})
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert a != d
    assert a != "not a feature"


def test_snapshot_is_independent_of_input_dict() -> None:
    source = {(1, 2): 9}
    feature = MapBackedScriptFeature("liga", source)
    source[(3, 4)] = 99
    assert feature.get_all_glyph_ids_for_substitution() == {(1, 2)}


def test_eq_self_identity_short_circuit() -> None:
    # Hits the ``self is other`` short-circuit branch in __eq__.
    feature = MapBackedScriptFeature("liga", {(1, 2): 9})
    assert feature == feature  # noqa: PLR0124


def test_equals_method_mirrors_python_eq() -> None:
    a = MapBackedScriptFeature("liga", {(1, 2): 9})
    b = MapBackedScriptFeature("liga", {(1, 2): 9})
    c = MapBackedScriptFeature("ccmp", {(1, 2): 9})
    assert a.equals(b) is True
    assert a.equals(c) is False
    assert a.equals("not-a-feature") is False


def test_hash_code_method_mirrors_python_hash() -> None:
    feature = MapBackedScriptFeature("liga", {(1, 2): 9})
    assert feature.hash_code() == hash(feature)
