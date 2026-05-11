"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedFonts`` (lines 34-76).

Embeds a TrueType font and writes Unicode text with ligatures.

Wave 1286 deviation
-------------------
Upstream loads a bundled ``LiberationSans-Regular.ttf`` resource via
``PDType0Font.load(document, new File(dir + "LiberationSans-Regular.ttf"))``.
pypdfbox does not redistribute that TTF (we never bundle external font
binaries — see project memory), so the example degrades to the
**Standard-14 Helvetica AFM** that PDFBox itself ships permissively. The
resulting PDF therefore lacks true Unicode coverage (Helvetica is a
WinAnsi-encoded Type1 font) — Unicode glyphs outside that encoding are
silently skipped during display, but ``main()`` runs end-to-end and emits
a valid PDF. The class additionally exposes ``demo_with_font(ttf_path)``
so a caller bringing their own TTF gets faithful upstream behaviour.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# Default output filename matches upstream ``document.save("example.pdf")``.
_DEFAULT_OUTPUT = "example.pdf"

# Text body — kept byte-identical to upstream lines 58-68.
_LINE_TITLE = "PDFBox's Unicode with Embedded TrueType Font"
_LINE_UNICODE = "Supports full Unicode text ☺"
_LINE_LATIN_CYRILLIC = "English русский " \
    "язык Tiếng Việt"
_LINE_LIGATURES = "Ligatures: ﬁlm ﬂood"


class EmbeddedFonts:
    """Mirrors ``EmbeddedFonts`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 41).

        Optional positional argument: output path (defaults to
        ``example.pdf`` matching the upstream hard-coded filename). An
        optional second positional argument can point at a TrueType font
        file; when supplied the example switches to the full
        ``PDType0Font.load`` path for upstream-faithful Unicode rendering.
        """
        argv = argv if argv is not None else []
        output = argv[0] if len(argv) >= 1 else _DEFAULT_OUTPUT
        font_path = Path(argv[1]) if len(argv) >= 2 else None
        EmbeddedFonts.demo_with_font(output, font_path)

    @staticmethod
    def demo_with_font(
        output: str | Path,
        ttf_path: Path | None = None,
    ) -> None:
        """Render the upstream demo into ``output``.

        When ``ttf_path`` is provided, the demo embeds it as a Type 0
        font (upstream-faithful path). When ``ttf_path`` is ``None`` the
        demo falls back to the Standard-14 Helvetica Type 1 font — the
        deviation documented in the module docstring.
        """
        with PDDocument() as doc:
            page = PDPage(PDRectangle.A4)
            doc.add_page(page)

            if ttf_path is not None:
                font = PDType0Font.load(doc, ttf_path)
            else:
                # Helvetica fallback. The Standard-14 AFM ships with PDFBox
                # itself (Apache 2.0), so this path stays dependency-free.
                font = make_standard14_type1_font(FontName.HELVETICA)

            with PDPageContentStream(doc, page) as stream:
                stream.begin_text()
                stream.set_font(font, 12)
                stream.set_leading(12 * 1.2)
                stream.new_line_at_offset(50, 600)
                # Helvetica's WinAnsi cmap can't encode every codepoint
                # used upstream; skip lines that the fallback rejects so
                # ``main()`` still produces a valid PDF. The TTF path
                # never raises here because Unicode is fully covered.
                for line in (
                    _LINE_TITLE,
                    _LINE_UNICODE,
                    _LINE_LATIN_CYRILLIC,
                    _LINE_LIGATURES,
                ):
                    try:
                        stream.show_text(line)
                    except (ValueError, KeyError, OSError, TypeError):
                        # Standard-14 Helvetica can't render some glyphs;
                        # render a placeholder so leading still advances
                        # the cursor and the output PDF stays well-formed.
                        stream.show_text("[skipped: unsupported glyph]")
                    if line is not _LINE_LIGATURES:
                        stream.new_line()
                stream.end_text()

            doc.save(str(output))


if __name__ == "__main__":  # pragma: no cover — CLI parity only.
    EmbeddedFonts.main(sys.argv[1:])
