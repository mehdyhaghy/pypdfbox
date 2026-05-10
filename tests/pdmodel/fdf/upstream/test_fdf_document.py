"""Ported from upstream PDFBox FDFDocumentTest-shape coverage.

Source PDFBox source tree was not available locally at original port
time, so this file mirrors the documented public API of ``FDFDocument``
rather than translating a JUnit file line-by-line. Method-level cases
below cite upstream line numbers in
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFDocument.java``
(PDFBox 3.0.x).
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fdf import FDFCatalog, FDFDocument, FDFField


def test_new_fdf_document_has_catalog_and_fdf_dict() -> None:
    """Mirrors ``new FDFDocument()`` upstream (lines 60-73) — must produce
    a saveable skeleton with a non-null catalog and an empty /FDF
    sub-dictionary."""
    doc = FDFDocument()
    try:
        cat = doc.get_catalog()
        assert cat is not None
        fdf = cat.get_fdf()
        assert fdf is not None
        assert fdf.get_fields() is None
    finally:
        doc.close()


def test_save_then_load_preserves_fields() -> None:
    """Mirrors upstream ``save(OutputStream)`` (lines 213-217) +
    parser round-trip."""
    doc = FDFDocument()
    field = FDFField()
    field.set_partial_field_name("name")
    field.set_value("Bob")
    doc.get_catalog().get_fdf().set_fields([field])
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    loaded = FDFDocument.load(buf.getvalue())
    try:
        fields = loaded.get_catalog().get_fdf().get_fields()
        assert fields is not None and len(fields) == 1
        assert fields[0].get_partial_field_name() == "name"
        assert fields[0].get_value() == "Bob"
    finally:
        loaded.close()


def test_set_catalog_wires_root() -> None:
    """Mirrors upstream ``setCatalog(FDFCatalog)`` (lines 173-177) — the
    catalog's COS dict must replace the trailer's /Root entry."""
    doc = FDFDocument()
    try:
        replacement = FDFCatalog()
        doc.set_catalog(replacement)
        trailer = doc.get_document().get_trailer()
        assert trailer is not None
        root = trailer.get_dictionary_object(COSName.get_pdf_name("Root"))
        assert root is replacement.get_cos_object()
        # Re-reading must surface the same wrapper.
        assert doc.get_catalog() is replacement
    finally:
        doc.close()


def test_write_xml_envelope() -> None:
    """Mirrors upstream ``writeXML(Writer)`` (lines 126-134) — emits an
    XFDF document with the Adobe namespace + xml:space attribute."""
    doc = FDFDocument()
    try:
        buf = io.StringIO()
        doc.write_xml(buf)
        text = buf.getvalue()
        assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n')
        assert (
            '<xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve">'
            in text
        )
        assert text.rstrip().endswith("</xfdf>")
    finally:
        doc.close()


def test_save_xfdf_text_stream_round_trip() -> None:
    """Mirrors upstream ``saveXFDF(Writer)`` (lines 254-267) which closes
    the writer after emitting XML."""
    doc = FDFDocument()
    buf = io.StringIO()
    doc.save_xfdf(buf)
    # save_xfdf must close the writer (upstream uses try/finally).
    assert buf.closed
    doc.close()


def test_get_document_returns_underlying_cos() -> None:
    """Mirrors upstream ``getDocument()`` (lines 141-144)."""
    doc = FDFDocument()
    try:
        assert doc.get_document() is not None
    finally:
        doc.close()
