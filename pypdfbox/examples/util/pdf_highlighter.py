"""Port of ``PDFHighlighter`` (upstream ``PDFHighlighter.java`` lines
44-165).

Generates an Adobe Highlight File Format XML payload for a set of
search words against a PDF.
"""

from __future__ import annotations

import io
import re
import sys
from typing import TextIO

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper


class PDFHighlighter(PDFTextStripper):
    """Mirrors ``PDFHighlighter`` (public, default ctor at line 58).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    PDFHighlighter.java`` (lines 44-165).
    """

    ENCODING: str = "utf-16"

    def __init__(self) -> None:
        super().__init__()
        try:
            self.set_line_separator("")
            self.set_word_separator("")
            self.set_should_separate_by_beads(False)
            self.set_suppress_duplicate_overlapping_text(False)
        except AttributeError:
            # The lite port may not expose every separator toggle yet.
            pass
        self._highlighter_output: TextIO | None = None
        self._searched_words: list[str] = []
        self._text_os: io.StringIO | None = None
        self._text_writer: io.StringIO | None = None

    def generate_xml_highlight(
        self,
        pd_document: PDDocument,
        words: str | list[str],
        xml_output: TextIO,
    ) -> None:
        """Generate Adobe Highlight File Format XML for ``words``.

        Mirrors both upstream overloads (line 75 ``String highlightWord``
        and line 89 ``String[] sWords``) — a single string is normalised
        to a one-element list."""
        if isinstance(words, str):
            words = [words]
        self._highlighter_output = xml_output
        self._searched_words = words
        xml_output.write("<XML>\n<Body units=characters  version=2>\n<Highlight>\n")
        self._text_os = io.StringIO()
        self._text_writer = self._text_os
        try:
            self.write_text(pd_document, self._text_writer)
        finally:
            xml_output.write("</Highlight>\n</Body>\n</XML>")
            xml_output.flush()

    def end_page(self, pd_page) -> None:  # type: ignore[no-untyped-def]
        """Per-page callback — mirrors upstream's ``endPage`` (line 106)."""
        if self._text_os is None or self._highlighter_output is None:
            return
        page = self._text_os.getvalue()
        self._text_os.seek(0)
        self._text_os.truncate(0)
        if "a" in page:
            page = re.sub(r"a\d{1,3}", ".", page)
        for searched_word in self._searched_words:
            for match in re.finditer(searched_word, page, flags=re.IGNORECASE):
                begin = match.start()
                end = match.end()
                page_no = (
                    self.get_current_page_no() - 1
                    if hasattr(self, "get_current_page_no")
                    else 0
                )
                self._highlighter_output.write(
                    f"    <loc pg={page_no} pos={begin} len={end - begin}>\n",
                )

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 142)."""
        argv = list(argv) if argv else []
        if len(argv) < 2:
            PDFHighlighter.usage()
            return
        highlight_strings = list(argv[1:])
        with PDDocument.load(argv[0]) as doc:
            xml_extractor = PDFHighlighter()
            xml_extractor.generate_xml_highlight(
                doc, highlight_strings, sys.stdout,
            )

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 160)."""
        sys.stderr.write(
            "usage: PDFHighlighter <pdf file> word1 word2 word3 ...\n",
        )


if __name__ == "__main__":  # pragma: no cover
    PDFHighlighter.main(sys.argv[1:])
