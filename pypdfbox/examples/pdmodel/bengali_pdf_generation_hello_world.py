"""Port of ``org.apache.pdfbox.examples.pdmodel.BengaliPdfGenerationHelloWorld`` (lines 44-206).

Lays out a Bengali Lohit-font text sample across one or more A4 pages.
"""

from __future__ import annotations

import sys


class BengaliPdfGenerationHelloWorld:
    """Mirrors ``BengaliPdfGenerationHelloWorld`` (line 44)."""

    LINE_GAP: int = 5
    LOHIT_BENGALI_TTF: str = "/org/apache/pdfbox/resources/ttf/Lohit-Bengali.ttf"
    TEXT_SOURCE_FILE: str = "/org/apache/pdfbox/resources/ttf/bengali-samples.txt"
    FONT_SIZE: int = 20
    MARGIN: int = 20

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 56)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            sys.stderr.write(
                "usage: BengaliPdfGenerationHelloWorld <output-file>\n",
            )
            raise SystemExit(1)
        # TODO: the example bundles a Lohit-Bengali TTF resource and a text
        # corpus that live in the upstream pdfbox jar. A faithful port needs
        # the resource-stream lookup and complex Indic shaping pipeline.
        raise NotImplementedError(
            "BengaliPdfGenerationHelloWorld awaits Lohit-Bengali resource "
            "wiring and Indic shaping.",
        )

    @staticmethod
    def get_page_size() -> object:
        """Mirrors ``getPageSize()`` (line 175)."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle
        return PDRectangle.A4

    @staticmethod
    def get_re_aligned_text_based_on_page_height(
        original_lines: list[str],
        font: object,
        workable_page_height: float,
    ) -> list[list[str]]:
        """Mirrors ``getReAlignedTextBasedOnPageHeight`` (line 110)."""
        del original_lines, font, workable_page_height
        raise NotImplementedError(
            "Bengali shaping is gated on the Lohit resource bundle.",
        )

    @staticmethod
    def get_re_aligned_text_based_on_page_width(
        original_lines: list[str],
        font: object,
        workable_page_width: float,
    ) -> list[str]:
        """Mirrors ``getReAlignedTextBasedOnPageWidth`` (line 137)."""
        del original_lines, font, workable_page_width
        raise NotImplementedError(
            "Bengali shaping is gated on the Lohit resource bundle.",
        )

    @staticmethod
    def get_bengali_text_from_file() -> list[str]:
        """Mirrors ``getBengaliTextFromFile()`` (line 180)."""
        raise NotImplementedError(
            "Bengali shaping is gated on the Lohit resource bundle.",
        )
