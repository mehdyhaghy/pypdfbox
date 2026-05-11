"""Load/save round-trip benchmarks.

Ported from
``benchmark/src/main/java/org/apache/pdfbox/benchmark/LoadAndSave.java``
(lines 32-108). Each ``@Benchmark`` method becomes a plain method that
runs the workload and returns the wall-clock duration; a ``Blackhole``
sink is replaced by an attribute on the instance so the JIT/optimizer
cannot dead-code-eliminate the loaded document.
"""

from __future__ import annotations

import time
from typing import Any

from pypdfbox.benchmark.null_output_stream import NullOutputStream
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters


class LoadAndSave:
    """Suite of load/save micro-benchmarks (parity surface only)."""

    MEDIUM_SIZE_TEST_FILE = "target/pdfs/849-42-94772-1-10-20210818.pdf"
    LARGE_SIZE_TEST_FILE = "target/pdfs/506-42-86246-2-10-20190822.pdf"

    def __init__(self) -> None:
        self._sink: Any = None

    # -- helpers ---------------------------------------------------------

    def _consume(self, value: Any) -> None:
        """Blackhole stand-in — keeps the value reachable."""
        self._sink = value

    @staticmethod
    def _time_call(callable_: Any) -> float:
        """Run ``callable_`` once and return elapsed milliseconds."""
        start = time.perf_counter()
        callable_()
        return (time.perf_counter() - start) * 1000.0

    # -- benchmark methods ----------------------------------------------

    def load_medium_file(self) -> float:
        """Mirror of ``loadMediumFile`` (line 40)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.MEDIUM_SIZE_TEST_FILE)
            try:
                self._consume(pdf)
            finally:
                pdf.close()

        return self._time_call(_body)

    def save_medium_file(self) -> float:
        """Mirror of ``saveMediumFile`` (line 49)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.MEDIUM_SIZE_TEST_FILE)
            try:
                pdf.save(NullOutputStream())
            finally:
                pdf.close()

        return self._time_call(_body)

    def save_incremental_medium_file(self) -> float:
        """Mirror of ``saveIncrementalMediumFile`` (line 58)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.MEDIUM_SIZE_TEST_FILE)
            try:
                pdf.save_incremental(NullOutputStream())
            finally:
                pdf.close()

        return self._time_call(_body)

    def save_no_compression_medium_file(self) -> float:
        """Mirror of ``saveNoCompressionMediumFile`` (line 67)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.MEDIUM_SIZE_TEST_FILE)
            try:
                pdf.save(NullOutputStream(), CompressParameters.NO_COMPRESSION)
            finally:
                pdf.close()

        return self._time_call(_body)

    def load_large_file(self) -> float:
        """Mirror of ``loadLargeFile`` (line 76)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.LARGE_SIZE_TEST_FILE)
            try:
                self._consume(pdf)
            finally:
                pdf.close()

        return self._time_call(_body)

    def save_large_file(self) -> float:
        """Mirror of ``saveLargeFile`` (line 85)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.LARGE_SIZE_TEST_FILE)
            try:
                pdf.save(NullOutputStream())
            finally:
                pdf.close()

        return self._time_call(_body)

    def save_incremental_large_file(self) -> float:
        """Mirror of ``saveIncrementalLargeFile`` (line 95)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.LARGE_SIZE_TEST_FILE)
            try:
                pdf.save_incremental(NullOutputStream())
            finally:
                pdf.close()

        return self._time_call(_body)

    def save_no_compression_large_file(self) -> float:
        """Mirror of ``saveNoCompressionLargeFile`` (line 104)."""

        def _body() -> None:
            pdf = Loader.load_pdf(self.LARGE_SIZE_TEST_FILE)
            try:
                pdf.save(NullOutputStream(), CompressParameters.NO_COMPRESSION)
            finally:
                pdf.close()

        return self._time_call(_body)
