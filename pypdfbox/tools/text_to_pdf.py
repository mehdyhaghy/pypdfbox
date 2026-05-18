"""``TextToPDF`` class port — wraps a text file into a PDF document.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/TextToPDF.java
    (lines 51-574)

The inner ``PageSizes`` enum is ported as a module-level enum.
"""
from __future__ import annotations

import argparse
import enum
import sys
from pathlib import Path
from typing import IO

from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName, Standard14Fonts
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

FONTSCALE = 1000
DEFAULT_FONT_SIZE = 10.0
DEFAULT_LINE_HEIGHT_FACTOR = 1.05
DEFAULT_MARGIN = 40.0


def _font_bbox_height(font: PDFont) -> float:
    """Return the font's bounding-box height in font units (1/1000 em).

    Standard 14 ``PDType1Font`` instances built by
    :func:`PDFontFactory.create_default_font` are not seeded with a
    parsed ``/FontDescriptor``, so ``font.get_bounding_box()`` returns
    ``None``. Pull the height directly from the bundled AFM metrics in
    that case; otherwise read the descriptor's bounding box; finally
    fall back to ``1000`` (one em).
    """
    name = font.get_name()
    if name is not None and Standard14Fonts.contains_name(name):
        bbox = Standard14Fonts.get_font_descriptor(name)["FontBBox"]
        return float(bbox[3]) - float(bbox[1])
    descriptor = font.get_font_descriptor()
    if descriptor is not None:
        rect = descriptor.get_font_bounding_box()
        if rect is not None:
            return rect.get_height()
    return 1000.0


class PageSizes(enum.Enum):
    """Mirror of inner ``TextToPDF.PageSizes`` (TextToPDF.java:116)."""

    LETTER = PDRectangle.LETTER
    LEGAL = PDRectangle.LEGAL
    A0 = PDRectangle.A0
    A1 = PDRectangle.A1
    A2 = PDRectangle.A2
    A3 = PDRectangle.A3
    A4 = PDRectangle.A4
    A5 = PDRectangle.A5
    A6 = PDRectangle.A6

    def get_page_size(self) -> PDRectangle:
        return self.value


