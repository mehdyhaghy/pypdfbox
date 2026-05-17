"""Tests for ``pypdfbox.benchmark.load_and_save``."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from pypdfbox.benchmark.load_and_save import LoadAndSave
from pypdfbox.benchmark.null_output_stream import NullOutputStream
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdmodel import PDDocument

# ---------------------------------------------------------------------------
# Fixture PDF — small, well-formed, lives in the repo. The upstream
# benchmark expects ``target/pdfs/*`` paths to be populated by the Maven
# ``download-pdfs`` profile; we redirect the loader so the tests exercise
# the real save / save_incremental / no-compression code paths without
# requiring those binaries on disk.
# ---------------------------------------------------------------------------
_FIXTURE_PDF = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "multipdf"
    / "rot0.pdf"
)


def _loader_factory():
    """Return a ``PDDocument.load`` shim that ignores the requested path
    and instead opens our in-repo fixture.

    Loads via the underlying ``Loader.load_pdf`` + ``PDDocument(...)``
    wrap rather than ``PDDocument.load`` directly, because the test that
    uses this factory monkey-patches ``PDDocument.load`` on the benchmark
    module — calling ``PDDocument.load`` here would recurse.
    """
    from pypdfbox.loader import Loader as _Loader

    def _load(_path, *_args, **_kwargs):
        return PDDocument(_Loader.load_pdf(str(_FIXTURE_PDF)))

    return _load


# ---------------------------------------------------------------------------
# Constants / scaffolding
# ---------------------------------------------------------------------------


def test_class_exposes_test_file_constants() -> None:
    assert LoadAndSave.MEDIUM_SIZE_TEST_FILE.endswith(".pdf")
    assert LoadAndSave.LARGE_SIZE_TEST_FILE.endswith(".pdf")


def test_consume_stores_value() -> None:
    bench = LoadAndSave()
    bench._consume(42)
    assert bench._sink == 42


def test_consume_overwrites_previous_value() -> None:
    bench = LoadAndSave()
    bench._consume("first")
    bench._consume("second")
    assert bench._sink == "second"


def test_time_call_returns_positive_float() -> None:
    elapsed = LoadAndSave._time_call(lambda: None)
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0


def test_time_call_propagates_exception() -> None:
    def _boom() -> None:
        raise RuntimeError("propagated")

    with pytest.raises(RuntimeError, match="propagated"):
        LoadAndSave._time_call(_boom)


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


# ---------------------------------------------------------------------------
# Benchmark body coverage
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_loader():
    """Monkey-patch ``Loader.load_pdf`` inside the benchmark module so
    every workload resolves to our small in-repo fixture wrapped as a
    real :class:`PDDocument`.
    """
    with mock.patch(
        "pypdfbox.benchmark.load_and_save.PDDocument.load",
        side_effect=_loader_factory(),
    ) as patched:
        yield patched


def test_load_medium_file_runs_and_consumes(patched_loader) -> None:
    bench = LoadAndSave()
    elapsed = bench.load_medium_file()
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0
    # ``_consume`` parks the loaded doc on the instance; the doc itself
    # is closed by the workload's ``finally`` block.
    assert bench._sink is not None
    patched_loader.assert_called_once_with(LoadAndSave.MEDIUM_SIZE_TEST_FILE)


def test_save_medium_file_saves_to_null_output(patched_loader, monkeypatch) -> None:
    bench = LoadAndSave()
    captured: dict[str, object] = {}
    real_save = PDDocument.save

    def _spy_save(self, output, *args, **kwargs):
        captured["output"] = output
        captured["args"] = args
        return real_save(self, output, *args, **kwargs)

    monkeypatch.setattr(PDDocument, "save", _spy_save)
    elapsed = bench.save_medium_file()
    assert elapsed >= 0.0
    assert isinstance(captured["output"], NullOutputStream)
    # No CompressParameters override -> default compression.
    assert captured["args"] == ()
    patched_loader.assert_called_once_with(LoadAndSave.MEDIUM_SIZE_TEST_FILE)


def test_save_incremental_medium_file_invokes_incremental(
    patched_loader, monkeypatch
) -> None:
    bench = LoadAndSave()
    captured: dict[str, object] = {}
    real_inc = PDDocument.save_incremental

    def _spy(self, output, *args, **kwargs):
        captured["output"] = output
        return real_inc(self, output, *args, **kwargs)

    monkeypatch.setattr(PDDocument, "save_incremental", _spy)
    elapsed = bench.save_incremental_medium_file()
    assert elapsed >= 0.0
    assert isinstance(captured["output"], NullOutputStream)


def test_save_no_compression_medium_file_passes_no_compression(
    patched_loader, monkeypatch
) -> None:
    bench = LoadAndSave()
    captured: dict[str, object] = {}
    real_save = PDDocument.save

    def _spy_save(self, output, *args, **kwargs):
        captured["args"] = args
        return real_save(self, output, *args, **kwargs)

    monkeypatch.setattr(PDDocument, "save", _spy_save)
    elapsed = bench.save_no_compression_medium_file()
    assert elapsed >= 0.0
    # Verify the workload threaded ``CompressParameters.NO_COMPRESSION``
    # through to ``PDDocument.save``.
    assert captured["args"] == (CompressParameters.NO_COMPRESSION,)


def test_load_large_file_runs_and_consumes(patched_loader) -> None:
    bench = LoadAndSave()
    elapsed = bench.load_large_file()
    assert elapsed >= 0.0
    assert bench._sink is not None
    patched_loader.assert_called_once_with(LoadAndSave.LARGE_SIZE_TEST_FILE)


def test_save_large_file_saves_to_null_output(patched_loader, monkeypatch) -> None:
    bench = LoadAndSave()
    captured: dict[str, object] = {}
    real_save = PDDocument.save

    def _spy_save(self, output, *args, **kwargs):
        captured["output"] = output
        return real_save(self, output, *args, **kwargs)

    monkeypatch.setattr(PDDocument, "save", _spy_save)
    elapsed = bench.save_large_file()
    assert elapsed >= 0.0
    assert isinstance(captured["output"], NullOutputStream)


def test_save_incremental_large_file_invokes_incremental(
    patched_loader, monkeypatch
) -> None:
    bench = LoadAndSave()
    captured: dict[str, object] = {}
    real_inc = PDDocument.save_incremental

    def _spy(self, output, *args, **kwargs):
        captured["output"] = output
        return real_inc(self, output, *args, **kwargs)

    monkeypatch.setattr(PDDocument, "save_incremental", _spy)
    elapsed = bench.save_incremental_large_file()
    assert elapsed >= 0.0


def test_save_no_compression_large_file_passes_no_compression(
    patched_loader, monkeypatch
) -> None:
    bench = LoadAndSave()
    captured: dict[str, object] = {}
    real_save = PDDocument.save

    def _spy_save(self, output, *args, **kwargs):
        captured["args"] = args
        return real_save(self, output, *args, **kwargs)

    monkeypatch.setattr(PDDocument, "save", _spy_save)
    elapsed = bench.save_no_compression_large_file()
    assert elapsed >= 0.0
    assert captured["args"] == (CompressParameters.NO_COMPRESSION,)


# ---------------------------------------------------------------------------
# Workload body always closes the loaded document, even on exception.
# ---------------------------------------------------------------------------


def test_load_medium_file_closes_document_on_consume_error(monkeypatch) -> None:
    """If ``_consume`` raises mid-workload, ``finally`` still closes the doc."""
    bench = LoadAndSave()
    closed = {"count": 0}

    class _StubDoc:
        def close(self) -> None:
            closed["count"] += 1

    monkeypatch.setattr(
        "pypdfbox.benchmark.load_and_save.PDDocument.load",
        lambda _path: _StubDoc(),
    )

    def _raise(_value):
        raise RuntimeError("boom")

    monkeypatch.setattr(bench, "_consume", _raise)
    with pytest.raises(RuntimeError, match="boom"):
        bench.load_medium_file()
    assert closed["count"] == 1


def test_save_medium_file_closes_document_on_save_error(monkeypatch) -> None:
    bench = LoadAndSave()
    closed = {"count": 0}

    class _StubDoc:
        def save(self, _out, *_args, **_kwargs):
            raise RuntimeError("save-boom")

        def close(self) -> None:
            closed["count"] += 1

    monkeypatch.setattr(
        "pypdfbox.benchmark.load_and_save.PDDocument.load",
        lambda _path: _StubDoc(),
    )
    with pytest.raises(RuntimeError, match="save-boom"):
        bench.save_medium_file()
    assert closed["count"] == 1
