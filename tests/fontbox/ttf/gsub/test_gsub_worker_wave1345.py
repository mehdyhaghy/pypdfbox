"""Wave 1345 coverage-boost tests for the shared GSUB helpers.

Covers the residual branches of
``pypdfbox.fontbox.ttf.gsub.gsub_worker``:

* line 84 — :meth:`_DictScriptFeature.get_name`.
* line 114 — :func:`_adapt_feature` returning an already-conformant
  :class:`_ScriptFeatureLike` unchanged.
* lines 117-118 — :func:`_adapt_feature` raising :class:`TypeError` for
  unsupported feature shapes.
* line 141 — :func:`_split_into_chunks` empty-substitution-keys early
  return (the "every glyph is its own chunk" path).
* line 187 — :func:`_iterable_to_list` defensive copy helper.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub.gsub_worker import (
    _adapt_feature,
    _DictScriptFeature,
    _iterable_to_list,
    _split_into_chunks,
)


def test_dict_script_feature_get_name_returns_constructor_name() -> None:
    """``_DictScriptFeature.get_name`` round-trips the constructor name."""
    feature = _DictScriptFeature("liga", {(1, 2): (99,)})
    assert feature.get_name() == "liga"


class _AlreadyConformant:
    """A real :class:`_ScriptFeatureLike` — used to exercise
    :func:`_adapt_feature`'s short-circuit on line 114."""

    def get_name(self) -> str:
        return "real"

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        return {(7,)}

    def can_replace_glyphs(self, glyphs: list[int]) -> bool:
        return tuple(glyphs) == (7,)

    def get_replacement_for_glyphs(self, glyphs: list[int]) -> int:
        return 8


def test_adapt_feature_passes_through_conformant_instance() -> None:
    """When the argument already satisfies :class:`_ScriptFeatureLike`,
    :func:`_adapt_feature` returns it unchanged (line 114)."""
    feature = _AlreadyConformant()
    adapted = _adapt_feature("real", feature)
    assert adapted is feature


def test_adapt_feature_raises_typeerror_for_unsupported_shape() -> None:
    """A non-dict, non-conformant feature raises :class:`TypeError`
    (lines 117-118)."""
    with pytest.raises(TypeError, match="Unsupported ScriptFeature shape"):
        _adapt_feature("bogus", object())


def test_split_into_chunks_empty_substitution_keys_returns_per_glyph_chunks() -> None:
    """With an empty substitution-key set every glyph becomes its own
    one-element chunk (line 141)."""
    out = _split_into_chunks([10, 11, 12], set())
    assert out == [[10], [11], [12]]


def test_iterable_to_list_materialises_iterables() -> None:
    """``_iterable_to_list`` is a defensive copy that materialises any
    iterable of ints into a fresh list (line 187)."""
    source = (1, 2, 3)
    result = _iterable_to_list(iter(source))
    assert result == [1, 2, 3]
    assert isinstance(result, list)
