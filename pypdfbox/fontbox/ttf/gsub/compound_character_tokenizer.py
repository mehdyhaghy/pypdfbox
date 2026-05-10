from __future__ import annotations

import re
from collections.abc import Iterable

GLYPH_ID_SEPARATOR = "_"


class CompoundCharacterTokenizer:
    """Split a glyph-id string into substitutable and non-substitutable chunks.

    Mirrors ``org.apache.fontbox.ttf.gsub.CompoundCharacterTokenizer``
    from upstream Apache PDFBox 3.0.x. The class compiles the set of
    compound-glyph strings (each starting and ending with ``"_"``,
    e.g. ``"_79_99_"``) into a single alternation regex and then walks
    an input string composed in the same format, emitting matched and
    unmatched segments in order.

    It is assumed the compound words are sorted in descending order of
    length so the longest applicable pattern wins; the regex engine
    walks alternatives left-to-right, so caller-side sort order is the
    same priority order upstream expects.
    """

    def __init__(self, compound_words: Iterable[str]) -> None:
        words = list(compound_words)
        self.validate_compound_words(words)
        # ``re.compile`` with alternation matches identical to Java's
        # ``Pattern.compile``; the regex itself is built the same way
        # upstream uses ``StringJoiner(")|(", "(", ")")``.
        self._regex_expression: re.Pattern[str] = re.compile(
            self.get_regex_from_tokens(words)
        )

    @staticmethod
    def validate_compound_words(compound_words: list[str]) -> None:
        """Reject ``None``, empty input, or words missing the ``_`` framing.

        Mirrors upstream ``validateCompoundWords`` — the same two
        invariants (non-empty set, every word framed in ``_``) are
        required for the regex to behave correctly.
        """
        if not compound_words:
            raise ValueError("Compound words cannot be null or empty")
        for word in compound_words:
            if not word.startswith(GLYPH_ID_SEPARATOR) or not word.endswith(
                GLYPH_ID_SEPARATOR
            ):
                raise ValueError(
                    f"Compound words should start and end with {GLYPH_ID_SEPARATOR}"
                )

    @staticmethod
    def get_regex_from_tokens(compound_words: list[str]) -> str:
        """Wrap each word in ``(...)`` and join with ``|`` — matches upstream."""
        return "|".join(f"({word})" for word in compound_words)

    def tokenize(self, text: str) -> list[str]:
        """Return ``text`` split into alternating match / non-match chunks.

        Mirrors upstream ``tokenize`` byte-for-byte:

        * Uses ``re.compile(...).finditer`` driven by an explicit
          cursor so we can rewind one character when a match swallows
          the leading ``"_"`` of the *following* compound word. Java's
          ``Matcher.find(int)`` accepts the start offset directly; the
          equivalent in Python is ``re.Pattern.search(text, pos)`` in
          a manual loop because ``finditer`` doesn't let us nudge the
          cursor between matches.
        * Emits the gap before each match (``prev_token``) unless it
          is empty, then the match itself, then continues. After the
          last match, the trailing tail is appended if non-empty.
        """
        tokens: list[str] = []
        last_index_of_prev_match = 0
        n = len(text)

        while True:
            match = self._regex_expression.search(text, last_index_of_prev_match)
            if match is None:
                break

            begin_index_of_next_match = match.start()
            prev_token = text[last_index_of_prev_match:begin_index_of_next_match]
            if prev_token:
                tokens.append(prev_token)

            tokens.append(match.group())

            last_index_of_prev_match = match.end()
            # The regex consumes the trailing ``_`` of the matched
            # compound, which is also the leading ``_`` of the next
            # one. Rewind by one char so the *next* compound starts
            # at its own ``_`` — matches upstream verbatim.
            if (
                last_index_of_prev_match < n
                and text[last_index_of_prev_match] != GLYPH_ID_SEPARATOR
            ):
                last_index_of_prev_match -= 1

        tail = text[last_index_of_prev_match:]
        if tail:
            tokens.append(tail)

        return tokens


__all__ = ["CompoundCharacterTokenizer"]
