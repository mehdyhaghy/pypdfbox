"""Port of ``PrintTextLocations`` (upstream ``PrintTextLocations.java``
lines 37-100).

Custom :class:`PDFTextStripper` that emits each ``TextPosition``'s
coordinates and styling to stdout.
"""

from __future__ import annotations

import io
import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper


class PrintTextLocations(PDFTextStripper):
    """Mirrors ``PrintTextLocations`` (public, default ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    PrintTextLocations.java`` (lines 37-100).
    """

    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 55)."""
        argv = list(argv) if argv else []
        if len(argv) != 1:
            PrintTextLocations.usage()
            return
        PrintTextLocations.run(argv[0])

    @staticmethod
    def run(filename: str) -> None:
        """Stream text-position diagnostics for ``filename``. Promoted
        from the upstream inline ``main`` body."""
        with PDDocument.load(filename) as document:
            stripper = PrintTextLocations()
            stripper.set_sort_by_position(True)
            stripper.set_start_page(1)
            stripper.set_end_page(document.get_number_of_pages())
            dummy = io.StringIO()
            stripper.write_text(document, dummy)

    def write_string(self, string: str, text_positions: list) -> None:
        """Override called per-line of extracted text — mirrors the Java
        ``writeString(String, List<TextPosition>)`` (line 80)."""
        for text in text_positions:
            try:
                font_name = text.get_font().get_name()
            except Exception:  # noqa: BLE001
                font_name = "<unknown>"
            sys.stdout.write(
                f"String[{getattr(text, 'get_x_dir_adj', lambda: 0)()},"
                f"{getattr(text, 'get_y_dir_adj', lambda: 0)()} "
                f"font={font_name}:{getattr(text, 'get_font_size', lambda: 0)()} "
                f"xscale={getattr(text, 'get_x_scale', lambda: 0)()} "
                f"height={getattr(text, 'get_height_dir', lambda: 0)()} "
                f"space={getattr(text, 'get_width_of_space', lambda: 0)()} "
                f"width={getattr(text, 'get_width_dir_adj', lambda: 0)()}]"
                f"{getattr(text, 'get_unicode', lambda: '')()}\n",
            )

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 97)."""
        sys.stderr.write("Usage: PrintTextLocations <input-pdf>\n")


if __name__ == "__main__":  # pragma: no cover
    PrintTextLocations.main(sys.argv[1:])
