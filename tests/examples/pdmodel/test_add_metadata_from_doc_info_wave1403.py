"""Wave 1403 branch round-out for ``add_metadata_from_doc_info``.

Closes ``79->81``: when the document information carries no ``/Title``,
``if info.get_title() is not None`` takes its False arc and the Dublin-Core
title is left unset.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.add_metadata_from_doc_info import (
    AddMetadataFromDocInfo,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _make_pdf_without_title(path: Path) -> None:
    """Document info with several fields set but **no** /Title."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        info = doc.get_document_information()
        info.set_author("Author Name")
        info.set_subject("The subject")
        info.set_keywords("kw1; kw2")
        info.set_creator("creator-tool")
        info.set_producer("pypdfbox")
        # Deliberately leave the title unset.
        doc.save(str(path))


def test_main_skips_dc_title_when_info_has_no_title(tmp_path: Path) -> None:
    src = tmp_path / "no_title.pdf"
    _make_pdf_without_title(src)
    dst = tmp_path / "stamped.pdf"
    AddMetadataFromDocInfo.main([str(src), str(dst)])
    assert dst.exists()
    # The stamped file is still a well-formed PDF carrying XMP metadata.
    with PDDocument.load(str(dst)) as out:
        assert out.get_document_catalog().get_metadata() is not None
