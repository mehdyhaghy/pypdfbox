"""Tests for ``pypdfbox.benchmark.load_and_save``."""
from __future__ import annotations

from pypdfbox.benchmark.load_and_save import LoadAndSave


def test_class_exposes_test_file_constants() -> None:
    assert LoadAndSave.MEDIUM_SIZE_TEST_FILE.endswith(".pdf")
    assert LoadAndSave.LARGE_SIZE_TEST_FILE.endswith(".pdf")


def test_consume_stores_value() -> None:
    bench = LoadAndSave()
    bench._consume(42)
    assert bench._sink == 42


def test_time_call_returns_positive_float() -> None:
    elapsed = LoadAndSave._time_call(lambda: None)
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0


def test_benchmark_method_surface_present() -> None:
    bench = LoadAndSave()
    expected = {
        "load_medium_file",
        "save_medium_file",
        "save_incremental_medium_file",
        "save_no_compression_medium_file",
        "load_large_file",
        "save_large_file",
        "save_incremental_large_file",
        "save_no_compression_large_file",
    }
    for name in expected:
        assert callable(getattr(bench, name))
