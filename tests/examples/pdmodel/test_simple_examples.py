"""Sanity tests for the simple, fully-functional ported examples.

Each test exercises ``main()`` of one example against a temporary output
path and verifies the resulting PDF is non-empty and starts with ``%PDF``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.create_blank_pdf import CreateBlankPDF
from pypdfbox.examples.pdmodel.create_landscape_pdf import CreateLandscapePDF
from pypdfbox.examples.pdmodel.create_page_labels import CreatePageLabels
from pypdfbox.examples.pdmodel.hello_world import HelloWorld
from pypdfbox.examples.pdmodel.show_color_boxes import ShowColorBoxes
from pypdfbox.examples.pdmodel.using_text_matrix import UsingTextMatrix


def _assert_is_pdf(path: Path) -> None:
    assert path.exists(), f"expected output PDF at {path}"
    assert path.stat().st_size > 0
    assert path.read_bytes()[:4] == b"%PDF"


def test_hello_world_main(tmp_path: Path) -> None:
    out = tmp_path / "hello.pdf"
    HelloWorld.main([str(out), "Hello pypdfbox!"])
    _assert_is_pdf(out)


def test_hello_world_usage(tmp_path: Path) -> None:
    del tmp_path
    with pytest.raises(SystemExit):
        HelloWorld.main([])


def test_create_blank_pdf_main(tmp_path: Path) -> None:
    out = tmp_path / "blank.pdf"
    CreateBlankPDF.main([str(out)])
    _assert_is_pdf(out)


def test_create_blank_pdf_usage() -> None:
    with pytest.raises(SystemExit):
        CreateBlankPDF.main([])


def test_create_landscape_pdf_main(tmp_path: Path) -> None:
    out = tmp_path / "landscape.pdf"
    CreateLandscapePDF.main(["Hi", str(out)])
    _assert_is_pdf(out)


def test_create_landscape_pdf_usage_returns_quietly() -> None:
    # Upstream prints a usage hint and returns; do_it is not invoked.
    CreateLandscapePDF.main([])


def test_create_page_labels_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    CreatePageLabels.main(None)
    _assert_is_pdf(tmp_path / "labels.pdf")


def test_show_color_boxes_main(tmp_path: Path) -> None:
    out = tmp_path / "boxes.pdf"
    ShowColorBoxes.main([str(out)])
    _assert_is_pdf(out)


def test_show_color_boxes_usage() -> None:
    with pytest.raises(SystemExit):
        ShowColorBoxes.main([])


def test_using_text_matrix_main(tmp_path: Path) -> None:
    out = tmp_path / "tm.pdf"
    UsingTextMatrix.main(["Hello", str(out)])
    _assert_is_pdf(out)
