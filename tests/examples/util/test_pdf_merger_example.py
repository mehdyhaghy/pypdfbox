"""Smoke test for :class:`PDFMergerExample`."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.pdf_merger_example import PDFMergerExample
from pypdfbox.io.random_access_read_buffered_file import RandomAccessReadBufferedFile


def test_merge_returns_bytes(make_pdf: Callable[..., Path]) -> None:
    a = make_pdf("a.pdf")
    b = make_pdf("b.pdf")
    sources = [RandomAccessReadBufferedFile(str(a)), RandomAccessReadBufferedFile(str(b))]
    merged = PDFMergerExample().merge(sources)
    assert isinstance(merged, io.BytesIO)
    merged.seek(0)
    head = merged.read(5)
    assert head.startswith(b"%PDF")
