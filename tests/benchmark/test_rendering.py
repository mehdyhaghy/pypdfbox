"""Tests for ``pypdfbox.benchmark.rendering``."""
from __future__ import annotations

from pathlib import Path

from pypdfbox.benchmark.rendering import Rendering


def test_class_exposes_path_constants() -> None:
    assert Rendering.ALTONA_TEST_SUITE.endswith(".pdf")
    assert Rendering.GHENT_CMYK_X4.endswith(".pdf")
    assert Rendering.PDF32000_2008.endswith(".pdf")
    assert Rendering.RENDER_OUTPUT_DIR.endswith("renditions")


def test_init_creates_output_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Rendering()
    assert (tmp_path / "target" / "renditions").is_dir()


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
