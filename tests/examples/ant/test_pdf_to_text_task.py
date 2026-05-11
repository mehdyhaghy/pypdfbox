"""Tests for ``pypdfbox.examples.ant.pdf_to_text_task``."""
from __future__ import annotations

import pytest

from pypdfbox.examples.ant.pdf_to_text_task import PDFToTextTask


def test_add_fileset_appends() -> None:
    task = PDFToTextTask()
    sentinel_a = object()
    sentinel_b = object()
    task.add_fileset(sentinel_a)
    task.add_fileset(sentinel_b)
    assert task._file_sets == [sentinel_a, sentinel_b]


def test_execute_raises_not_implemented() -> None:
    task = PDFToTextTask()
    with pytest.raises(NotImplementedError):
        task.execute()
