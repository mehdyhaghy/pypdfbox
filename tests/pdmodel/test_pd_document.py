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
    # ``add_signature`` now exists; it requires a real ``PDSignature``
    # instance — passing anything else raises TypeError (write-side
    # signature pipeline shipped in the digitalsignature cluster).
    with pytest.raises(TypeError):
        doc.add_signature(object())  # type: ignore[arg-type]


def test_construction_from_cos_document() -> None:
    cos = COSDocument()
    cos.set_trailer(COSDictionary())
    doc = PDDocument(cos)
    assert doc.get_document() is cos


def test_construction_rejects_bad_type() -> None:
    with pytest.raises(TypeError):
        PDDocument("nope")  # type: ignore[arg-type]


# ---------- import_page (cross-document deep-copy) ----------


def test_import_page_creates_independent_copy() -> None:
    """Cross-document copy: the imported page wraps a fresh COSDictionary
    that is *not* the source's underlying dict, and adds to dst's tree."""
    src = PDDocument()
    src.add_page(PDPage())
    dst = PDDocument()
    src_page = src.get_pages()[0]

    imported = dst.import_page(src_page)

    assert isinstance(imported, PDPage)
    assert imported.get_cos_object() is not src_page.get_cos_object()
    assert dst.get_number_of_pages() == 1
    # Source must remain untouched.
    assert src.get_number_of_pages() == 1


def test_import_page_resources_not_shared() -> None:
    """The /Resources dict on the imported page must be a deep copy —
    mutating one must not bleed into the other."""
    src = PDDocument()
    src_page = PDPage()
    # Force a /Resources dict so we can compare identity meaningfully.
    src_page.set_resources(COSDictionary())
    src.add_page(src_page)
    dst = PDDocument()

    imported = dst.import_page(src.get_pages()[0])

    src_res = src.get_pages()[0].get_resources().get_cos_object()
    dst_res = imported.get_resources().get_cos_object()
    assert dst_res is not src_res
    # Mutate destination — source must not see it.
    dst_res.set_item(COSName.get_pdf_name("Marker"), COSName.get_pdf_name("X"))
    assert not src_res.contains_key(COSName.get_pdf_name("Marker"))


def test_import_page_drops_parent_pointer() -> None:
    """The deep-copied page must not carry over its source /Parent — the
    page tree's add() rewires it to dst's /Pages root."""
    src = PDDocument()
    src.add_page(PDPage())
    dst = PDDocument()

    imported = dst.import_page(src.get_pages()[0])

    parent = imported.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Parent")
    )
    # /Parent is now dst's /Pages root, not src's.
    assert parent is dst.get_pages().get_cos_object()
    assert parent is not src.get_pages().get_cos_object()


def test_import_page_three_pages_in_order() -> None:
    """Importing each page of a 3-page source individually preserves order
    and leaves dst with exactly 3 pages."""
    src = PDDocument()
    pages = [PDPage(), PDPage(), PDPage()]
    for p in pages:
        src.add_page(p)
    dst = PDDocument()

    imported = [dst.import_page(src.get_pages()[i]) for i in range(3)]

    assert dst.get_number_of_pages() == 3
    for i, ip in enumerate(imported):
        assert dst.get_pages()[i].get_cos_object() is ip.get_cos_object()
        # Each imported dict is a fresh copy distinct from the source.
        assert ip.get_cos_object() is not src.get_pages()[i].get_cos_object()


def test_import_page_copies_contents_stream_bytes() -> None:
    """The /Contents stream body is deep-copied: the imported stream is a
    distinct COSStream instance carrying identical raw bytes."""
    from pypdfbox.cos import COSStream

    src = PDDocument()
    src_page = PDPage()
    contents = COSStream()
    contents.set_raw_data(b"q 1 0 0 1 0 0 cm Q\n")
    src_page.set_contents(contents)
    src.add_page(src_page)
    dst = PDDocument()

    imported = dst.import_page(src.get_pages()[0])

    src_contents = src.get_pages()[0].get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Contents")
    )
    dst_contents = imported.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Contents")
    )
    assert isinstance(dst_contents, COSStream)
    assert dst_contents is not src_contents
    assert dst_contents.get_raw_data() == b"q 1 0 0 1 0 0 cm Q\n"


# ---------- set_document_catalog ----------


def test_set_document_catalog_replaces_root() -> None:
    """``set_document_catalog`` rewires trailer/Root, drops the cached
    page-tree wrapper, and is observable via ``get_document_catalog``."""
    doc = PDDocument()
    original_root = doc.get_document().get_trailer().get_dictionary_object(  # type: ignore[union-attr]
        COSName.ROOT  # type: ignore[attr-defined]
    )

    new_catalog_dict = COSDictionary()
    new_catalog_dict.set_item(COSName.TYPE, COSName.CATALOG)  # type: ignore[attr-defined]
    new_pages = COSDictionary()
    new_pages.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    from pypdfbox.cos import COSArray as _COSArray

    new_pages.set_item(COSName.KIDS, _COSArray())  # type: ignore[attr-defined]
    new_pages.set_int(COSName.COUNT, 0)  # type: ignore[attr-defined]
    new_catalog_dict.set_item(COSName.PAGES, new_pages)  # type: ignore[attr-defined]
    from pypdfbox.pdmodel import PDDocumentCatalog as _PDC

    new_catalog = _PDC(doc, new_catalog_dict)

    doc.set_document_catalog(new_catalog)
    assert doc.get_document_catalog() is new_catalog
    swapped_root = doc.get_document().get_trailer().get_dictionary_object(  # type: ignore[union-attr]
        COSName.ROOT  # type: ignore[attr-defined]
    )
    assert swapped_root is new_catalog_dict
    assert swapped_root is not original_root


