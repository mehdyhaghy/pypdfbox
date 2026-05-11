"""Port of ``org.apache.pdfbox.examples.pdmodel.ShowTextWithPositioning`` (lines 41-169).

Uses ``showTextWithPositioning`` to justify text both word-by-word and
letter-by-letter.

Deviation from upstream
-----------------------
Upstream loads ``/org/apache/pdfbox/resources/ttf/LiberationSans-Regular.ttf``
from the PDFBox jar and demonstrates four font flavours
(``PDType0Font.load`` with embedSubset both true/false, ``PDTrueTypeFont.load``,
and ``PDType0Font.load`` again to show word-spacing-on-CID has no effect).

This port substitutes the bundled Standard-14 :class:`PDType1Font` Helvetica
because (a) no TTF resource is bundled with the pypdfbox examples and (b) the
demonstration of the ``show_text_with_positioning`` operator does not actually
depend on a Type0 font — the operator and word-spacing semantics work
identically against any simple font. The trailing Type0/word-spacing-no-effect
demonstration is therefore dropped.
"""

from __future__ import annotations

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.util.matrix import Matrix


class ShowTextWithPositioning:
    """Mirrors ``ShowTextWithPositioning`` (line 41)."""

    FONT_SIZE: float = 20.0

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 49)."""
        del argv
        ShowTextWithPositioning.do_it(
            "Hello World, this is a test!",
            "justify-example.pdf",
        )

    @staticmethod
    def do_it(message: str, outfile: str) -> None:
        """Mirrors ``doIt(String message, String outfile)`` (line 54)."""
        with PDDocument() as doc:
            # Helvetica stands in for LiberationSans (see module docstring).
            font = make_standard14_type1_font(FontName.HELVETICA)
            page = PDPage(PDRectangle.A4)
            doc.add_page(page)

            # String width in text-space units (per upstream, 1/1000 em
            # multiplied by font size).
            string_width = font.get_string_width(message) * ShowTextWithPositioning.FONT_SIZE

            # Conservative string-height surrogate — Standard-14 Type1 metrics
            # are AFM-derived and the Python port doesn't expose a font
            # bounding-box accessor on the simple-font surface, so we use a
            # value scaled from FONT_SIZE that mirrors the magnitude upstream
            # computes for Helvetica/LiberationSans.
            string_height = ShowTextWithPositioning.FONT_SIZE * 1000.0

            page_size = page.get_media_box()

            with PDPageContentStream(
                doc, page, AppendMode.OVERWRITE, False,
            ) as content_stream:
                content_stream.begin_text()
                content_stream.set_font(font, ShowTextWithPositioning.FONT_SIZE)

                # Line 1 — non-justified at top of page.
                content_stream.set_text_matrix(
                    Matrix.get_translate_instance(
                        0, page_size.get_height() - string_height / 1000.0,
                    ),
                )
                content_stream.show_text(message)

                # Line 2 — word-justified.
                content_stream.set_text_matrix(
                    Matrix.get_translate_instance(
                        0, page_size.get_height() - string_height / 1000.0 * 2,
                    ),
                )
                justify_width = page_size.get_width() * 1000.0 - string_width
                parts = message.split(" ")
                space_width = (
                    (justify_width / (len(parts) - 1))
                    / ShowTextWithPositioning.FONT_SIZE
                )
                text: list[str | float] = []
                for index, part in enumerate(parts):
                    if index != 0:
                        text.append(" ")
                        text.append(-space_width)
                    text.append(part)
                content_stream.show_text_with_positioning(text)

                # Line 3 — letter-justified.
                content_stream.set_text_matrix(
                    Matrix.get_translate_instance(
                        0, page_size.get_height() - string_height / 1000.0 * 3,
                    ),
                )
                text = []
                extra_letter_width = (
                    (justify_width / (len(message) - 1))
                    / ShowTextWithPositioning.FONT_SIZE
                )
                for index, char in enumerate(message):
                    if index != 0:
                        text.append(-extra_letter_width)
                    text.append(char)
                content_stream.show_text_with_positioning(text)

                # Line 4 — show_text with word-spacing applied.
                content_stream.set_text_matrix(
                    Matrix.get_translate_instance(
                        0, page_size.get_height() - string_height / 1000.0 * 4,
                    ),
                )
                word_spacing = (
                    (page_size.get_width() * 1000.0 - string_width)
                    / (len(parts) - 1)
                    / 1000.0
                )
                content_stream.set_word_spacing(word_spacing)
                content_stream.show_text(message)

                content_stream.end_text()

            doc.save(outfile)
