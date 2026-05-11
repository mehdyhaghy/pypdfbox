"""Port of ``org.apache.pdfbox.examples.pdmodel.BengaliPdfGenerationHelloWorld`` (lines 44-206).

Lays out a Bengali Lohit-font text sample across one or more A4 pages.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _read_bengali_lines(path: Path) -> list[str]:
    """Read ``path`` as UTF-8 and drop lines beginning with ``#``.

    Helper for :func:`BengaliPdfGenerationHelloWorld.get_bengali_text_from_file`
    — mirrors the upstream comment filter (L196-199).
    """
    lines: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if line.startswith("#"):
                continue
            lines.append(line)
    return lines


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
        """Mirrors ``getBengaliTextFromFile()`` (line 180).

        Upstream reads the resource from the classpath
        (``/org/apache/pdfbox/resources/ttf/bengali-samples.txt``). The
        pypdfbox port does not bundle the upstream resource jar — we look up
        the file via ``importlib.resources`` against
        ``pypdfbox.examples.pdmodel.resources``, then fall back to
        ``$PYPDFBOX_RESOURCE_DIR`` (if set), and finally to the upstream
        repository path under the Python source tree. Returns an empty list
        when no candidate exists so the caller (``main()``) can short-circuit
        gracefully. Lines beginning with ``#`` are filtered out, mirroring
        upstream L196-199.
        """
        import os

        candidates: list[Path] = []

        # Search-strategy 1: bundled package data.
        try:
            from importlib import resources as _resources

            ref = _resources.files(
                "pypdfbox.examples.pdmodel",
            ).joinpath("resources/ttf/bengali-samples.txt")
            if ref.is_file():
                with _resources.as_file(ref) as path:
                    return _read_bengali_lines(path)
        except (ModuleNotFoundError, FileNotFoundError, AttributeError):
            pass

        # Search-strategy 2: env-var override (pypdfbox extension).
        env_dir = os.environ.get("PYPDFBOX_RESOURCE_DIR")
        if env_dir:
            candidates.append(
                Path(env_dir) / "ttf" / "bengali-samples.txt",
            )

        # Search-strategy 3: walk a few parents looking for a checked-out
        # PDFBox tree (developer convenience for the example).
        here = Path(__file__).resolve()
        for parent in (*here.parents[:6], Path("/tmp/pdfbox")):
            candidates.append(
                parent / "examples" / "src" / "main" / "resources"
                / "org" / "apache" / "pdfbox" / "resources" / "ttf"
                / "bengali-samples.txt",
            )

        for path in candidates:
            if path.is_file():
                return _read_bengali_lines(path)
        return []
