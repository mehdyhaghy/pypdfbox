"""Tests for ``pypdfbox.benchmark.text_extraction``."""
from __future__ import annotations

from pypdfbox.benchmark.text_extraction import TextExtraction


def test_class_exposes_pdf_constant() -> None:
    assert TextExtraction.PDF32000_2008.endswith(".pdf")


def test_consume_stores_value() -> None:
    bench = TextExtraction()
    bench._consume("hello")
    assert bench._sink == "hello"


def test_benchmark_method_surface_present() -> None:
    bench = TextExtraction()
    assert callable(bench.extract_pdf_spec_unsorted)
    assert callable(bench.extract_pdf_spec_sorted)
