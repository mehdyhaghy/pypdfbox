"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedMultipleFonts`` (lines 44-164).

Renders multi-script text by falling back through a font list.
"""

from __future__ import annotations

from typing import Any


class EmbeddedMultipleFonts:
    """Mirrors ``EmbeddedMultipleFonts`` (line 44)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 50)."""
        del argv
        # TODO: assumes Windows font collections (batang.ttc, mingliu.ttc,
        # mangal.ttf, ArialUni.ttf) — not portable. Structural stub.
        raise NotImplementedError(
            "EmbeddedMultipleFonts depends on Windows TTC fonts not bundled.",
        )

    @staticmethod
    def show_text_multiple(
        cs: Any,
        text: str,
        fonts: list[Any],
        size: float,
    ) -> None:
        """Mirrors ``showTextMultiple`` (line 83)."""
        del cs, text, fonts, size
        raise NotImplementedError(
            "EmbeddedMultipleFonts.show_text_multiple awaits font.encode "
            "exposure on the public surface.",
        )

    @staticmethod
    def is_win_ansi_encoding(unicode: int) -> bool:
        """Mirrors ``isWinAnsiEncoding(int unicode)`` (line 155)."""
        from pypdfbox.pdmodel.font.encoding.glyph_list import GlyphList
        from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import (
            WinAnsiEncoding,
        )

        name = GlyphList.get_adobe_glyph_list().code_point_to_name(unicode)
        if name == ".notdef":
            return False
        return WinAnsiEncoding.INSTANCE.contains(name)
