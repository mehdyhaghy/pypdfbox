from __future__ import annotations

from enum import Enum


class Language(Enum):
    """Languages supported for GSUB shaping.

    Mirrors ``org.apache.fontbox.ttf.model.Language`` from upstream
    Apache PDFBox 3.0.x. Each entry carries the ordered list of
    OpenType script tags (4-byte strings such as ``"bng2"``, ``"beng"``)
    that identify the language inside a GSUB ScriptList. Order is
    significant — index 0 is the most preferred script tag.

    ``UNSPECIFIED`` is intentionally last with an empty tuple of script
    names. It is not a language per se; it marks the absence of any
    concrete language match, useful when only the contents of the GSUB
    table are of interest (no actual glyph substitution required).
    """

    BENGALI = ("bng2", "beng")
    DEVANAGARI = ("dev2", "deva")
    GUJARATI = ("gjr2", "gujr")
    LATIN = ("latn",)
    DFLT = ("DFLT",)
    UNSPECIFIED = ()

    def __init__(self, *script_names: str) -> None:
        # ``Enum`` passes each tuple element as a separate positional
        # arg, so ``*script_names`` collects them back into the ordered
        # tuple the Java side exposes via ``getScriptNames()``.
        self._script_names: tuple[str, ...] = script_names

    def get_script_names(self) -> tuple[str, ...]:
        """Return the OpenType script tags this language matches.

        Mirrors upstream ``Language.getScriptNames()``. Index 0 is the
        most preferred tag; callers iterate in order and stop at the
        first match present in the font's ScriptList.
        """
        return self._script_names


__all__ = ["Language"]
