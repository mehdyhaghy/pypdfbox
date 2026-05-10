from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.pdmodel.fdf import FDFCatalog, FDFDocument


def test_default_constructor_builds_skeleton() -> None:
    fdf = FDFDocument()
    cos_doc = fdf.get_document()
    assert isinstance(cos_doc, COSDocument)
    trailer = cos_doc.get_trailer()
    assert trailer is not None
    catalog = fdf.get_catalog()
    assert isinstance(catalog, FDFCatalog)
    # Skeleton catalog has an empty /FDF dict already.
    assert catalog.get_fdf() is not None


def test_get_catalog_returns_same_wrapper() -> None:
    fdf = FDFDocument()
    a = fdf.get_catalog()
    b = fdf.get_catalog()
    assert a is b


def test_round_trip_through_save_and_load(tmp_path: Path) -> None:
    fdf = FDFDocument()
    cat = fdf.get_catalog()
    cat.get_fdf().set_status("OK")
    cat.get_fdf().set_file("source.pdf")
    out = tmp_path / "out.fdf"
    fdf.save(out)
    fdf.close()

    loaded = FDFDocument.load(out)
    try:
        assert loaded.get_catalog().get_fdf().get_status() == "OK"
        assert loaded.get_catalog().get_fdf().get_file_path() == "source.pdf"
    finally:
        loaded.close()


def test_save_to_bytesio() -> None:
    fdf = FDFDocument()
    fdf.get_catalog().get_fdf().set_status("hello")
    buf = io.BytesIO()
    fdf.save(buf)
    fdf.close()
    data = buf.getvalue()
    assert data.startswith(b"%PDF-")  # FDF shares the PDF wire header
    assert b"%%EOF" in data


def test_close_is_idempotent() -> None:
    fdf = FDFDocument()
    fdf.close()
    fdf.close()
    assert fdf.is_closed()


def test_context_manager_closes() -> None:
    with FDFDocument() as fdf:
        assert not fdf.is_closed()
    assert fdf.is_closed()


def test_save_after_close_raises() -> None:
    fdf = FDFDocument()
    fdf.close()
    with pytest.raises(ValueError):
        fdf.save(io.BytesIO())


def test_set_xfdf_still_unsupported() -> None:
    """XFDF ingest still requires a SAX/DOM front-end (deferred wave)."""
    fdf = FDFDocument()
    try:
        with pytest.raises(NotImplementedError):
            fdf.set_xfdf(b"<xfdf/>")
    finally:
        fdf.close()


def test_save_xfdf_writes_xml_to_text_stream() -> None:
    fdf = FDFDocument()
    captured: list[str] = []

    class _CapturingWriter(io.StringIO):
        def close(self) -> None:  # type: ignore[override]
            captured.append(self.getvalue())
            super().close()

    buf = _CapturingWriter()
    fdf.save_xfdf(buf)
    # save_xfdf must close the writer to mirror upstream behaviour.
    assert buf.closed
    text = captured[0]
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<xfdf" in text
    assert text.rstrip().endswith("</xfdf>")
    fdf.close()


def test_save_xfdf_writes_xml_to_path(tmp_path: Path) -> None:
    fdf = FDFDocument()
    out = tmp_path / "out.xfdf"
    fdf.save_xfdf(out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<xfdf" in text
    fdf.close()


def test_write_xml_emits_xfdf_envelope() -> None:
    fdf = FDFDocument()
    buf = io.StringIO()
    fdf.write_xml(buf)
    text = buf.getvalue()
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n')
    assert '<xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve">' in text
    assert text.rstrip().endswith("</xfdf>")
    fdf.close()


def test_set_catalog_replaces_root() -> None:
    fdf = FDFDocument()
    new_cat = FDFCatalog()
    fdf.set_catalog(new_cat)
    assert fdf.get_catalog() is new_cat
    # And the trailer's /Root must now point at the new catalog's COS dict.
    from pypdfbox.cos import COSName

    trailer = fdf.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.get_pdf_name("Root")) is (
        new_cat.get_cos_object()
    )
    fdf.close()


def test_save_xfdf_after_close_raises() -> None:
    fdf = FDFDocument()
    fdf.close()
    with pytest.raises(ValueError):
        fdf.save_xfdf(io.StringIO())


def test_constructor_rejects_unknown_type() -> None:
    with pytest.raises(TypeError):
        FDFDocument("not a cos doc")  # type: ignore[arg-type]


def test_constructor_accepts_existing_cos_document() -> None:
    cos = COSDocument()
    fdf = FDFDocument(cos)
    # Constructor with an existing COSDocument should NOT replace the
    # trailer (it's a wrapping operation, not initialization).
    assert fdf.get_document() is cos
    # Catalog accessor must still synthesize a /Root if missing.
    cat = fdf.get_catalog()
    assert cat is not None
    fdf.close()