class TextToPDF:
    def __init__(self) -> None:
        self.media_box: PDRectangle = PDRectangle.LETTER
        self.font = None  # PDFont | None
        self.font_size: float = DEFAULT_FONT_SIZE
        self.line_spacing: float = DEFAULT_LINE_HEIGHT_FACTOR
        self.landscape: bool = False
        self.page_size: PageSizes = PageSizes.LETTER
        self.charset: str = "utf-8"
        self.margins: list[float] = [DEFAULT_MARGIN] * 4
        self.standard_font: FontName = FontName.HELVETICA
        self.ttf: Path | None = None
        self.infile: Path | None = None
        self.outfile: Path | None = None
        self.left_margin: float = DEFAULT_MARGIN
        self.right_margin: float = DEFAULT_MARGIN
        self.top_margin: float = DEFAULT_MARGIN
        self.bottom_margin: float = DEFAULT_MARGIN

    # --- accessors (mirror upstream public API) -----------------------
    def get_font(self):
        return self.font

    def set_font(self, font) -> None:
        self.font = font

    def get_font_size(self) -> int:
        return int(self.font_size)

    def set_font_size(self, font_size: float | int) -> None:
        self.font_size = float(font_size)

    def get_line_spacing(self) -> float:
        return self.line_spacing

    def set_line_spacing(self, line_spacing: float) -> None:
        if line_spacing <= 0:
            raise ValueError(f"line spacing must be positive: {line_spacing}")
        self.line_spacing = line_spacing

    def get_left_margin(self) -> float:
        return self.left_margin

    def set_left_margin(self, m: float) -> None:
        self.left_margin = m

    def get_right_margin(self) -> float:
        return self.right_margin

    def set_right_margin(self, m: float) -> None:
        self.right_margin = m

    def get_top_margin(self) -> float:
        return self.top_margin

    def set_top_margin(self, m: float) -> None:
        self.top_margin = m

    def get_bottom_margin(self) -> float:
        return self.bottom_margin

    def set_bottom_margin(self, m: float) -> None:
        self.bottom_margin = m

    def get_media_box(self) -> PDRectangle:
        return self.media_box

    def set_media_box(self, media_box: PDRectangle) -> None:
        self.media_box = media_box

    def is_landscape(self) -> bool:
        return self.landscape

    def set_landscape(self, landscape: bool) -> None:
        self.landscape = landscape

    # --- core API -----------------------------------------------------
    def create_pdf_from_text(self, text_or_doc, text_reader: IO[str] | None = None):
        """Mirror of upstream overloads. Two-argument form (doc + reader)
        and single-argument form (reader only)."""
        if isinstance(text_or_doc, PDDocument):
            self._create_pdf_from_text(text_or_doc, text_reader)
            return None
        # single-arg overload
        doc = PDDocument()
        self._create_pdf_from_text(doc, text_or_doc)
        return doc

    def _create_pdf_from_text(self, doc: PDDocument, text_reader) -> None:  # noqa: ANN001
        if self.font is None:
            self.font = PDFontFactory.create_default_font(self.standard_font.value)
        font_height = _font_bbox_height(self.font) / FONTSCALE
        actual_media_box = (
            PDRectangle(self.media_box.get_height(), self.media_box.get_width())
            if self.landscape else self.media_box
        )
        line_height = font_height * self.font_size * self.line_spacing
        content = text_reader.read() if hasattr(text_reader, "read") else str(text_reader)
        text_is_empty = True
        page = PDPage(actual_media_box)
        content_stream: PDPageContentStream | None = None
        y = -1.0
        max_string_length = page.get_media_box().get_width() - self.left_margin - self.right_margin
        # Split on newline only, NOT ``str.splitlines`` — the latter also
        # treats ``\f`` (form feed) as a line break and would swallow the
        # token that the form-feed handling below relies on.
        for next_line in content.split("\n") if content else [""]:
            text_is_empty = False
            line_words = next_line.split(" ")
            line_index = 0
            while line_index < len(line_words):
                next_line_to_draw: list[str] = []
                add_space = False
                length_if_using_next_word = 0.0
                ff = False
                while True:
                    word = line_words[line_index]
                    index_ff = word.find("\f")
                    if index_ff == -1:
                        word1, word2 = word, ""
                    else:
                        ff = True
                        word1 = word[:index_ff]
                        word2 = word[index_ff + 1:]
                    if len(word1) > 0 or not ff:
                        if add_space:
                            next_line_to_draw.append(" ")
                        else:
                            add_space = True
                        next_line_to_draw.append(word1)
                    if not ff or len(word2) == 0:
                        line_index += 1
                    else:
                        line_words[line_index] = word2
                    if ff:
                        break
                    if line_index < len(line_words):
                        next_word = line_words[line_index]
                        idx = next_word.find("\f")
                        if idx != -1:
                            next_word = next_word[:idx]
                        line_with_next = "".join(next_line_to_draw) + " " + next_word
                        length_if_using_next_word = (
                            self.font.get_string_width(line_with_next) / FONTSCALE
                        ) * self.font_size
                    more_words = line_index < len(line_words)
                    fits = length_if_using_next_word < max_string_length
                    if not (more_words and fits):
                        break
                if y - line_height < self.bottom_margin:
                    page = PDPage(actual_media_box)
                    doc.add_page(page)
                    if content_stream is not None:
                        content_stream.end_text()
                        content_stream.close()
                    content_stream = PDPageContentStream(doc, page)
                    content_stream.set_font(self.font, self.font_size)
                    content_stream.begin_text()
                    y = page.get_media_box().get_height() - self.top_margin
                    y += line_height - font_height * self.font_size
                    content_stream.new_line_at_offset(self.left_margin, y)
                if content_stream is None:
                    raise OSError("Error:Expected non-null content stream.")
                content_stream.new_line_at_offset(0, -line_height)
                y -= line_height
                content_stream.show_text("".join(next_line_to_draw))
                if ff:
                    page = PDPage(actual_media_box)
                    doc.add_page(page)
                    content_stream.end_text()
                    content_stream.close()
                    content_stream = PDPageContentStream(doc, page)
                    content_stream.set_font(self.font, self.font_size)
                    content_stream.begin_text()
                    y = page.get_media_box().get_height() - self.top_margin
                    y += line_height - font_height * self.font_size
                    content_stream.new_line_at_offset(self.left_margin, y)
        # pragma below: unreachable — ``[""]`` fallback iterates once and clears the flag.
        if text_is_empty:  # pragma: no cover
            doc.add_page(page)
        if content_stream is not None:
            content_stream.end_text()
            content_stream.close()

    # --- entry points ---------------------------------------------------
    def call(self) -> int:
        if self.infile is None or self.outfile is None:
            raise OSError("infile and outfile are required")
        try:
            with PDDocument() as doc:
                if self.ttf is not None:
                    self.font = PDType0Font.load(doc, str(self.ttf))
                else:
                    self.font = PDFontFactory.create_default_font(self.standard_font.value)
                self.set_font(self.font)
                self.set_font_size(self.font_size)
                self.set_media_box(self.page_size.get_page_size())
                self.set_landscape(self.landscape)
                self.set_line_spacing(self.line_spacing)
                self.set_left_margin(self.margins[0])
                self.set_right_margin(self.margins[1])
                self.set_top_margin(self.margins[2])
                self.set_bottom_margin(self.margins[3])
                with open(self.infile, encoding=self.charset) as f:
                    self.create_pdf_from_text(doc, f)
                doc.save(self.outfile)
        except OSError as ioe:
            sys.stderr.write(
                f"Error converting text to PDF [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="texttopdf", description="Creates a PDF document from text",
        )
        parser.add_argument("-fontSize", dest="fontSize", type=float, default=DEFAULT_FONT_SIZE)
        parser.add_argument(
            "-lineSpacing", dest="lineSpacing", type=float,
            default=DEFAULT_LINE_HEIGHT_FACTOR,
        )
        parser.add_argument("-landscape", action="store_true")
        parser.add_argument("-pageSize", dest="pageSize", default="LETTER")
        parser.add_argument("-charset", default="utf-8")
        parser.add_argument(
            "-margins", nargs=4, type=float,
            default=[DEFAULT_MARGIN] * 4,
        )
        parser.add_argument("-standardFont", dest="standardFont", default="HELVETICA")
        parser.add_argument("-ttf", default=None)
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", required=True)
        ns = parser.parse_args(args)
        runner = TextToPDF()
        runner.font_size = ns.fontSize
        runner.line_spacing = ns.lineSpacing
        runner.landscape = ns.landscape
        runner.page_size = PageSizes[ns.pageSize]
        runner.charset = ns.charset
        runner.margins = list(ns.margins)
        runner.standard_font = FontName[ns.standardFont]
        runner.ttf = Path(ns.ttf) if ns.ttf else None
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile)
        return runner.call()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(TextToPDF.main(sys.argv[1:]))
