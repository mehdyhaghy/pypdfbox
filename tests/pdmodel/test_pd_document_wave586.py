from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


def test_wave586_constructor_rejects_unknown_source_type() -> None:
    with pytest.raises(TypeError, match="expected COSDocument or None"):
        PDDocument(object())  # type: ignore[arg-type]


def test_wave586_remove_page_by_reference() -> None:
    doc = PDDocument()
    page = PDPage()

    try:
        doc.add_page(page)
        doc.remove_page(page)

        assert doc.get_number_of_pages() == 0
    finally:
        doc.close()


def test_wave586_save_path_target_closes_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
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
    doc = PDDocument()

    try:
        doc.save(tmp_path / "saved.pdf")

        assert writes == [doc]
    finally:
        doc.close()


def test_wave586_save_incremental_closed_document_raises() -> None:
    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))
    doc.close()

    with pytest.raises(ValueError, match="closed PDDocument"):
        doc.save_incremental(io.BytesIO())


def test_wave586_render_placeholder_success_pads_byte_range(
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
            self.sink.write(b"head <0000> tail [0 999 999 999] end")

    import pypdfbox.pdfwriter as pdfwriter

    monkeypatch.setattr(pdfwriter, "COSWriter", Writer)
    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))
    doc._pending_signature = PDSignature()  # noqa: SLF001
    monkeypatch.setattr(doc, "_CONTENTS_PLACEHOLDER_HEX_LEN", 4)
    monkeypatch.setattr(doc, "_BYTERANGE_SLOT_WIDTH", 3)

    try:
        rendered, contents_span, byte_range = doc._render_incremental_with_placeholder()  # noqa: SLF001

        assert contents_span == (6, 10)
        assert byte_range == [0, 6, 10, len(rendered) - 10]
        assert b"[0 6 10 26    ]" in rendered
    finally:
        doc.close()


def test_wave586_encryption_alias_and_unsupported_policy() -> None:
    doc = PDDocument()
    encryption = COSDictionary()

    try:
        doc.set_encryption(encryption)

        trailer = doc.get_document().get_trailer()
        assert trailer is not None
        assert trailer.get_dictionary_object(COSName.ENCRYPT) is encryption  # type: ignore[attr-defined]
        with pytest.raises(NotImplementedError, match="only StandardProtectionPolicy"):
            doc.protect(object())
    finally:
        doc.close()


def test_wave586_resource_cache_and_signature_absence_helpers() -> None:
    doc = PDDocument()
    cache = object()
    font = object()

    try:
        assert doc.get_resource_cache() is doc.get_resource_cache()
        doc.set_resource_cache(cache)
        assert doc.get_resource_cache() is cache
        assert doc.get_signature_fields() == []
        assert doc.requires_full_save() is True
        assert doc.is_locked_by_outline_destinations() is False

        doc.register_true_type_font_for_closing(font)
        assert doc.get_fonts_to_close() == [font]
    finally:
        doc.close()


def test_wave586_external_signing_guards_and_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))

    try:
        with pytest.raises(ValueError, match="prior add_signature"):
            doc.save_incremental_for_external_signing(io.BytesIO())

        signature = PDSignature()
        output = io.BytesIO()
        doc._pending_signature = signature  # noqa: SLF001
        doc._pending_signature_interface = object()  # noqa: SLF001
        doc._pending_signature_options = object()  # noqa: SLF001
        monkeypatch.setattr(
            doc,
            "_render_incremental_with_placeholder",
            lambda: (bytearray(b"<0000>tail"), (1, 5), [0, 1, 5, 5]),
        )

        support = doc.save_incremental_for_external_signing(output)

        assert support.get_content() == b"<>tail"
        assert support.get_byte_range() == [0, 1, 5, 5]
        support.set_signature(b"\x0a")
        assert output.getvalue() == b"<0A00>tail"
        assert doc.get_pending_signature() is None
        with pytest.raises(RuntimeError, match="called twice"):
            support.set_signature(b"\x0b")
    finally:
        doc.close()


def test_wave586_closed_external_signing_raises() -> None:
    doc = PDDocument(COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")))
    doc._pending_signature = PDSignature()  # noqa: SLF001
    doc.close()

    with pytest.raises(ValueError, match="closed PDDocument"):
        doc.save_incremental_for_external_signing(io.BytesIO())


def test_wave586_split_extract_and_merge_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    split_calls: list[tuple[str, object]] = []
    extracted = PDDocument()

    class Splitter:
        def set_split_at_page(self, every: int) -> None:
            split_calls.append(("every", every))

        def split(self, document: PDDocument) -> list[PDDocument]:
            split_calls.append(("doc", document))
            return [document]

    class Extractor:
        def __init__(self, document: PDDocument, start: int, end: int) -> None:
            split_calls.append(("extract", (document, start, end)))

        def extract(self) -> PDDocument:
            return extracted

    class Merger:
        def __init__(self) -> None:
            self.count = 0

        def append_document(self, result: PDDocument, source: PDDocument) -> None:
            split_calls.append(("merge", (result, source)))
            self.count += 1

    import pypdfbox.multipdf.page_extractor as extractor_module
    import pypdfbox.multipdf.pdf_merger_utility as merger_module
    import pypdfbox.multipdf.splitter as splitter_module

    monkeypatch.setattr(splitter_module, "Splitter", Splitter)
    monkeypatch.setattr(extractor_module, "PageExtractor", Extractor)
    monkeypatch.setattr(merger_module, "PDFMergerUtility", Merger)
    doc = PDDocument()
    other = PDDocument()
    merged: PDDocument | None = None

    try:
        assert doc.split(every=2) == [doc]
        assert doc.extract_pages(3, 4) is extracted
        merged = PDDocument.merge(doc, other)

        assert isinstance(merged, PDDocument)
        assert ("every", 2) in split_calls
        assert ("extract", (doc, 3, 4)) in split_calls
        assert any(
            label == "merge" and value[1] is other for label, value in split_calls
        )
    finally:
        if merged is not None:
            merged.close()
        doc.close()
        other.close()
        extracted.close()


def test_wave586_get_signature_fields_filters_signature_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.pdmodel.interactive.form.pd_signature_field as sig_field_module

    class FakeSignatureField:
        pass

    sig_field = FakeSignatureField()
    acro_form = SimpleNamespace(get_field_tree=lambda: [object(), sig_field])
    catalog = SimpleNamespace(get_acro_form=lambda: acro_form)
    doc = PDDocument()
    monkeypatch.setattr(sig_field_module, "PDSignatureField", FakeSignatureField)
    monkeypatch.setattr(doc, "get_document_catalog", lambda: catalog)

    try:
        assert doc.get_signature_fields() == [sig_field]
    finally:
        doc.close()
