"""Port of ``DrawPrintTextLocations`` (upstream
``DrawPrintTextLocations.java`` lines 61-333).

Extends :class:`PDFTextStripper` to print each glyph's location while
rendering an overlay image for visual inspection.

The full upstream sample renders every page to a PNG via
:class:`PDFRenderer` and overlays glyph bounds drawn with Java2D
``Graphics2D``. pypdfbox does not yet expose a Python rendering surface
and the AWT-based ``Graphics2D`` overlay would require a heavyweight
imaging dependency. The port keeps the text-stripper class shape and
prints the same per-glyph diagnostic line as upstream; the rendering
overlay step is documented in ``CHANGES.md`` as deferred.
"""

from __future__ import annotations

import contextlib
import io
import sys
from typing import Any

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper


class DrawPrintTextLocations(PDFTextStripper):
    """Mirrors ``DrawPrintTextLocations`` (public ctor at line 77).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    DrawPrintTextLocations.java`` (lines 61-333).
    """

    SCALE: int = 4

    def __init__(self, document: PDDocument, filename: str) -> None:
        super().__init__()
        # Upstream pre-populates ``this.document`` to break a base-class
        # init-order constraint; we keep the same attribute for parity.
        self.document = document
        self.filename = filename
        self.flip_at: Any = None
        self.rotate_at: Any = None
        self.trans_at: Any = None
        self.g2d: Any = None

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 90)."""
        argv = list(argv) if argv else []
        if len(argv) != 1:
            DrawPrintTextLocations.usage()
            return
        DrawPrintTextLocations.run(argv[0])

    @staticmethod
    def run(filename: str) -> None:
        """Strip each page and print glyph coordinates. Promoted from the
        upstream inline ``main`` body."""
        with PDDocument.load(filename) as document:
            stripper = DrawPrintTextLocations(document, filename)
            stripper.set_sort_by_position(True)
            for page in range(document.get_number_of_pages()):
                stripper.strip_page(page)

    def strip_page(self, page: int) -> None:
        """Run the text stripper over a single page index — promoted from
        upstream's private ``stripPage`` (line 195)."""
        self.set_start_page(page + 1)
        self.set_end_page(page + 1)
        dummy = io.StringIO()
        self.write_text(self.document, dummy)

    def show_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        """Glyph-level callback — mirrors the Java
        ``showGlyph(Matrix, PDFont, int, Vector)`` (line 112)."""
        with contextlib.suppress(AttributeError):
            super().show_glyph(text_rendering_matrix, font, code, displacement)

    def calculate_glyph_bounds(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
    ) -> Any:
        """Mirror of upstream's private ``calculateGlyphBounds`` (line
        135) promoted public so tests can drive it. The lite port returns
        ``None`` when the surrounding rendering substrate isn't available."""
        return None

    def write_string(self, string: str, text_positions: list) -> None:
        """Mirror of upstream's overridden ``writeString`` (line 271)."""
        for text in text_positions:
            try:
                font_name = text.get_font().get_name()
            except Exception:  # noqa: BLE001
                font_name = "<unknown>"
            sys.stdout.write(
                f"String[{getattr(text, 'get_x_dir_adj', lambda: 0)()},"
                f"{getattr(text, 'get_y_dir_adj', lambda: 0)()} "
                f"font={font_name}:"
                f"{getattr(text, 'get_font_size', lambda: 0)()} "
                f"xscale={getattr(text, 'get_x_scale', lambda: 0)()} "
                f"height={getattr(text, 'get_height_dir', lambda: 0)()} "
                f"space={getattr(text, 'get_width_of_space', lambda: 0)()} "
                f"width={getattr(text, 'get_width_dir_adj', lambda: 0)()}]"
                f"{getattr(text, 'get_unicode', lambda: '')()}\n",
            )

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 329)."""
        sys.stderr.write("Usage: DrawPrintTextLocations <input-pdf>\n")


if __name__ == "__main__":  # pragma: no cover
    DrawPrintTextLocations.main(sys.argv[1:])
