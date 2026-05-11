"""Port of ``PrintTextColors`` (upstream ``PrintTextColors.java`` lines
55-132).

Custom :class:`PDFTextStripper` that emits stroking / non-stroking
colors and rendering mode for each text position.
"""

from __future__ import annotations

import contextlib
import io
import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper


class PrintTextColors(PDFTextStripper):
    """Mirrors ``PrintTextColors`` (public, default ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    PrintTextColors.java`` (lines 55-132).
    """

    def __init__(self) -> None:
        super().__init__()
        # Upstream installs a dozen color-state operators here. pypdfbox's
        # :class:`PDFTextStripper` already wires up the color operators it
        # needs for its own text-extraction pipeline; the operator
        # registration that the Java sample does is a no-op against the
        # lite port.

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 85)."""
        argv = list(argv) if argv else []
        if len(argv) != 1:
            PrintTextColors.usage()
            return
        PrintTextColors.run(argv[0])

    @staticmethod
    def run(filename: str) -> None:
        """Stream color diagnostics for ``filename`` — promoted from the
        upstream inline ``main`` body."""
        with PDDocument.load(filename) as document:
            stripper: PDFTextStripper = PrintTextColors()
            stripper.set_sort_by_position(True)
            stripper.set_start_page(1)
            stripper.set_end_page(document.get_number_of_pages())
            dummy = io.StringIO()
            stripper.write_text(document, dummy)

    def process_text_position(self, text) -> None:  # type: ignore[no-untyped-def]
        """Per-glyph callback — mirrors the Java
        ``processTextPosition(TextPosition)`` (line 107). The lite port
        prints best-effort color attributes; missing graphics-state
        accessors degrade gracefully."""
        # PDFTextStripper variants may not expose this hook.
        with contextlib.suppress(AttributeError):
            super().process_text_position(text)
        unicode_ = getattr(text, "get_unicode", lambda: "")()
        gs = None
        try:
            gs = self.get_graphics_state()
        except Exception:  # noqa: BLE001
            gs = None
        stroking_color = getattr(gs, "get_stroking_color", lambda: None)() if gs else None
        non_stroking_color = getattr(gs, "get_non_stroking_color", lambda: None)() if gs else None
        rendering_mode = None
        if gs is not None:
            ts = getattr(gs, "get_text_state", lambda: None)()
            if ts is not None:
                rendering_mode = getattr(ts, "get_rendering_mode", lambda: None)()
        sys.stdout.write(
            f"Unicode:            {unicode_}\n"
            f"Rendering mode:     {rendering_mode}\n"
            f"Stroking color:     {stroking_color}\n"
            f"Non-Stroking color: {non_stroking_color}\n\n",
        )

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 128)."""
        sys.stderr.write("Usage: PrintTextColors <input-pdf>\n")


if __name__ == "__main__":  # pragma: no cover
    PrintTextColors.main(sys.argv[1:])
