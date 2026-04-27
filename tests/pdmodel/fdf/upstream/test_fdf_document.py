"""Ported from upstream PDFBox FDFDocumentTest-shape coverage.

Source PDFBox source tree was not available locally at port time, so this
file mirrors the documented public API of ``FDFDocument`` rather than
translating a JUnit file line-by-line. When the upstream test class is
located, replace this file (drop a row in PROVENANCE.md for it).
"""

from __future__ import annotations

import io

from pypdfbox.pdmodel.fdf import FDFDocument, FDFField


def test_new_fdf_document_has_catalog_and_fdf_dict() -> None:
    """Mirrors ``new FDFDocument()`` upstream — must produce a saveable
    skeleton with a non-null catalog and an empty /FDF sub-dictionary."""
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
    """Mirrors upstream ``saveFDF`` / ``loadFDF`` round-trip."""
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
