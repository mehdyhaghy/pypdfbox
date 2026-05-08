from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.cos import COSDictionary, COSDocument
from pypdfbox.pdmodel.fdf import FDFDocument


def _build_pdf(objects: list[bytes], trailer: bytes, version: bytes = b"1.4") -> bytes:
    """Assemble a tiny but spec-compliant PDF.

    Mirrors the helper in ``tests/test_loader.py`` — copied here so this
    parity test module stands alone (no cross-module relative import).
    """
    out = bytearray()
    out += b"%PDF-" + version + b"\n"
    offsets: list[int] = [0]
    for body in objects:
        offsets.append(len(out))
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    xref_offset = len(out)
    out += b"xref\n"
    out += f"0 {len(offsets)}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += trailer + b"\n"
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def _minimal_pdf() -> bytes:
    return _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj",
        ],
        b"<< /Size 3 /Root 1 0 R >>",
        version=b"1.7",
    )


def _assert_minimal_document(doc: COSDocument) -> None:
    assert isinstance(doc, COSDocument)
    assert doc.get_version() == 1.7
    catalog = doc.get_catalog()
    assert isinstance(catalog, COSDictionary)
    assert catalog.get_name("Type") == "Catalog"


# ---------- Loader.load alias ----------


def test_load_alias_matches_load_pdf() -> None:
    """Loader.load must behave identically to Loader.load_pdf — feeding
    the same input through both must yield equivalent documents.
    Upstream PDFBox callers expect ``Loader.load`` to work as a synonym
    for ``Loader.loadPDF``.
    """
    pdf = _minimal_pdf()

    via_alias = Loader.load(pdf)
    try:
        _assert_minimal_document(via_alias)
    finally:
        via_alias.close()

    via_canonical = Loader.load_pdf(pdf)
    try:
        _assert_minimal_document(via_canonical)
        # Cross-check: same trailer /Root resolves the same catalog Type
        # under both entry points.
        catalog = via_canonical.get_catalog()
        assert catalog is not None
        assert catalog.get_name("Type") == "Catalog"
    finally:
        via_canonical.close()


# ---------- explicit-source entry points ----------


def test_load_pdf_from_bytes_round_trip() -> None:
    doc = Loader.load_pdf_from_bytes(_minimal_pdf())
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_bytes_rejects_non_bytes() -> None:
    with pytest.raises(TypeError, match="Loader.load_pdf_from_bytes"):
        Loader.load_pdf_from_bytes("not-bytes")  # type: ignore[arg-type]


def test_load_pdf_from_file_round_trip(tmp_path: Path) -> None:
    # No checked-in PDF fixtures yet (corpus/ is empty in the current
    # wave), so materialize one in tmp_path and feed it through the
    # path entry point. Same end-to-end round trip as a real fixture.
    pdf_path = tmp_path / "tiny.pdf"
    pdf_path.write_bytes(_minimal_pdf())

    doc = Loader.load_pdf_from_file(pdf_path)
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_file_accepts_str_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "tiny.pdf"
    pdf_path.write_bytes(_minimal_pdf())

    doc = Loader.load_pdf_from_file(str(pdf_path))
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_file_rejects_non_path() -> None:
    with pytest.raises(TypeError, match="Loader.load_pdf_from_file"):
        Loader.load_pdf_from_file(b"not-a-path")  # type: ignore[arg-type]


# ---------- deferred parsers ----------


def test_load_xfdf_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="XFDF"):
        Loader.load_xfdf(b"<?xml version='1.0'?><xfdf/>")


def test_load_fdf_delegates_to_fdf_document_loader() -> None:
    source = FDFDocument()
    source.get_catalog().get_fdf().set_status("OK")
    source.get_catalog().get_fdf().set_file("source.pdf")
    buf = io.BytesIO()
    source.save(buf)
    source.close()

    loaded = Loader.load_fdf(buf.getvalue())
    try:
        assert isinstance(loaded, FDFDocument)
        assert loaded.get_catalog().get_fdf().get_status() == "OK"
        assert loaded.get_catalog().get_fdf().get_file() == "source.pdf"
    finally:
        loaded.close()
