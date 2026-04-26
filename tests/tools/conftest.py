"""Shared fixtures for the tools CLI test suite."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage


def _build_pdf(path: Path, *, page_count: int = 1) -> Path:
    """Build a minimal valid PDF with ``page_count`` blank pages and write
    it to ``path``."""
    doc = PDDocument()
    try:
        for _ in range(page_count):
            doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()
    return path


@pytest.fixture
def make_pdf(tmp_path: Path) -> Iterator[callable]:
    """Factory yielding a function that writes a fresh PDF into ``tmp_path``."""
    counter = {"n": 0}

    def _factory(name: str | None = None, *, page_count: int = 1) -> Path:
        counter["n"] += 1
        target = tmp_path / (name or f"sample-{counter['n']}.pdf")
        return _build_pdf(target, page_count=page_count)

    yield _factory
