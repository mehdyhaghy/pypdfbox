"""Wave 1403 branch round-out for ``replace_urls``.

Closes two loop-continuation partials in ``ReplaceURLs.main``:

* ``34->33`` — an annotation that is **not** a ``PDAnnotationLink`` skips the
  body and the loop advances to the next annotation.
* ``36->33`` — a ``PDAnnotationLink`` whose action is **not** a
  ``PDActionURI`` skips the rewrite and the loop advances.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.replace_urls import ReplaceURLs
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)


def _build_mixed_annotation_pdf(path: Path) -> None:
    """A page carrying a non-link annotation plus a link whose action is a
    GoTo (not a URI)."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        doc.add_page(page)

        # Non-link annotation → drives the ``isinstance(..., PDAnnotationLink)``
        # False arc (34->33).
        text_annot = PDAnnotationText()
        text_annot.set_rectangle(PDRectangle(10, 10, 30, 30))

        # Link annotation whose action is a GoTo, not a URI → drives the
        # ``isinstance(action, PDActionURI)`` False arc (36->33).
        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(40, 40, 80, 60))
        link.set_action(PDActionGoTo())

        page.set_annotations([text_annot, link])
        doc.save(str(path))
    finally:
        doc.close()


def test_replace_urls_skips_non_link_and_non_uri_annotations(
    tmp_path: Path, capsys,
) -> None:
    src = tmp_path / "mixed.pdf"
    _build_mixed_annotation_pdf(src)
    dst = tmp_path / "out.pdf"
    ReplaceURLs.main([str(src), str(dst)])
    assert dst.exists()
    # Neither annotation is a URI link, so nothing was reported as replaced.
    out = capsys.readouterr().out
    assert "Replacing" not in out
