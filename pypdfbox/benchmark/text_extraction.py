"""Text-extraction benchmarks.

Ported from
``benchmark/src/main/java/org/apache/pdfbox/benchmark/TextExtraction.java``
(lines 32-65). The Java suite drives :class:`PDFTextStripper` with and
without position-based sorting; the port follows the same shape and
returns elapsed milliseconds rather than relying on JMH.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pypdfbox.loader import Loader
from pypdfbox.text.pdf_text_stripper import PDFTextStripper


class TextExtraction:
    """Suite of text-extraction micro-benchmarks."""

    PDF32000_2008 = "target/pdfs/PDF32000_2008.pdf"

    def __init__(self) -> None:
        logging.getLogger("org.apache").setLevel(logging.CRITICAL)
        self._sink: Any = None

    def _consume(self, value: Any) -> None:
        self._sink = value

    @staticmethod
    def _time_call(callable_: Any) -> float:
        start = time.perf_counter()
        callable_()
        return (time.perf_counter() - start) * 1000.0

    def extract_pdf_spec_unsorted(self) -> float:
        """Mirror of ``extractPDFSpecUnsorted`` (line 46)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.PDF32000_2008)
            try:
                stripper = PDFTextStripper()
                stripper.set_sort_by_position(False)
                parsed = stripper.get_text(pdf)
                self._consume(parsed)
            finally:
                pdf.close()

        return self._time_call(_body)

    def extract_pdf_spec_sorted(self) -> float:
        """Mirror of ``extractPDFSpecSorted`` (line 58)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.PDF32000_2008)
            try:
                stripper = PDFTextStripper()
                stripper.set_sort_by_position(True)
                parsed = stripper.get_text(pdf)
                self._consume(parsed)
            finally:
                pdf.close()

        return self._time_call(_body)
