"""Smoke test for :class:`ExtractTextSimple`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.extract_text_simple import ExtractTextSimple


def test_extract_runs(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("simple.pdf", page_count=2)
    text = ExtractTextSimple.extract(str(src))
    assert "page 1:" in text
    assert "page 2:" in text


def test_main_usage_no_args(capsys) -> None:
    ExtractTextSimple.main([])
    err = capsys.readouterr().err
    assert "Usage" in err