def test_set_document_catalog_rejects_none() -> None:
    doc = PDDocument()
    with pytest.raises(TypeError):
        doc.set_document_catalog(None)  # type: ignore[arg-type]


# ---------- set_encryption alias ----------


def test_set_encryption_alias_round_trips() -> None:
    """``set_encryption`` is the upstream-named alias for
    ``set_encryption_dictionary``."""
    doc = PDDocument()
    enc = COSDictionary()
    enc.set_int(COSName.get_pdf_name("V"), 4)
    doc.set_encryption(enc)
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.ENCRYPT) is enc  # type: ignore[attr-defined]
    assert doc.is_encrypted() is True


# ---------- document id seed ----------


def test_document_id_seed_default_is_none() -> None:
    doc = PDDocument()
    assert doc.get_document_id() is None


def test_document_id_seed_round_trip() -> None:
    doc = PDDocument()
    doc.set_document_id(123456789)
    assert doc.get_document_id() == 123456789
    doc.set_document_id(None)
    assert doc.get_document_id() is None


def test_document_id_seed_rejects_non_int() -> None:
    doc = PDDocument()
    with pytest.raises(TypeError):
        doc.set_document_id("not-an-int")  # type: ignore[arg-type]


# ---------- save with compress_parameters arg ----------


def test_save_accepts_compress_parameters_kwarg(tmp_path: Path) -> None:
    """``save`` accepts (and currently ignores) the upstream
    ``CompressParameters`` argument so direct ports compile."""
    out = tmp_path / "compress.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(out, compress_parameters=object())
    data = out.read_bytes()
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")


# ---------- multi-page round trip ----------


def test_multi_page_save_load_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "multi.pdf"
    src = PDDocument()
    for _ in range(5):
        src.add_page(PDPage())
    src.save(out)
    src.close()

    with PDDocument.load(out) as loaded:
        assert loaded.get_number_of_pages() == 5


# ---------- register_true_type_font_for_closing ----------


def test_register_true_type_font_for_closing_appends() -> None:
    """The lite stub appends to an internal log without raising."""
    doc = PDDocument()
    sentinel = object()
    doc.register_true_type_font_for_closing(sentinel)
    assert sentinel in doc._fonts_to_close  # noqa: SLF001 — test introspection


# ---------- resource cache ----------


def test_resource_cache_lazy_default() -> None:
    """``get_resource_cache`` lazily allocates a
    :class:`DefaultResourceCache` on first call and caches it."""
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    doc = PDDocument()
    cache = doc.get_resource_cache()
    assert isinstance(cache, DefaultResourceCache)
    assert doc.get_resource_cache() is cache


def test_resource_cache_set_round_trips_custom_value() -> None:
    """A custom cache flows through ``set_resource_cache`` without
    triggering lazy re-allocation."""
    doc = PDDocument()
    sentinel = object()
    doc.set_resource_cache(sentinel)
    assert doc.get_resource_cache() is sentinel


# ---------- close behaviour ----------


def test_save_on_closed_doc_raises() -> None:
    doc = PDDocument()
    doc.close()
    with pytest.raises(ValueError):
        doc.save(io.BytesIO())


def test_save_incremental_on_closed_doc_raises() -> None:
    doc = PDDocument()
    doc.close()
    with pytest.raises(ValueError):
        doc.save_incremental(io.BytesIO())


# ---------- get_last_signature_dictionary ----------


def test_get_last_signature_dictionary_empty_when_no_acroform() -> None:
    """No ``/AcroForm`` → no signatures → ``None``."""
    doc = PDDocument()
    assert doc.get_last_signature_dictionary() is None


def test_get_last_signature_dictionary_returns_most_recent() -> None:
    """When multiple signatures are present, the last entry of the field
    tree wins. Mirrors upstream ``getLastSignatureDictionary``."""
    from pypdfbox.cos import COSArray
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    cat = doc.get_document_catalog()
    acro = PDAcroForm(doc)
    cat.set_acro_form(acro)

    fields = COSArray()
    acro.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)

    # Build two signature fields with sig dicts in /V.
    last_sig: PDSignature | None = None
    for name in ("Signature1", "Signature2"):
        sig_field = COSDictionary()
        sig_field.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
        sig_field.set_string(COSName.get_pdf_name("T"), name)
        sig = PDSignature()
        sig.set_name(f"signer-{name}")
        sig_field.set_item(COSName.get_pdf_name("V"), sig.get_cos_object())
        fields.add(sig_field)
        last_sig = sig

    out = doc.get_last_signature_dictionary()
    assert out is not None
    assert isinstance(out, PDSignature)
    # Same backing dictionary as the last signature added.
    assert last_sig is not None
    assert out.get_cos_object() is last_sig.get_cos_object()


# ---------- document information caching ----------


def test_get_document_information_returns_cached_wrapper() -> None:
    """Repeated calls return the same wrapper instance (parity with
    upstream ``documentInformation`` caching)."""
    doc = PDDocument()
    a = doc.get_document_information()
    b = doc.get_document_information()
    assert a is b


def test_set_document_information_updates_cache() -> None:
    """``set_document_information`` swaps the cached wrapper so the next
    ``get_document_information`` returns the supplied instance."""
    from pypdfbox.pdmodel import PDDocumentInformation

    doc = PDDocument()
    # Force lazy-build of the original wrapper.
    original = doc.get_document_information()
    fresh = PDDocumentInformation()
    fresh.set_title("Fresh")
    doc.set_document_information(fresh)
    assert doc.get_document_information() is fresh
    assert doc.get_document_information() is not original
    # Trailer reflects the swap.
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.INFO) is fresh.get_cos_object()  # type: ignore[attr-defined]
