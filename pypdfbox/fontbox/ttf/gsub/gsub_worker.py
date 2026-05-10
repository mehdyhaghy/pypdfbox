"""``GsubWorker`` interface plus shared helpers used by every per-script worker.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorker`` from upstream Apache
PDFBox 3.0.x. Each writing-system worker is responsible for replacing
GlyphIDs with new ones according to the GSUB tables for that script.

The private helpers in this module (``_ScriptFeatureLike``,
``_split_into_chunks``, ``_apply_gsub_feature``) factor out the
"split-then-substitute" loop that every concrete worker repeats; in
upstream those live in ``GlyphArraySplitterRegexImpl`` plus copy-pasted
``applyGsubFeature`` methods in every worker class. Keeping them in one
place here avoids duplicating the same six-line loop five times.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable


class GsubWorker(ABC):
    """Abstract base for per-script GSUB workers.

    Concrete subclasses apply OpenType GSUB substitutions (plus any
    pre/post repositioning) for one writing system (Latin, Devanagari,
    Bengali, Gujarati, ...).
    """

    @abstractmethod
    def apply_transforms(self, original_glyph_ids: list[int]) -> list[int]:
        """Apply language-specific transforms to ``original_glyph_ids``.

        Returns the list of transformed glyph IDs. The returned list
        should be treated as read-only by callers; implementations are
        free (and encouraged) to return an immutable copy.
        """


@runtime_checkable
class _ScriptFeatureLike(Protocol):
    """Structural protocol matching upstream's ``ScriptFeature``.

    Concrete shapes the workers accept:

    * a real ``ScriptFeature`` object (when one is ported in a future
      wave), or
    * a substitution-map dict (the shape :class:`GsubData.get_feature`
      currently returns) wrapped via :class:`_DictScriptFeature`.
    """

    def get_name(self) -> str: ...

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]: ...

    def can_replace_glyphs(self, glyphs: list[int]) -> bool: ...

    def get_replacement_for_glyphs(self, glyphs: list[int]) -> int: ...


class _DictScriptFeature:
    """Wrap the ``feature_tag -> {glyph_run -> substitution}`` dict from
    :class:`pypdfbox.fontbox.ttf.gsub.GsubData` so it satisfies
    :class:`_ScriptFeatureLike`.

    Only single-glyph substitutions (``len(substitution) == 1``) are
    eligible for the per-script ligature/conjunct collapse upstream
    performs; everything else falls through unchanged.
    """

    __slots__ = ("_name", "_table")

    def __init__(
        self,
        name: str,
        table: dict[tuple[int, ...], tuple[int, ...]],
    ) -> None:
        self._name = name
        self._table = table

    def get_name(self) -> str:
        return self._name

    def get_all_glyph_ids_for_substitution(self) -> set[tuple[int, ...]]:
        # Upstream only emits substitution clusters whose replacement is
        # a single glyph id; multi-glyph (one-to-many) substitutions are
        # tracked separately in the lookup graph.
        return {k for k, v in self._table.items() if len(v) == 1}

    def can_replace_glyphs(self, glyphs: list[int]) -> bool:
        key = tuple(glyphs)
        sub = self._table.get(key)
        return sub is not None and len(sub) == 1

    def get_replacement_for_glyphs(self, glyphs: list[int]) -> int:
        return self._table[tuple(glyphs)][0]


def _adapt_feature(
    name: str,
    feature: object,
) -> _ScriptFeatureLike | None:
    """Wrap ``feature`` so it satisfies :class:`_ScriptFeatureLike`.

    Returns ``None`` when ``feature`` is ``None`` (the upstream
    ``isFeatureSupported`` already filters this, but defending here
    keeps each worker's loop tidy).
    """
    if feature is None:
        return None
    if isinstance(feature, _ScriptFeatureLike):
        return feature
    if isinstance(feature, dict):
        return _DictScriptFeature(name, feature)
    msg = f"Unsupported ScriptFeature shape: {type(feature).__name__}"
    raise TypeError(msg)


def _split_into_chunks(
    glyph_ids: list[int],
    substitution_keys: set[tuple[int, ...]],
) -> list[list[int]]:
    """Greedy longest-match left-to-right split of ``glyph_ids``.

    Mirrors what ``GlyphArraySplitterRegexImpl.split`` does upstream:
    walks the glyph stream, emitting either a matched substitution
    cluster (as its own chunk) or a single unmatched glyph (also as a
    one-element chunk). Returns an empty list for an empty input.

    The upstream implementation compiles a regex from the substitution
    keys; we mirror the *behavior* (greedy longest-match, output is a
    list of consecutive chunks covering the whole input) using a plain
    sliding window. The end result is identical for any GSUB cluster
    pattern PDFBox emits.
    """
    if not glyph_ids:
        return []
    if not substitution_keys:
        return [[g] for g in glyph_ids]

    max_len = max(len(k) for k in substitution_keys)
    out: list[list[int]] = []
    i = 0
    n = len(glyph_ids)
    while i < n:
        matched = False
        for length in range(min(max_len, n - i), 0, -1):
            key = tuple(glyph_ids[i : i + length])
            if key in substitution_keys:
                out.append(list(key))
                i += length
                matched = True
                break
        if not matched:
            out.append([glyph_ids[i]])
            i += 1
    return out


def _apply_gsub_feature(
    feature: _ScriptFeatureLike,
    original_glyphs: list[int],
) -> list[int]:
    """Apply ``feature`` to ``original_glyphs`` via split-then-substitute.

    Mirrors the ``applyGsubFeature`` private method that every upstream
    worker duplicates: empty substitution set → no-op; otherwise split
    into chunks and replace each chunk that the feature can handle.
    """
    keys = feature.get_all_glyph_ids_for_substitution()
    if not keys:
        return original_glyphs
    tokens = _split_into_chunks(original_glyphs, keys)
    out: list[int] = []
    for chunk in tokens:
        if feature.can_replace_glyphs(chunk):
            out.append(feature.get_replacement_for_glyphs(chunk))
        else:
            out.extend(chunk)
    return out


def _iterable_to_list(seq: Iterable[int]) -> list[int]:
    """Materialize ``seq`` as a list (defensive copy)."""
    return list(seq)


__all__ = ["GsubWorker"]
