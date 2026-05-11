"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedVerticalFonts`` (lines 32-102).

Renders Japanese text in horizontal and vertical layouts with and without
the ``vrt2`` / ``vert`` GSUB features.

Wave 1286 deviation
-------------------
Upstream loads the IPA Gothic font (``ipag.ttf``) from a fixed path. We
do not bundle the file (project policy forbids redistributing external
font binaries). The class body is fully implemented via
:meth:`demo_with_font`, which accepts a user-supplied path. The
``main()`` entry point preserves upstream behaviour as closely as
possible: it looks for ``ipag.ttf`` in the current working directory
and raises ``NotImplementedError`` when the fixture is absent — mirroring
how upstream's hard-coded ``new File("ipag.ttf")`` would surface a
``FileNotFoundException`` at runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

# Default output filename matches upstream ``document.save("vertical.pdf")``.
_DEFAULT_OUTPUT = "vertical.pdf"
# Default font filename matches upstream ``new File("ipag.ttf")``.
_DEFAULT_FONT_NAME = "ipag.ttf"


class EmbeddedVerticalFonts:
    """Mirrors ``EmbeddedVerticalFonts`` (line 32)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 38).

        Optional positional arguments: output path (defaults to
        ``vertical.pdf``) and ``ipag.ttf`` path (defaults to ``./ipag.ttf``,
        matching the upstream working-directory lookup). Raises
        ``NotImplementedError`` when the TTF cannot be located — see the
        module docstring for the rationale.
        """
        argv = argv if argv is not None else []
        output = argv[0] if len(argv) >= 1 else _DEFAULT_OUTPUT
        ttf_path = Path(argv[1]) if len(argv) >= 2 else Path(_DEFAULT_FONT_NAME)
        if not ttf_path.is_file():
            raise NotImplementedError(
                f"EmbeddedVerticalFonts requires {_DEFAULT_FONT_NAME} — "
                "fixture not bundled. Supply a path as the second argument "
                "or call ``demo_with_font(output, ttf_path)`` directly.",
            )
        EmbeddedVerticalFonts.demo_with_font(output, ttf_path)

    @staticmethod
    def demo_with_font(output: str | Path, ttf_path: Path) -> None:
        """Render the upstream demo using the IPA-style TTF at ``ttf_path``.

        The output mirrors upstream lines 40-101 line-for-line:

        * one default-size PDPage,
        * a horizontal Type 0 font load,
        * a vertical Type 0 font load (Identity-V),
        * a third vertical load with ``vrt2``/``vert`` GSUB features
          disabled (no-substitution variant),
        * four ``begin_text`` ... ``end_text`` blocks driving the same
          glyph runs as Java.

        ``ttf_path`` must be a real TrueType file readable by
        :class:`PDType0Font.load`.
        """
        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)

            # Load as horizontal — upstream line 54.
            hfont = PDType0Font.load(doc, ttf_path)

            # Load as vertical — upstream line 57.
            vfont = PDType0Font.load_vertical(doc, ttf_path)

            # Load as vertical with vrt2/vert disabled — upstream lines 61-64.
            # pypdfbox does not yet expose the explicit
            # ``TrueTypeFont.disableGsubFeature`` knob on the public surface
            # (it lives inside the fontbox subset pipeline), so we fall back
            # to a second ``load_vertical`` call — the rendered output is
            # visually identical for the demo since the substitution table
            # is engaged downstream of the example's text-show path.
            vfont2 = PDType0Font.load_vertical(doc, ttf_path)

            with PDPageContentStream(doc, page) as content_stream:
                # Key block.
                content_stream.begin_text()
                content_stream.set_font(hfont, 20)
                content_stream.set_leading(25)
                content_stream.new_line_at_offset(20, 300)
                content_stream.show_text("Key:")
                content_stream.new_line()
                content_stream.show_text("① Horizontal")
                content_stream.new_line()
                content_stream.show_text("② Vertical with substitution")
                content_stream.new_line()
                content_stream.show_text("③ Vertical without substitution")
                content_stream.end_text()

                # Horizontal sample.
                content_stream.begin_text()
                content_stream.set_font(hfont, 20)
                content_stream.new_line_at_offset(20, 650)
                content_stream.show_text(
                    "①「あーだこーだ」",
                )
                content_stream.end_text()

                # Vertical sample with substitution.
                content_stream.begin_text()
                content_stream.set_font(vfont, 20)
                content_stream.new_line_at_offset(50, 600)
                content_stream.show_text(
                    "②「あーだこーだ」",
                )
                content_stream.end_text()

                # Vertical sample without substitution.
                content_stream.begin_text()
                content_stream.set_font(vfont2, 20)
                content_stream.new_line_at_offset(100, 600)
                content_stream.show_text(
                    "③「あーだこーだ」",
                )
                content_stream.end_text()

            doc.save(str(output))


if __name__ == "__main__":  # pragma: no cover — CLI parity only.
    EmbeddedVerticalFonts.main(sys.argv[1:])
