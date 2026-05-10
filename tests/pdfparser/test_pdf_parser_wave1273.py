"""Wave 1273 — ``PDFParser.load`` static factory parity.

Upstream PDFBox exposes ``PDFParser.load(File [, String password])`` as
a deprecated thin delegate to :class:`Loader.loadPDF`. The pypdfbox
port mirrors the surface so source-level ports of PDFBox 1.x / 2.x
code resolve. New code should call :func:`pypdfbox.loader.Loader.load_pdf`
or use :class:`PDDocument` wrappers directly.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfparser import PDFParser

# Build a tiny in-memory PDF identical to the harness used by
# ``test_pdf_parser`` so the load() surface is covered without
# requiring a fixture file.
from tests.pdfparser.test_pdf_parser import _build_pdf


def test_load_static_factory_returns_pddocument() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj",
        ],
        b"<< /Size 3 /Root 1 0 R >>",
    )

    pd_document = PDFParser.load(pdf)
    try:
        # Returned a PDDocument-shaped wrapper — exposes get_number_of_pages.
        assert pd_document.get_number_of_pages() == 0
        # The underlying COSDocument is accessible via the documented
        # PDDocument surface (``get_document``).
        cos_doc = pd_document.get_document()
        assert cos_doc is not None
    finally:
        pd_document.close()


def test_load_static_factory_accepts_password_argument() -> None:
    """Password kwarg is forwarded to ``Loader.load_pdf``. For an
    unencrypted document a password is harmless — this is the only
    invariant tested here so the test stays free of encryption setup."""
    pdf = _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj",
        ],
        b"<< /Size 3 /Root 1 0 R >>",
    )

    pd_document = PDFParser.load(pdf, "")  # blank password
    try:
        assert pd_document.get_number_of_pages() == 0
    finally:
        pd_document.close()


def test_load_static_factory_rejects_invalid_input() -> None:
    """A bogus payload surfaces as an :class:`OSError` (matching the
    upstream ``IOException`` contract on the ``Loader.loadPDF`` path).
    """
    with pytest.raises(OSError):
        PDFParser.load(b"not a pdf at all")
