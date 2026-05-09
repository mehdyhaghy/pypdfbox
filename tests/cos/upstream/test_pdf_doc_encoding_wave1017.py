from __future__ import annotations

from tests.cos.upstream import test_pdf_doc_encoding


def test_skipped_pdf_doc_encoding_placeholders_are_reachable() -> None:
    test_pdf_doc_encoding.test_deviations()
    test_pdf_doc_encoding.test_pdfbox3864()
