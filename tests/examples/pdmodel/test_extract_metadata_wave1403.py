"""Wave 1403 branch round-out for ``extract_metadata``.

Closes ``56->exit``: when a document carries no XMP metadata **and**
``get_document_information`` yields ``None``, the ``if information is not
None`` guard takes its False arc and ``main`` returns without printing.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.extract_metadata import ExtractMetadata
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _build_blank_pdf(path: Path) -> None:
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(path))


def test_main_returns_when_no_metadata_and_no_document_information(
    tmp_path: Path, capsys, monkeypatch,
) -> None:
    """A blank PDF has no XMP metadata; force ``get_document_information``
    to None so the False arc of ``if information is not None`` (56->exit)
    is exercised."""
    src = tmp_path / "blank.pdf"
    _build_blank_pdf(src)

    # ``get_document_information`` never returns None for a real document,
    # so override it on the class to drive the defensive False arc.
    monkeypatch.setattr(
        PDDocument, "get_document_information", lambda self: None,
    )

    ExtractMetadata.main([str(src)])
    captured = capsys.readouterr()
    # Nothing printed to stdout (no schema / info output) and no error.
    assert captured.out == ""
    assert captured.err == ""
