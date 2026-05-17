"""Tests for ``pypdfbox.benchmark.rendering``.

The rendering benchmark currently calls ``Loader.load_pdf`` which
returns a :class:`COSDocument`, but the subsequent
``PDFRenderer(pdf)`` and ``pdf.get_number_of_pages()`` calls require a
:class:`PDDocument` — a latent bug parallel to the one fixed in
``benchmark.load_and_save`` (waves 1336/1338). Until that lands, the
workload tests stub :func:`Loader.load_pdf` and :class:`PDFRenderer` so
the body still executes end-to-end and covers the loop.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.benchmark.rendering import Rendering

# ---------------------------------------------------------------------------
# Class-level scaffolding (no I/O)
# ---------------------------------------------------------------------------


def test_class_exposes_path_constants() -> None:
    assert Rendering.ALTONA_TEST_SUITE.endswith(".pdf")
    assert Rendering.GHENT_CMYK_X4.endswith(".pdf")
    assert Rendering.PDF32000_2008.endswith(".pdf")
    assert Rendering.RENDER_OUTPUT_DIR.endswith("renditions")


def test_init_creates_output_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Rendering()
    assert (tmp_path / "target" / "renditions").is_dir()


def test_init_succeeds_when_output_dir_already_exists(
    tmp_path: Path, monkeypatch
) -> None:
    """``mkdir(exist_ok=True)`` -> a second instance must not raise."""
    monkeypatch.chdir(tmp_path)
    Rendering()
    Rendering()


def test_benchmark_method_surface_present() -> None:
    bench = Rendering()
    expected = {
        "render_ghent_cmyk_no_output",
        "render_ghent_cmyk",
        "render_altona_no_output",
        "render_altona",
        "render_pdf_spec_no_output",
        "render_pdf_spec",
    }
    for name in expected:
        assert callable(getattr(bench, name))


# ---------------------------------------------------------------------------
# _consume / _time_call helpers
# ---------------------------------------------------------------------------


def test_consume_stores_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    bench = Rendering()
    bench._consume("hello")
    assert bench._sink == "hello"


def test_consume_overwrites_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    bench = Rendering()
    bench._consume("first")
    bench._consume("second")
    assert bench._sink == "second"


def test_time_call_returns_positive_float() -> None:
    elapsed = Rendering._time_call(lambda: None)
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0


def test_time_call_propagates_exception() -> None:
    def _boom() -> None:
        raise RuntimeError("propagated")

    with pytest.raises(RuntimeError, match="propagated"):
        Rendering._time_call(_boom)


# ---------------------------------------------------------------------------
# Workload body coverage — stub Loader + PDFRenderer so the for-loop runs
# ---------------------------------------------------------------------------


class _FakeImage:
    def __init__(self) -> None:
        self.saved_to: Path | None = None
        self.saved_format: str | None = None

    def save(self, path, *, format: str | None = None) -> None:  # noqa: A002
        self.saved_to = Path(path)
        self.saved_format = format
        # Write a tiny placeholder so callers can read the file back.
        Path(path).write_bytes(b"png-placeholder")


class _FakePDF:
    """Stand-in for the document type returned by ``Loader.load_pdf``.

    Provides ``get_number_of_pages`` + ``close`` so the workload body
    runs without invoking real PDF rendering plumbing.
    """

    def __init__(self, num_pages: int = 2) -> None:
        self._num = num_pages
        self.closed = False

    def get_number_of_pages(self) -> int:
        return self._num

    def close(self) -> None:
        self.closed = True


class _FakeRenderer:
    def __init__(self, document: object) -> None:
        self.document = document

    def render_image_with_dpi(self, page_index: int, dpi: float) -> _FakeImage:
        _ = (page_index, dpi)
        return _FakeImage()


@pytest.fixture
def patched_workload(monkeypatch, tmp_path):
    """Install Loader + Renderer stubs, return the captured docs list."""
    monkeypatch.chdir(tmp_path)
    loaded: list[_FakePDF] = []

    def _load(_path):
        doc = _FakePDF(num_pages=2)
        loaded.append(doc)
        return doc

    monkeypatch.setattr(
        "pypdfbox.benchmark.rendering.Loader.load_pdf",
        _load,
    )
    monkeypatch.setattr(
        "pypdfbox.benchmark.rendering.PDFRenderer",
        _FakeRenderer,
    )
    return loaded


def test_render_ghent_cmyk_no_output_runs_loop(patched_workload) -> None:
    bench = Rendering()
    elapsed = bench.render_ghent_cmyk_no_output()
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0
    assert patched_workload, "loader stub should have been called"
    assert patched_workload[0].closed is True
    # ``no_output`` -> images are sunk on the instance (last page wins).
    assert bench._sink is not None


def test_render_ghent_cmyk_writes_png(patched_workload, tmp_path) -> None:
    bench = Rendering()
    bench.render_ghent_cmyk()
    out_dir = tmp_path / "target" / "renditions"
    pngs = sorted(out_dir.glob("ghent-*.png"))
    assert len(pngs) == 2  # FakePDF reports 2 pages
    assert all(p.stat().st_size > 0 for p in pngs)


def test_render_altona_no_output_runs_loop(patched_workload) -> None:
    bench = Rendering()
    elapsed = bench.render_altona_no_output()
    assert elapsed >= 0.0
    assert patched_workload[0].closed is True


def test_render_altona_writes_png(patched_workload, tmp_path) -> None:
    bench = Rendering()
    bench.render_altona()
    out_dir = tmp_path / "target" / "renditions"
    pngs = sorted(out_dir.glob("altona-*.png"))
    assert len(pngs) == 2


def test_render_pdf_spec_no_output_runs_loop(patched_workload) -> None:
    bench = Rendering()
    elapsed = bench.render_pdf_spec_no_output()
    assert elapsed >= 0.0
    assert patched_workload[0].closed is True


def test_render_pdf_spec_writes_png(patched_workload, tmp_path) -> None:
    bench = Rendering()
    bench.render_pdf_spec()
    out_dir = tmp_path / "target" / "renditions"
    pngs = sorted(out_dir.glob("pdf32000_2008-*.png"))
    assert len(pngs) == 2


def test_render_pages_closes_document_on_renderer_error(
    monkeypatch, tmp_path
) -> None:
    """Even when the renderer throws mid-loop the loaded doc is closed."""
    monkeypatch.chdir(tmp_path)
    doc = _FakePDF(num_pages=1)

    class _ExplodingRenderer:
        def __init__(self, _doc):
            pass

        def render_image_with_dpi(self, page, dpi):
            raise RuntimeError("render-boom")

    monkeypatch.setattr(
        "pypdfbox.benchmark.rendering.Loader.load_pdf",
        lambda _p: doc,
    )
    monkeypatch.setattr(
        "pypdfbox.benchmark.rendering.PDFRenderer",
        _ExplodingRenderer,
    )
    bench = Rendering()
    with pytest.raises(RuntimeError, match="render-boom"):
        bench.render_ghent_cmyk_no_output()
    assert doc.closed is True
