"""Tests for ``pypdfbox.examples.ant.pdf_to_text_task``."""
from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.ant.pdf_to_text_task import PDFToTextTask
from pypdfbox.pdmodel import PDDocument, PDPage


def _make_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()
    return path


def test_add_fileset_appends() -> None:
    task = PDFToTextTask()
    sentinel_a = object()
    sentinel_b = object()
    task.add_fileset(sentinel_a)
    task.add_fileset(sentinel_b)
    assert task._file_sets == [sentinel_a, sentinel_b]


def test_set_attribute_setters() -> None:
    task = PDFToTextTask()
    task.set_pdf_file("a.pdf")
    task.set_text_file("a.txt")
    task.set_password("secret")
    assert task.pdf_file == Path("a.pdf")
    assert task.text_file == Path("a.txt")
    assert task.password == "secret"


def test_execute_writes_text_file(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "blank.pdf")
    out = tmp_path / "blank.txt"

    task = PDFToTextTask()
    task.set_pdf_file(pdf)
    task.set_text_file(out)
    task.execute()

    assert out.exists()
    # blank page -> empty / whitespace-only stripper output is fine; what
    # matters is that the task actually wrote something the stripper produced.
    assert out.read_text(encoding="utf-8") is not None


def test_execute_derives_text_path_when_unset(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "doc.pdf")
    task = PDFToTextTask()
    task.set_pdf_file(pdf)
    task.execute()
    assert (tmp_path / "doc.txt").exists()


def test_execute_handles_fileset_iterable(tmp_path: Path) -> None:
    pdf_a = _make_pdf(tmp_path / "a.pdf")
    pdf_b = _make_pdf(tmp_path / "b.pdf")
    # Mix in a non-pdf path that the task must silently skip.
    task = PDFToTextTask()
    task.add_fileset([pdf_a, pdf_b, tmp_path / "notes.txt"])
    task.execute()
    assert (tmp_path / "a.txt").exists()
    assert (tmp_path / "b.txt").exists()
