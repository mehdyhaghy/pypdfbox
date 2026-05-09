from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document import ExternalSigningSupport


def test_wave545_save_incremental_pending_signature_requires_interface() -> None:
    src = PDDocument()
    src.add_page(PDPage())
    data = io.BytesIO()
    src.save(data)
    src.close()

    with PDDocument.load(data.getvalue()) as loaded:
        loaded.add_signature(PDSignature())

        with pytest.raises(ValueError, match="requires a SignatureInterface"):
            loaded.save_incremental(io.BytesIO())


def test_wave545_external_signing_support_splices_once_and_clears_staging() -> None:
    output = io.BytesIO()
    doc = PDDocument()
    signature = PDSignature()
    doc._pending_signature = signature  # noqa: SLF001
    doc._pending_signature_interface = object()  # noqa: SLF001
    doc._pending_signature_options = object()  # noqa: SLF001
    support = ExternalSigningSupport(
        document=doc,
        output=output,
        buffer=bytearray(b"<0000>tail"),
        contents_span=(1, 5),
        byte_range=[0, 1, 5, 5],
    )

    assert support.get_content() == b"<>tail"
    assert support.get_byte_range() == [0, 1, 5, 5]

    support.set_signature(b"\xab")

    assert output.getvalue() == b"<AB00>tail"
    assert doc.get_pending_signature() is None
    assert doc.get_signature_interface() is None
    assert doc.get_signature_options() is None
    with pytest.raises(RuntimeError, match="called twice"):
        support.set_signature(b"\xcd")

    doc.close()


def test_wave545_encrypted_without_handler_returns_uncached_no_permission() -> None:
    doc = PDDocument()
    try:
        trailer = doc.get_document().get_trailer()
        assert trailer is not None
        trailer.set_item(COSName.ENCRYPT, COSDictionary())  # type: ignore[attr-defined]

        first = doc.get_current_access_permission()
        second = doc.get_current_access_permission()

        assert first is not second
        assert first.get_permission_bytes() == 0
        assert second.get_permission_bytes() == 0
        assert first.can_print() is False
        assert second.can_modify() is False
    finally:
        doc.close()
