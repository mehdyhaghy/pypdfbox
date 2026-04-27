from __future__ import annotations

import io

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


def test_round_trip_through_save_and_load(tmp_path) -> None:
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
        assert loaded.get_catalog().get_fdf().get_file() == "source.pdf"
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


def test_xfdf_methods_raise_not_implemented() -> None:
    fdf = FDFDocument()
    try:
        with pytest.raises(NotImplementedError):
            fdf.set_xfdf(b"<xfdf/>")
        with pytest.raises(NotImplementedError):
            fdf.save_xfdf(io.BytesIO())
    finally:
        fdf.close()


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
