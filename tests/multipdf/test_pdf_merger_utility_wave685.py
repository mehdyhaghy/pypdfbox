from __future__ import annotations

import logging

from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage


def test_wave685_append_document_skips_unreadable_version_bump(
    caplog,
    monkeypatch,
) -> None:
    source = PDDocument()
    destination = PDDocument()
    source.add_page(PDPage())

    monkeypatch.setattr(destination, "get_version", lambda: object())

    try:
        with caplog.at_level(
            logging.DEBUG,
            logger="pypdfbox.multipdf.pdf_merger_utility",
        ):
            PDFMergerUtility().append_document(destination, source)

        assert destination.get_number_of_pages() == 1
        assert "PDF version bump skipped" in caplog.text
    finally:
        source.close()
        destination.close()
