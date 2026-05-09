from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDDocument


def test_wave566_encryption_dictionary_round_trips_raw_wrapper_and_clear() -> None:
    doc = PDDocument()
    raw = COSDictionary()
    wrapper = SimpleNamespace(get_cos_object=lambda: raw)

    try:
        doc.set_encryption_dictionary(raw)
        assert doc.get_document().get_encryption_dictionary() is raw
        assert doc.get_encryption() is not None

        doc.set_encryption_dictionary(wrapper)
        assert doc.get_document().get_encryption_dictionary() is raw
        assert doc.get_encryption() is wrapper

        doc.clear_encryption_dictionary()
        assert doc.get_document().get_encryption_dictionary() is None
        assert doc.get_encryption() is None
    finally:
        doc.close()


def test_wave566_decrypt_returns_when_not_encrypted_or_encrypt_is_malformed() -> None:
    doc = PDDocument()
    try:
        doc.decrypt("ignored")

        trailer = doc.get_document().get_trailer()
        assert trailer is not None
        trailer.set_item(COSName.ENCRYPT, COSName.get_pdf_name("Bad"))  # type: ignore[attr-defined]

        doc.decrypt(b"ignored")

        assert doc.get_encryption() is None
    finally:
        doc.close()


def test_wave566_requires_full_save_notices_dirty_resolved_object() -> None:
    inner = COSDictionary()
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    cos_obj = cos_doc.get_object_from_pool(COSObjectKey(12))
    cos_obj.set_object(inner)
    doc = PDDocument(cos_doc)

    try:
        assert doc.requires_full_save() is True

        inner.set_needs_to_be_updated(True)

        assert doc.requires_full_save() is False
    finally:
        doc.close()


def test_wave566_signature_dictionary_helpers_use_signature_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = SimpleNamespace(get_signature=lambda: None)
    second_sig = object()
    second = SimpleNamespace(get_signature=lambda: second_sig)
    third_sig = object()
    third = SimpleNamespace(get_signature=lambda: third_sig)
    doc = PDDocument()
    monkeypatch.setattr(doc, "get_signature_fields", lambda: [first, second, third])

    try:
        assert doc.get_signature_dictionaries() == [second_sig, third_sig]
        assert doc.has_signatures() is True
        assert doc.get_last_signature_dictionary() is third_sig
    finally:
        doc.close()


def test_wave566_signature_dictionary_helpers_handle_empty_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = PDDocument()
    monkeypatch.setattr(doc, "get_signature_fields", lambda: [])

    try:
        assert doc.get_signature_dictionaries() == []
        assert doc.has_signatures() is False
        assert doc.get_last_signature_dictionary() is None
    finally:
        doc.close()


def test_wave566_write_bytes_to_path_and_binary_stream(tmp_path) -> None:
    target = tmp_path / "out.pdf"

    PDDocument._write_bytes_to_target(b"path", target)  # noqa: SLF001
    stream = io.BytesIO()
    PDDocument._write_bytes_to_target(b"stream", stream)  # noqa: SLF001

    assert target.read_bytes() == b"path"
    assert stream.getvalue() == b"stream"


def test_wave566_fonts_to_close_returns_live_registration_list() -> None:
    doc = PDDocument()
    font = object()

    try:
        doc.register_true_type_font_for_closing(font)
        fonts = doc.get_fonts_to_close()

        assert fonts == [font]
        fonts.clear()
        assert doc.get_fonts_to_close() == []
    finally:
        doc.close()


def test_wave566_split_and_extract_reject_closed_document() -> None:
    doc = PDDocument()
    doc.close()

    with pytest.raises(ValueError, match="closed PDDocument"):
        doc.split()
    with pytest.raises(ValueError, match="closed PDDocument"):
        doc.extract_pages(1, 1)
