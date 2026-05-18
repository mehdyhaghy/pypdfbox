from __future__ import annotations

from collections.abc import Iterable
from functools import cmp_to_key

from .compound_character_tokenizer import (
    GLYPH_ID_SEPARATOR,
    CompoundCharacterTokenizer,
)
from .glyph_array_splitter import GlyphArraySplitter


class GlyphArraySplitterRegexImpl(GlyphArraySplitter):
    """Regex-driven :class:`GlyphArraySplitter` implementation.

    Mirrors ``org.apache.fontbox.ttf.gsub.GlyphArraySplitterRegexImpl``
    from upstream Apache PDFBox 3.0.x. Glyph id sequences are
    serialised to underscore-framed strings (``_84_93_``), the
    matchers are fed to a :class:`CompoundCharacterTokenizer`, the
    input glyph run is serialised the same way, tokenized, and each
    token is parsed back into a list of integers.

    The implementation is the "in-efficient implementation based on
    regex" upstream advertises — kept here for parity rather than
    performance.
    """

    def __init__(self, matchers: Iterable[list[int]]) -> None:
        self._compound_character_tokenizer = CompoundCharacterTokenizer(
            self.get_matchers_as_strings(matchers)
        )

    def split(self, glyph_ids: list[int]) -> list[list[int]]:
        original_glyphs_as_text = self.convert_glyph_ids_to_string(glyph_ids)
        tokens = self._compound_character_tokenizer.tokenize(original_glyphs_as_text)
        return [self.convert_glyph_ids_to_list(token) for token in tokens]

    @classmethod
    def get_matchers_as_strings(cls, matchers: Iterable[list[int]]) -> list[str]:
        """Order matchers by descending length, ties by reverse-alpha.

        Mirrors upstream's ``TreeSet`` comparator: ``s2.length() -
        s1.length()`` first, ``s2.compareTo(s1)`` on length tie.
        Returning a *list* rather than a set is intentional — Python
        sets aren't ordered, and the
        :class:`CompoundCharacterTokenizer` builds the alternation
        regex in iteration order so duplicates have already collapsed
        by the time we serialise (the dedup goes through the
        intermediate ``dict`` lookup in :func:`sorted`).
        """
        seen: dict[str, None] = {}
        for ids in matchers:
            seen.setdefault(cls.convert_glyph_ids_to_string(ids), None)

        def compare(s1: str, s2: str) -> int:
            if len(s1) == len(s2):
                # ``s2.compareTo(s1)`` — Java's String.compareTo is a
                # codepoint-wise comparison; Python's tuple ordering
                # over the strings reproduces it for the ASCII glyph
                # id strings we're working with.
                if s2 == s1:  # pragma: no cover - dedup'd before sort
                    return 0
                return -1 if s2 < s1 else 1
            return len(s2) - len(s1)

        return sorted(seen.keys(), key=cmp_to_key(compare))

    @staticmethod
    def convert_glyph_ids_to_string(glyph_ids: Iterable[int]) -> str:
        """Serialise ``glyph_ids`` as ``"_a_b_c_"`` — matches upstream."""
        parts = [GLYPH_ID_SEPARATOR]
        for glyph_id in glyph_ids:
            parts.append(str(glyph_id))
            parts.append(GLYPH_ID_SEPARATOR)
        return "".join(parts)

    @staticmethod
    def convert_glyph_ids_to_list(glyph_ids_as_string: str) -> list[int]:
        """Parse ``"_a_b_c_"`` (or any subset) back into ``[a, b, c]``.

        Mirrors upstream's behavior of skipping empty fragments after
        ``split("_")`` and trimming whitespace; the tokenizer is
        documented to sometimes drop the leading or trailing ``"_"``,
        so we are tolerant of either.
        """
        result: list[int] = []
        for raw in glyph_ids_as_string.split(GLYPH_ID_SEPARATOR):
            stripped = raw.strip()
            if not stripped:
                continue
            result.append(int(stripped))
        return result


__all__ = ["GlyphArraySplitterRegexImpl"]
