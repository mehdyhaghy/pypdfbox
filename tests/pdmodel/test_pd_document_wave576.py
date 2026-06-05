from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName, COSStream
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


def test_wave576_constructor_adopts_loader_security_state() -> None:
    cos_doc = COSDocument()
    handler = object()
    encryption = object()
    cos_doc._loader_security_handler = handler  # noqa: SLF001
    cos_doc._loader_encryption = encryption  # noqa: SLF001
    doc = PDDocument(cos_doc)

    try:
        assert doc._security_handler is handler  # noqa: SLF001
        assert doc.get_encryption() is encryption
    finally:
        doc.close()


def test_wave576_get_document_information_creates_missing_trailer() -> None:
    cos_doc = COSDocument()
    cos_doc.set_trailer(None)
    doc = PDDocument(cos_doc)

    try:
        info = doc.get_document_information()

        trailer = cos_doc.get_trailer()
        assert trailer is not None
        assert trailer.get_dictionary_object(COSName.INFO) is info.get_cos_object()  # type: ignore[attr-defined]
    finally:
        doc.close()


def test_wave576_save_strips_encryption_and_decodes_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[PDDocument] = []

    class Writer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> Writer:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def write(self, document: PDDocument) -> None:
            writes.append(document)

    import pypdfbox.pdfwriter as pdfwriter

    monkeypatch.setattr(pdfwriter, "COSWriter", Writer)
    cos_doc = COSDocument()
    stream = COSStream()
    stream.set_raw_data(b"stream-data")
    cos_doc.get_object_from_pool(COSObjectKey(7)).set_object(stream)
    cos_doc.set_trailer(COSDictionary())
    doc = PDDocument(cos_doc)
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, COSDictionary())  # type: ignore[attr-defined]
    doc.set_all_security_to_be_removed(True)

    try:
        doc.save(io.BytesIO())

        assert writes == [doc]
        assert trailer.get_dictionary_object(COSName.ENCRYPT) is None  # type: ignore[attr-defined]
    finally:
        doc.close()


def test_wave576_save_incremental_path_target_closes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    writes: list[COSDocument] = []

    class Writer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> Writer:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def write(self, document: COSDocument) -> None:
            writes.append(document)

    import pypdfbox.pdfwriter as pdfwriter

    monkeypatch.setattr(pdfwriter, "COSWriter", Writer)
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    doc = PDDocument(cos_doc)
    target = tmp_path / "incremental.pdf"

    try:
        doc.save_incremental(target)

        assert writes == [cos_doc]
    finally:
        doc.close()


def test_wave576_save_incremental_pending_signature_signs_and_clears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Signer:
        def __init__(self) -> None:
            self.payload: bytes | None = None

        def sign(self, source: io.BytesIO) -> bytes:
            self.payload = source.read()
            return b"\x01\x02"

    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))
    signer = Signer()
    signature = PDSignature()
    output = io.BytesIO()
    monkeypatch.setattr(
        doc,
        "_render_incremental_with_placeholder",
        lambda: (bytearray(b"<0000>tail"), (1, 5), [0, 1, 5, 5]),
    )
    doc._pending_signature = signature  # noqa: SLF001
    doc._pending_signature_interface = signer  # noqa: SLF001
    doc._pending_signature_options = object()  # noqa: SLF001

    try:
        doc.save_incremental(output)

        assert signer.payload == b"<>tail"
        assert output.getvalue() == b"<0102>tail"
        assert doc.get_pending_signature() is None
        assert doc.get_signature_interface() is None
        assert doc.get_signature_options() is None
    finally:
        doc.close()


def test_wave576_render_placeholder_error_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Writer:
        data = b""

        def __init__(self, sink: io.BytesIO, *_args: object, **_kwargs: object) -> None:
            self.sink = sink

        def __enter__(self) -> Writer:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def write(self, _document: COSDocument) -> None:
            self.sink.write(self.data)

    import pypdfbox.pdfwriter as pdfwriter

    monkeypatch.setattr(pdfwriter, "COSWriter", Writer)
    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))
    doc._pending_signature = PDSignature()  # noqa: SLF001

    try:
        Writer.data = b"no contents here"
        with pytest.raises(RuntimeError, match="Contents placeholder not found"):
            doc._render_incremental_with_placeholder()  # noqa: SLF001

        zero_run = b"<" + b"0" * doc._CONTENTS_PLACEHOLDER_HEX_LEN + b">"  # noqa: SLF001
        Writer.data = b"/ByteRange [1 2 3 4] " + zero_run
        with pytest.raises(RuntimeError, match="ByteRange placeholder not found"):
            doc._render_incremental_with_placeholder()  # noqa: SLF001
    finally:
        doc.close()


