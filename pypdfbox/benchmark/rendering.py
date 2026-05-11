"""Rendering benchmarks.

Ported from
``benchmark/src/main/java/org/apache/pdfbox/benchmark/Rendering.java``
(lines 40-145). Replaces JMH ``@Benchmark`` annotations with plain
methods that return elapsed milliseconds; Pillow saves PNGs in place of
``ImageIO.write``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pypdfbox.loader import Loader
from pypdfbox.rendering.pdf_renderer import PDFRenderer


class Rendering:
    """Suite of rendering micro-benchmarks."""

    ALTONA_TEST_SUITE = (
        "target/pdfs/eci_altona-test-suite-v2_technical2_x4.pdf"
    )
    GHENT_CMYK_X4 = (
        "target/pdfs/Ghent_PDF_Output_Suite_V50_Full/Categories/"
        "1-CMYK/Test pages/Ghent_PDF-Output-Test-V50_CMYK_X4.pdf"
    )
    PDF32000_2008 = "target/pdfs/PDF32000_2008.pdf"
    RENDER_OUTPUT_DIR = "target/renditions"

    def __init__(self) -> None:
        # Lines 47-58: silence logging + create the output dir.
        logging.getLogger("org.apache").setLevel(logging.CRITICAL)
        Path(self.RENDER_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        self._sink: Any = None

    def _consume(self, value: Any) -> None:
        self._sink = value

    @staticmethod
    def _time_call(callable_: Any) -> float:
        start = time.perf_counter()
        callable_()
        return (time.perf_counter() - start) * 1000.0

    def _render_pages(self, path: str, dpi: float, prefix: str | None) -> None:
        pdf = Loader.load_pdf(path)
        try:
            renderer = PDFRenderer(pdf)
            num_pages = pdf.get_number_of_pages()
            for i in range(num_pages):
                image = renderer.render_image_with_dpi(i, dpi)
                if prefix is None:
                    self._consume(image)
                else:
                    out = Path(self.RENDER_OUTPUT_DIR) / f"{prefix}-{i}.png"
                    image.save(out, format="PNG")
        finally:
            pdf.close()

    # Benchmark methods --------------------------------------------------

    def render_ghent_cmyk_no_output(self) -> float:
        """Mirror of ``renderGhentCMYKNoOutput`` (line 63)."""
        return self._time_call(
            lambda: self._render_pages(self.GHENT_CMYK_X4, 600.0, None)
        )

    def render_ghent_cmyk(self) -> float:
        """Mirror of ``renderGhentCMYK`` (line 77)."""
        return self._time_call(
            lambda: self._render_pages(self.GHENT_CMYK_X4, 600.0, "ghent")
        )

    def render_altona_no_output(self) -> float:
        """Mirror of ``renderAltonaNoOutput`` (line 92)."""
        return self._time_call(
            lambda: self._render_pages(self.ALTONA_TEST_SUITE, 600.0, None)
        )

    def render_altona(self) -> float:
        """Mirror of ``renderAltona`` (line 106)."""
        return self._time_call(
            lambda: self._render_pages(self.ALTONA_TEST_SUITE, 600.0, "altona")
        )

    def render_pdf_spec_no_output(self) -> float:
        """Mirror of ``renderPDFSpecNoOutput`` (line 121)."""
        return self._time_call(
            lambda: self._render_pages(self.PDF32000_2008, 150.0, None)
        )

    def render_pdf_spec(self) -> float:
        """Mirror of ``renderPDFSpec`` (line 135)."""
        return self._time_call(
            lambda: self._render_pages(
                self.PDF32000_2008, 150.0, "pdf32000_2008"
            )
        )
