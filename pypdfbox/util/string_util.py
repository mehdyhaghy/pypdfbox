"""String split helpers used by ``Hex`` and friends.

Mirrors ``org.apache.pdfbox.util.StringUtil`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/StringUtil.java``).
"""

from __future__ import annotations

import re

PATTERN_SPACE = re.compile(r"\s")


class StringUtil:
    """Static-only helpers."""

    PATTERN_SPACE = PATTERN_SPACE

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("StringUtil is a utility class")

    @staticmethod
    def split_on_space(s: str) -> list[str]:
        """Split on Java ``\\s`` (whitespace)."""
        return PATTERN_SPACE.split(s)

    @staticmethod
    def tokenize_on_space(s: str) -> list[str]:
        """Split at whitespace boundaries while keeping the separators."""
        if not s:
            return [s] if s == "" else []
        # Match the upstream lookaround behaviour: a token boundary lives
        # either before or after a whitespace char, so each run of spaces
        # becomes its own token.
        return re.split(r"(?<=\s)|(?=\s)", s)


__all__ = ["StringUtil", "PATTERN_SPACE"]
