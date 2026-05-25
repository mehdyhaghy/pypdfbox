"""Wave 1403 branch round-out for ``extract_embedded_files``.

Closes two partials:

* ``42->47`` — ``main`` run against a PDF with no embedded-files name tree:
  the ``if ef_tree is not None`` guard takes its False arc and flow proceeds
  straight to the page walk.
* ``69->62`` — a file-attachment annotation whose complex file spec has no
  embedded payload: ``if embedded_file is not None`` takes its False arc and
  the per-annotation loop advances.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.extract_embedded_files import ExtractEmbeddedFiles
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def test_main_without_embedded_files_tree_walks_pages(tmp_path: Path) -> None:
    """A plain PDF has no /Names embedded-files tree, so ``main`` skips the
    tree extraction (42->47) and walks the (attachment-free) pages."""
    src = tmp_path / "plain.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))

    # No exception, and nothing is written to the source directory.
    before = set(tmp_path.iterdir())
    ExtractEmbeddedFiles.main([str(src)])
    after = set(tmp_path.iterdir())
    assert after == before


def test_extract_files_from_page_skips_attachment_without_payload(
    tmp_path: Path,
) -> None:
    """A file-attachment annotation referencing a complex file spec that
    carries no embedded file drives the ``embedded_file is not None`` False
    arc (69->62)."""
    page = PDPage()

    file_spec = PDComplexFileSpecification()
    file_spec.set_file("orphan.bin")
    # Note: no embedded file stream set on the spec.

    attachment = PDAnnotationFileAttachment()
    attachment.set_file(file_spec)
    page.set_annotations([attachment])

    ExtractEmbeddedFiles.extract_files_from_page(page, str(tmp_path))
    # Nothing extracted: the spec had no embedded payload.
    assert list(tmp_path.iterdir()) == []
