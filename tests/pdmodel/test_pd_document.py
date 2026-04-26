from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.pdmodel import PDDocumentCatalog, PDPageTree


def _save_to_bytes(doc: PDDocument) -> bytes:
    sink = io.BytesIO()
    doc.save(sink)
    return sink.getvalue()


def test_default_constructor_empty_saveable() -> None:
    doc = PDDocument()
    assert isinstance(doc.get_document(), COSDocument)
    assert isinstance(doc.get_document_catalog(), PDDocumentCatalog)
    assert isinstance(doc.get_pages(), PDPageTree)
    assert doc.get_number_of_pages() == 0
    out = _save_to_bytes(doc)
    assert out.startswith(b"%PDF-1.4\n")
    assert b"%%EOF" in out


def test_load_round_trips_empty_document() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    written = _save_to_bytes(doc)
    doc.close()

    with PDDocument.load(written) as loaded:
        assert loaded.get_number_of_pages() == 1


def test_load_from_path(tmp_path: Path) -> None:
    src = PDDocument()
    src.add_page(PDPage())
    out_path = tmp_path / "doc.pdf"
    src.save(out_path)
    src.close()

    with PDDocument.load(out_path) as loaded:
        assert loaded.get_number_of_pages() == 1


def test_save_to_path_writes_pdf(tmp_path: Path) -> None:
    out_path = tmp_path / "out.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(out_path)
    data = out_path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")


def test_add_page_increments_count() -> None:
    doc = PDDocument()
    assert doc.get_number_of_pages() == 0
    doc.add_page(PDPage())
    assert doc.get_number_of_pages() == 1
    doc.add_page(PDPage())
    assert doc.get_number_of_pages() == 2


def test_remove_page_by_reference() -> None:
    doc = PDDocument()
    p1 = PDPage()
    p2 = PDPage()
    doc.add_page(p1)
    doc.add_page(p2)
    doc.remove_page(p1)
    assert doc.get_number_of_pages() == 1


def test_remove_page_by_index() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    doc.remove_page(0)
    assert doc.get_number_of_pages() == 1


def test_save_incremental_requires_source() -> None:
    """A synthesised document has no source — incremental save must fail
    with the same error path as upstream."""
    doc = PDDocument()
    doc.add_page(PDPage())
    with pytest.raises(ValueError, match="requires a loaded document"):
        doc.save_incremental(io.BytesIO())


def test_save_incremental_round_trip(tmp_path: Path) -> None:
    """A loaded document with no dirty objects should produce
    byte-for-byte-identical output (matches upstream incremental contract)."""
    # First make a fresh saveable document.
    src = PDDocument()
    src.add_page(PDPage())
    src_bytes = _save_to_bytes(src)
    src.close()

    # Load it back, then save incrementally with no changes.
    with PDDocument.load(src_bytes) as loaded:
        sink = io.BytesIO()
        loaded.save_incremental(sink)
        assert sink.getvalue() == src_bytes


def test_context_manager_closes_underlying_document() -> None:
    doc = PDDocument()
    cos = doc.get_document()
    with doc:
        assert not cos.is_closed()
    assert cos.is_closed()


def test_close_idempotent() -> None:
    doc = PDDocument()
    doc.close()
    doc.close()  # second call must not raise


def test_get_document_information_creates_when_absent() -> None:
    """Cluster #2: ``get_document_information`` always returns a wrapper;
    it auto-creates the ``/Info`` dict on the trailer when missing."""
    from pypdfbox.pdmodel import PDDocumentInformation

    doc = PDDocument()
    info = doc.get_document_information()
    assert isinstance(info, PDDocumentInformation)
    # The new info dict was wired into the trailer.
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.INFO) is info.get_cos_object()  # type: ignore[attr-defined]


def test_get_document_information_returns_existing_dict() -> None:
    doc = PDDocument()
    info = COSDictionary()
    info.set_string(COSName.get_pdf_name("Title"), "Hello")
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.INFO, info)  # type: ignore[attr-defined]
    wrapper = doc.get_document_information()
    assert wrapper.get_cos_object() is info
    assert wrapper.get_title() == "Hello"


def test_version_default_is_1_4() -> None:
    doc = PDDocument()
    assert doc.get_version() == 1.4


def test_set_version_round_trip() -> None:
    doc = PDDocument()
    doc.set_version(1.7)
    assert doc.get_version() == 1.7


def test_set_version_does_not_downgrade() -> None:
    doc = PDDocument()
    doc.set_version(1.7)
    doc.set_version(1.4)  # ignored
    assert doc.get_version() == 1.7


def test_is_encrypted_false_on_fresh_doc() -> None:
    doc = PDDocument()
    assert doc.is_encrypted() is False


def test_is_encrypted_true_when_encrypt_dict_present() -> None:
    doc = PDDocument()
    enc = COSDictionary()
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, enc)  # type: ignore[attr-defined]
    assert doc.is_encrypted() is True


def test_security_removal_flag_round_trip() -> None:
    doc = PDDocument()
    assert doc.is_all_security_to_be_removed() is False
    doc.set_all_security_to_be_removed(True)
    assert doc.is_all_security_to_be_removed() is True


def test_stubs_raise_with_cluster_pointer() -> None:
    doc = PDDocument()
    # ``get_encryption`` now returns ``None`` for unencrypted docs (no
    # raise) — encryption wiring landed in the security cluster.
    assert doc.get_encryption() is None
    # ``protect`` accepts only StandardProtectionPolicy; passing a stray
    # object still raises (NotImplementedError for non-standard policy
    # shapes such as the public-key handler).
    with pytest.raises(NotImplementedError):
        doc.protect(object())
    with pytest.raises(NotImplementedError):
        doc.import_page(PDPage())
    with pytest.raises(NotImplementedError):
        doc.add_signature(object())


def test_construction_from_cos_document() -> None:
    cos = COSDocument()
    cos.set_trailer(COSDictionary())
    doc = PDDocument(cos)
    assert doc.get_document() is cos


def test_construction_rejects_bad_type() -> None:
    with pytest.raises(TypeError):
        PDDocument("nope")  # type: ignore[arg-type]
