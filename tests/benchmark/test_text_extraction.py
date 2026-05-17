"""Tests for ``pypdfbox.benchmark.text_extraction``.

LATENT BUG (flagged for wave 1341): the benchmark calls
``Loader.load_pdf(...)`` which returns a :class:`COSDocument`, but
:meth:`PDFTextStripper.get_text` requires a :class:`PDDocument` —
exactly the bug fixed for ``benchmark.load_and_save`` and
``benchmark.rendering`` in waves 1336/1338. The workload tests below
stub :class:`Loader` + :class:`PDFTextStripper` so the loop body still
executes end-to-end and covers the timer / consume / try / finally
branches without exercising the broken wiring.
"""
from __future__ import annotations

import pytest

from pypdfbox.benchmark.text_extraction import TextExtraction

# ---------------------------------------------------------------------------
# Class-level scaffolding (no I/O)
# ---------------------------------------------------------------------------


def test_class_exposes_pdf_constant() -> None:
    assert TextExtraction.PDF32000_2008.endswith(".pdf")


def test_consume_stores_value() -> None:
    bench = TextExtraction()
    bench._consume("hello")
    assert bench._sink == "hello"


def test_consume_overwrites_value() -> None:
    bench = TextExtraction()
    bench._consume("first")
    bench._consume("second")
    assert bench._sink == "second"


def test_time_call_returns_positive_float() -> None:
    elapsed = TextExtraction._time_call(lambda: None)
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0


def test_time_call_propagates_exception() -> None:
    def _boom() -> None:
        raise RuntimeError("propagated")

    with pytest.raises(RuntimeError, match="propagated"):
        TextExtraction._time_call(_boom)


def test_benchmark_method_surface_present() -> None:
    bench = TextExtraction()
    assert callable(bench.extract_pdf_spec_unsorted)
    assert callable(bench.extract_pdf_spec_sorted)


# ---------------------------------------------------------------------------
# Workload coverage — stub Loader + PDFTextStripper so the body runs
# ---------------------------------------------------------------------------


class _FakePDF:
    """Stand-in for the document returned by ``Loader.load_pdf``.

    Provides ``close`` so the workload's ``finally`` clause can fire
    without depending on a real :class:`COSDocument` / :class:`PDDocument`.
    """

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeStripper:
    """Stand-in for :class:`PDFTextStripper` — records sort flag + last doc."""

    sort_flags: list[bool] = []
    docs_received: list[_FakePDF] = []

    def __init__(self) -> None:
        self._sort = False

    def set_sort_by_position(self, value: bool) -> None:
        self._sort = value
        type(self).sort_flags.append(value)

    def get_text(self, doc: _FakePDF) -> str:
        type(self).docs_received.append(doc)
        return "extracted text"


@pytest.fixture
def patched_workload(monkeypatch):
    """Install Loader + Stripper stubs; return the per-load doc list."""
    loaded: list[_FakePDF] = []
    # Reset class-level capture state between tests.
    _FakeStripper.sort_flags = []
    _FakeStripper.docs_received = []

    def _load(_path):
        doc = _FakePDF()
        loaded.append(doc)
        return doc

    monkeypatch.setattr(
        "pypdfbox.benchmark.text_extraction.Loader.load_pdf",
        staticmethod(_load),
    )
    monkeypatch.setattr(
        "pypdfbox.benchmark.text_extraction.PDFTextStripper",
        _FakeStripper,
    )
    return loaded


def test_extract_pdf_spec_unsorted_runs_workload(patched_workload) -> None:
    bench = TextExtraction()
    elapsed = bench.extract_pdf_spec_unsorted()
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0
    assert patched_workload, "loader stub must have been called"
    assert patched_workload[0].closed is True
    # Unsorted -> set_sort_by_position(False)
    assert _FakeStripper.sort_flags == [False]
    # Stripper must have been handed the loaded doc.
    assert _FakeStripper.docs_received == [patched_workload[0]]
    # ``_consume`` parks the extracted text on the instance.
    assert bench._sink == "extracted text"


def test_extract_pdf_spec_sorted_runs_workload(patched_workload) -> None:
    bench = TextExtraction()
    elapsed = bench.extract_pdf_spec_sorted()
    assert elapsed >= 0.0
    assert patched_workload[0].closed is True
    assert _FakeStripper.sort_flags == [True]
    assert bench._sink == "extracted text"


def test_extract_unsorted_closes_doc_on_stripper_error(monkeypatch) -> None:
    """A mid-workload exception still triggers the ``finally`` close."""
    doc = _FakePDF()

    class _ExplodingStripper:
        def set_sort_by_position(self, _value: bool) -> None:
            pass

        def get_text(self, _doc) -> str:
            raise RuntimeError("strip-boom")

    monkeypatch.setattr(
        "pypdfbox.benchmark.text_extraction.Loader.load_pdf",
        staticmethod(lambda _p: doc),
    )
    monkeypatch.setattr(
        "pypdfbox.benchmark.text_extraction.PDFTextStripper",
        _ExplodingStripper,
    )
    bench = TextExtraction()
    with pytest.raises(RuntimeError, match="strip-boom"):
        bench.extract_pdf_spec_unsorted()
    assert doc.closed is True


def test_extract_sorted_closes_doc_on_stripper_error(monkeypatch) -> None:
    doc = _FakePDF()

    class _ExplodingStripper:
        def set_sort_by_position(self, _value: bool) -> None:
            pass

        def get_text(self, _doc) -> str:
            raise RuntimeError("sort-boom")

    monkeypatch.setattr(
        "pypdfbox.benchmark.text_extraction.Loader.load_pdf",
        staticmethod(lambda _p: doc),
    )
    monkeypatch.setattr(
        "pypdfbox.benchmark.text_extraction.PDFTextStripper",
        _ExplodingStripper,
    )
    bench = TextExtraction()
    with pytest.raises(RuntimeError, match="sort-boom"):
        bench.extract_pdf_spec_sorted()
    assert doc.closed is True


def test_init_silences_apache_logger() -> None:
    """``__init__`` raises org.apache logger level to CRITICAL — verify."""
    import logging

    # Reset to a known low level first.
    logging.getLogger("org.apache").setLevel(logging.DEBUG)
    TextExtraction()
    assert logging.getLogger("org.apache").level == logging.CRITICAL