def test_wave576_render_placeholder_rejects_byte_range_that_exceeds_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Writer:
        def __init__(self, sink: io.BytesIO, *_args: object, **_kwargs: object) -> None:
            self.sink = sink

        def __enter__(self) -> Writer:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def write(self, _document: COSDocument) -> None:
            zero_run = b"<" + b"0" * doc._CONTENTS_PLACEHOLDER_HEX_LEN + b">"  # noqa: SLF001
            self.sink.write(b"prefix " + zero_run + b" [0 9 9 9]")

    import pypdfbox.pdfwriter as pdfwriter

    monkeypatch.setattr(pdfwriter, "COSWriter", Writer)
    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))
    doc._pending_signature = PDSignature()  # noqa: SLF001
    monkeypatch.setattr(doc, "_BYTERANGE_SLOT_WIDTH", 1)

    try:
        with pytest.raises(RuntimeError, match="exceeds placeholder width"):
            doc._render_incremental_with_placeholder()  # noqa: SLF001
    finally:
        doc.close()


def test_wave576_get_version_uses_header_when_catalog_access_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = PDDocument()
    monkeypatch.setattr(
        doc,
        "get_document_catalog",
        lambda: (_ for _ in ()).throw(RuntimeError("bad catalog")),
    )

    try:
        assert doc.get_version() == pytest.approx(1.4)
    finally:
        doc.close()


def test_wave576_decrypt_sets_stream_handlers_and_invalidates_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, bytes, object]] = []

    class Handler:
        def __init__(self, encryption: object) -> None:
            self.encryption = encryption

        def prepare_for_decryption(
            self,
            encryption: object,
            document_id: bytes,
            material: object,
        ) -> None:
            calls.append((encryption, document_id, material))

    import pypdfbox.pdmodel.encryption.standard_security_handler as ssh_module

    monkeypatch.setattr(ssh_module, "StandardSecurityHandler", Handler)
    cos_doc = COSDocument()
    cos_doc.set_trailer(COSDictionary())
    trailer = cos_doc.get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, COSDictionary())  # type: ignore[attr-defined]
    ids = COSArray()
    from pypdfbox.cos import COSString

    ids.add(COSString(b"file-id"))
    cos_doc.set_document_id(ids)
    stream = COSStream()
    cos_obj = cos_doc.get_object_from_pool(COSObjectKey(9, 2))
    cos_obj.set_object(stream)
    doc = PDDocument(cos_doc)
    doc._access_permission = object()  # noqa: SLF001

    try:
        doc.decrypt("secret")
        assert calls[0][1] == b"file-id"

        calls.clear()
        doc._access_permission = object()  # noqa: SLF001
        doc.decrypt(b"secret")

        assert calls
        assert calls[0][1] == b"file-id"
        assert doc._security_handler is not None  # noqa: SLF001
        assert doc._access_permission is None  # noqa: SLF001
    finally:
        doc.close()


def test_wave576_add_signature_creates_fields_array_when_missing() -> None:
    from pypdfbox.pdmodel import PDPage

    doc = PDDocument()
    # add_signature refuses a page-less document upstream.
    doc.add_page(PDPage())
    acro_form = doc.get_document_catalog().get_acro_form()
    if acro_form is not None:
        acro_form.get_cos_object().remove_item(COSName.get_pdf_name("Fields"))
    signature = PDSignature()

    try:
        doc.add_signature(signature, options=SimpleNamespace(name="opts"))

        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form is not None
        fields = acro_form.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        assert isinstance(fields, COSArray)
        assert fields.size() == 1
        assert doc.get_pending_signature() is signature
        assert doc.has_pending_signature() is True
        assert doc.is_signature_added() is True
    finally:
        doc.close()


def test_wave576_add_signature_replaces_malformed_fields_entry() -> None:
    from pypdfbox.pdmodel import PDPage

    doc = PDDocument()
    # add_signature refuses a page-less document upstream.
    doc.add_page(PDPage())
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    acro_form = PDAcroForm(doc)
    acro_form.get_cos_object().set_item(
        COSName.get_pdf_name("Fields"), COSName.get_pdf_name("Broken")
    )
    doc.get_document_catalog().set_acro_form(acro_form)

    try:
        doc.add_signature(PDSignature())

        fields = acro_form.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        assert isinstance(fields, COSArray)
        assert fields.size() == 1
    finally:
        doc.close()


def test_wave576_repr_handles_page_count_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = PDDocument()
    monkeypatch.setattr(
        doc,
        "get_number_of_pages",
        lambda: (_ for _ in ()).throw(RuntimeError("broken pages")),
    )

    try:
        assert "pages=?" in repr(doc)
    finally:
        doc.close()
