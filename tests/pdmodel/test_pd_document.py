from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

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
    doc.close()


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
    doc.close()


def test_remove_page_by_reference() -> None:
    doc = PDDocument()
    p1 = PDPage()
    p2 = PDPage()
    doc.add_page(p1)
    doc.add_page(p2)
    doc.remove_page(p1)
    assert doc.get_number_of_pages() == 1
    doc.close()


def test_remove_page_by_index() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    doc.remove_page(0)
    assert doc.get_number_of_pages() == 1
    doc.close()


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
    # ``protect`` accepts ``StandardProtectionPolicy`` or
    # ``PublicKeyProtectionPolicy``; passing a stray object surfaces a
    # ``TypeError`` (caller bug, no longer a deferred-feature marker).
    with pytest.raises(TypeError):
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


# ---------- get_fonts_to_subset ----------


def test_get_fonts_to_subset_returns_empty_set_by_default() -> None:
    """Fresh documents start with an empty subset queue."""
    doc = PDDocument()
    fonts = doc.get_fonts_to_subset()
    assert isinstance(fonts, set)
    assert fonts == set()


def test_get_fonts_to_subset_returns_live_backing_store() -> None:
    """Mirrors upstream: the returned set is the document's own backing
    store, so callers may mutate it in place and subsequent calls see
    the same set."""
    doc = PDDocument()
    fonts = doc.get_fonts_to_subset()
    sentinel = object()
    fonts.add(sentinel)
    assert doc.get_fonts_to_subset() is fonts
    assert sentinel in doc.get_fonts_to_subset()


# ---------- set_encryption_dictionary(None) ----------


def test_set_encryption_dictionary_none_clears_trailer_and_cache() -> None:
    """Passing ``None`` drops ``/Encrypt`` from the trailer and clears the
    cached :class:`PDEncryption` wrapper. Mirrors upstream
    ``setEncryptionDictionary(null)``."""
    doc = PDDocument()
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name("Standard"))
    doc.set_encryption_dictionary(enc)
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_item(COSName.get_pdf_name("Encrypt")) is enc

    doc.set_encryption_dictionary(None)
    assert trailer.get_item(COSName.get_pdf_name("Encrypt")) is None
    assert doc._encryption is None  # noqa: SLF001 — test introspection


def test_set_encryption_dictionary_none_is_noop_without_trailer() -> None:
    """Clearing on a document that has no /Encrypt entry must not raise."""
    doc = PDDocument()
    # No /Encrypt has ever been set — clearing should silently succeed.
    doc.set_encryption_dictionary(None)
    assert doc._encryption is None  # noqa: SLF001 — test introspection


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
    doc.close()


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
    doc.close()


# ---------- document information caching ----------


def test_get_document_information_returns_cached_wrapper() -> None:
    """Repeated calls return the same wrapper instance (parity with
    upstream ``documentInformation`` caching)."""
    doc = PDDocument()
    a = doc.get_document_information()
    b = doc.get_document_information()
    assert a is b
    doc.close()


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
    doc.close()


# ---------- save_incremental(objects_to_write=...) ----------


def test_save_incremental_objects_to_write_marks_dirty() -> None:
    """The second-overload set of ``COSDictionary`` instances must be
    marked ``needs_to_be_updated`` so the writer emits them in the
    appended xref. Mirrors upstream
    ``saveIncremental(OutputStream, Set<COSDictionary>)``."""
    src = PDDocument()
    src.add_page(PDPage())
    src_bytes = _save_to_bytes(src)
    src.close()

    with PDDocument.load(src_bytes) as loaded:
        # Reach down into a dict that is NOT already flagged dirty — the
        # /Info dict on a fresh load has no needs_to_be_updated bit.
        info_dict = loaded.get_document_information().get_cos_object()
        assert info_dict.is_needs_to_be_updated() is False
        loaded.save_incremental(io.BytesIO(), {info_dict})
        # After the call, the supplied dict is flagged dirty (the writer
        # consumed it via the same flag).
        assert info_dict.is_needs_to_be_updated() is True


def test_save_incremental_objects_to_write_rejects_non_dict() -> None:
    """The set must contain ``COSDictionary`` instances only — anything
    else surfaces a TypeError before the writer engages."""
    from pypdfbox.cos import COSArray

    src = PDDocument()
    src.add_page(PDPage())
    src_bytes = _save_to_bytes(src)
    src.close()

    with (
        PDDocument.load(src_bytes) as loaded,
        pytest.raises(TypeError, match="COSDictionary"),
    ):
        # COSArray is not a COSDictionary — must reject.
        loaded.save_incremental(io.BytesIO(), {COSArray()})  # type: ignore[arg-type]


def test_save_incremental_objects_to_write_none_is_default() -> None:
    """Passing ``None`` (the default) preserves the original
    single-argument behaviour."""
    src = PDDocument()
    src.add_page(PDPage())
    src_bytes = _save_to_bytes(src)
    src.close()

    with PDDocument.load(src_bytes) as loaded:
        sink = io.BytesIO()
        loaded.save_incremental(sink, None)
        # Same byte-for-byte round-trip as the no-arg form.
        assert sink.getvalue() == src_bytes


# ---------- set_version no-op on equal ----------


def test_set_version_no_op_on_equal() -> None:
    """Setting the version to the value already in effect is a no-op —
    no catalog mutation, no header mutation. Mirrors upstream's
    ``Float.compare(newVersion, currentVersion) == 0`` early exit."""
    doc = PDDocument()
    # Default version is 1.4 — but the catalog gets a /Version entry from
    # the minimal skeleton. Confirm baseline first.
    assert doc.get_version() == 1.4
    catalog_dict = doc.get_document_catalog().get_cos_object()
    version_before = catalog_dict.get_dictionary_object(
        COSName.get_pdf_name("Version")
    )
    # Bump from 1.4 to 1.4 — exit-on-equal must not even touch the catalog.
    doc.set_version(1.4)
    version_after = catalog_dict.get_dictionary_object(
        COSName.get_pdf_name("Version")
    )
    # Identity-stable: no replacement happened.
    assert version_after is version_before
    doc.close()


# ---------- add_signature one-shot guard ----------


def test_add_signature_rejects_second_call() -> None:
    """A second ``add_signature`` on the same document raises — mirrors
    upstream ``IllegalStateException("Only one signature may be added in
    a document")``. Surfaced as ``ValueError`` for symmetry with other
    PDDocument guards."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_signature(PDSignature())
    with pytest.raises(ValueError, match="Only one signature"):
        doc.add_signature(PDSignature())
    doc.close()


# ---------- Wave 194: class constants + protect parity + access cache ----------


def test_default_version_constant_exposes_1_4() -> None:
    """``DEFAULT_VERSION`` mirrors upstream's hard-coded ``"1.4"`` literal."""
    assert PDDocument.DEFAULT_VERSION == 1.4


def test_default_version_constant_drives_empty_skeleton() -> None:
    """The empty-document constructor stamps the catalog ``/Version`` with
    :attr:`PDDocument.DEFAULT_VERSION`. Round-trip through the literal so a
    future bump (e.g. to 1.7) reaches the catalog without code changes."""
    doc = PDDocument()
    catalog_dict = doc.get_document_catalog().get_cos_object()
    version = catalog_dict.get_dictionary_object(COSName.get_pdf_name("Version"))
    assert version is not None
    expected = f"{PDDocument.DEFAULT_VERSION:.1f}"
    assert isinstance(version, COSName)
    assert version.get_name() == expected
    doc.close()


def test_reserve_byte_range_matches_upstream() -> None:
    """``RESERVE_BYTE_RANGE`` equals the upstream Java
    ``int[] {0, 1000000000, 1000000000, 1000000000}`` literal."""
    assert PDDocument.RESERVE_BYTE_RANGE == (0, 1_000_000_000, 1_000_000_000, 1_000_000_000)
    # Tuple shape is (start1, len1, start2, len2) — 4 entries.
    assert len(PDDocument.RESERVE_BYTE_RANGE) == 4


def test_protect_clears_security_removal_flag(caplog: pytest.LogCaptureFixture) -> None:
    """``protect()`` warns and force-clears
    ``set_all_security_to_be_removed(True)`` (mirrors upstream's
    ``setAllSecurityToBeRemoved(false)`` reset inside ``protect``)."""
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    doc = PDDocument()
    doc.set_all_security_to_be_removed(True)
    assert doc.is_all_security_to_be_removed() is True

    policy = StandardProtectionPolicy("owner-pwd", "user-pwd", None)
    with caplog.at_level("WARNING", logger="pypdfbox.pdmodel.pd_document"):
        doc.protect(policy)

    assert doc.is_all_security_to_be_removed() is False
    # A warning should have been logged about the conflict.
    assert any("protect" in rec.message.lower() for rec in caplog.records)
    doc.close()


def test_protect_no_warning_when_flag_not_set(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``protect()`` does NOT log when the security-removal flag was never
    set — only the conflicting case warns."""
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    doc = PDDocument()
    policy = StandardProtectionPolicy("owner-pwd", "user-pwd", None)
    with caplog.at_level("WARNING", logger="pypdfbox.pdmodel.pd_document"):
        doc.protect(policy)
    assert not caplog.records
    doc.close()


def test_get_current_access_permission_caches_result() -> None:
    """Repeated ``get_current_access_permission`` calls return the same
    instance — mirrors upstream's cached ``accessPermission`` field."""
    doc = PDDocument()
    first = doc.get_current_access_permission()
    second = doc.get_current_access_permission()
    assert first is second
    doc.close()


def test_get_current_access_permission_uncached_when_encrypted_undecoded() -> None:
    """An encrypted-but-not-yet-decrypted doc returns a fresh no-permission
    object on each call — the cache only kicks in for owner-level / handler-
    derived results so a follow-up ``decrypt()`` can still upgrade."""
    from pypdfbox.cos import COSDictionary as _COSDict
    from pypdfbox.pdmodel.encryption.access_permission import AccessPermission

    doc = PDDocument()
    # Inject a synthetic /Encrypt dict so ``is_encrypted`` flips True without
    # actually decrypting anything.
    enc = _COSDict()
    enc.set_string(COSName.get_pdf_name("Filter"), "Standard")
    enc.set_int(COSName.get_pdf_name("V"), 1)
    enc.set_int(COSName.get_pdf_name("R"), 2)
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.get_pdf_name("Encrypt"), enc)

    assert doc.is_encrypted() is True
    first = doc.get_current_access_permission()
    second = doc.get_current_access_permission()
    # Both are no-permission AccessPermission objects, but NOT cached
    # (the encrypted-undecrypted branch deliberately skips the cache).
    assert isinstance(first, AccessPermission)
    assert isinstance(second, AccessPermission)
    doc.close()


# ---------- Wave 194: has_signatures predicate ----------


def test_has_signatures_false_on_fresh_document() -> None:
    """A pristine doc has no signatures — ``has_signatures()`` returns False
    without raising."""
    doc = PDDocument()
    assert doc.has_signatures() is False
    doc.close()


def test_has_signatures_false_when_acroform_absent() -> None:
    """Doc without /AcroForm reports no signatures (no KeyError leak)."""
    doc = PDDocument()
    doc.add_page(PDPage())
    assert doc.has_signatures() is False
    doc.close()


def test_has_signatures_true_when_signed_field_present() -> None:
    """A signature field with a populated /V signals
    ``has_signatures() == True``. Builds the field directly via the AcroForm
    surface — independent of ``add_signature``'s staging path."""
    from pypdfbox.cos import COSArray as _COSArray
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    doc.add_page(PDPage())
    catalog = doc.get_document_catalog()
    acro_form = PDAcroForm(doc)
    catalog.set_acro_form(acro_form)
    acro_form_dict = acro_form.get_cos_object()

    sig = PDSignature()
    field = COSDictionary()
    field.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
    field.set_string(COSName.get_pdf_name("T"), "Signature1")
    field.set_item(COSName.get_pdf_name("V"), sig.get_cos_object())

    fields = _COSArray()
    fields.add(field)
    acro_form_dict.set_item(COSName.get_pdf_name("Fields"), fields)

    assert doc.has_signatures() is True
    doc.close()


def test_has_signatures_false_when_field_has_no_value() -> None:
    """An empty signature field (no /V) is ignored — ``has_signatures()``
    only counts fields that have actually been signed."""
    from pypdfbox.cos import COSArray as _COSArray
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    doc.add_page(PDPage())
    catalog = doc.get_document_catalog()
    acro_form = PDAcroForm(doc)
    catalog.set_acro_form(acro_form)
    acro_form_dict = acro_form.get_cos_object()

    field = COSDictionary()
    field.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
    field.set_string(COSName.get_pdf_name("T"), "Signature1")
    # No /V — the field is unsigned.

    fields = _COSArray()
    fields.add(field)
    acro_form_dict.set_item(COSName.get_pdf_name("Fields"), fields)

    assert doc.has_signatures() is False
    doc.close()


# ---------- Wave 233: pdf-source + pending-signature accessors ----------


def test_get_pdf_source_returns_none_for_synthesised_doc() -> None:
    """``get_pdf_source`` returns ``None`` when no source backs the
    document — i.e. for a freshly-instantiated ``PDDocument`` synthesised
    in memory. Matches ``save_incremental``'s "requires a loaded
    document" guard."""
    doc = PDDocument()
    assert doc.get_pdf_source() is None
    doc.close()


def test_get_pdf_source_returns_loaded_source(tmp_path: Path) -> None:
    """When the document was loaded from a path (or any
    ``RandomAccessRead``-shaped source), ``get_pdf_source`` exposes that
    source — same instance that ``save_incremental`` uses internally."""
    src = PDDocument()
    src.add_page(PDPage())
    file_path = tmp_path / "source.pdf"
    src.save(file_path)
    src.close()

    doc = PDDocument.load(file_path)
    source = doc.get_pdf_source()
    assert source is not None
    # Same instance the underlying COSDocument exposes.
    assert source is doc.get_document().get_source()
    doc.close()


def test_get_pending_signature_returns_none_by_default() -> None:
    """A fresh document has no pending signature staged."""
    doc = PDDocument()
    assert doc.get_pending_signature() is None
    assert doc.has_pending_signature() is False
    doc.close()


def test_get_pending_signature_returns_staged_signature() -> None:
    """``add_signature`` stages the supplied :class:`PDSignature` —
    ``get_pending_signature`` returns the same instance until the next
    successful save (or external-signing handoff) clears it."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    doc = PDDocument()
    doc.add_page(PDPage())
    sig = PDSignature()
    doc.add_signature(sig)
    assert doc.get_pending_signature() is sig
    assert doc.has_pending_signature() is True
    doc.close()


def test_get_signature_interface_returns_staged_interface() -> None:
    """``get_signature_interface`` returns the callback wired by
    ``add_signature``. Unset when the caller chose the external-signing
    path (interface argument left as ``None``)."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    doc = PDDocument()
    doc.add_page(PDPage())
    assert doc.get_signature_interface() is None

    captured: list[bytes] = []

    from pypdfbox.pdmodel.interactive.digitalsignature.signature_interface import (
        SignatureInterface,
    )

    class _Sentinel(SignatureInterface):
        def sign(self, content: BinaryIO) -> bytes:  # pragma: no cover — not exercised here
            captured.append(b"signed")
            return b""

    iface = _Sentinel()
    doc.add_signature(PDSignature(), signature_interface=iface)
    assert doc.get_signature_interface() is iface
    doc.close()


def test_get_signature_options_returns_staged_options() -> None:
    """``get_signature_options`` returns the options object passed to
    ``add_signature``. Stored verbatim — pypdfbox doesn't introspect the
    options shape itself."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    doc = PDDocument()
    doc.add_page(PDPage())
    assert doc.get_signature_options() is None

    sentinel_options = object()
    doc.add_signature(PDSignature(), options=sentinel_options)
    assert doc.get_signature_options() is sentinel_options
    doc.close()


def test_pending_signature_cleared_after_external_signing() -> None:
    """The pending-signature accessors reflect the post-sign state once
    :meth:`ExternalSigningSupport.set_signature` finalises a signing
    cycle — both the staged signature and its sidecar fields drop back to
    ``None`` so a follow-up ``save_incremental`` no-ops."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    src = PDDocument()
    src.add_page(PDPage())
    sink = io.BytesIO()
    src.save(sink)
    src.close()

    doc = PDDocument.load(io.BytesIO(sink.getvalue()))
    doc.add_signature(PDSignature(), options=object())
    assert doc.has_pending_signature() is True

    out = io.BytesIO()
    handle = doc.save_incremental_for_external_signing(out)
    handle.set_signature(b"\x00\x01\x02\x03")

    assert doc.has_pending_signature() is False
    assert doc.get_pending_signature() is None
    assert doc.get_signature_interface() is None
    assert doc.get_signature_options() is None
    doc.close()


# ---------- get_number_of_pages → get_count() upstream parity ----------


def test_get_number_of_pages_uses_page_tree_count_field() -> None:
    """``get_number_of_pages`` should delegate to ``PDPageTree.get_count``
    (the cached ``/Pages /Count`` integer) rather than walking the tree
    via ``__len__``. The counts must match when the cached field is the
    truthful source — but the call goes through the cheap path."""
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    # The Count field on the root /Pages dict drives the cheap accessor.
    pages_root = doc.get_pages().get_cos_object()
    assert pages_root.get_int(COSName.get_pdf_name("Count")) == 3
    assert doc.get_number_of_pages() == 3
    doc.close()


def test_get_number_of_pages_zero_on_fresh_doc() -> None:
    doc = PDDocument()
    assert doc.get_number_of_pages() == 0
    doc.close()


# ---------- get_version: catalog skip when header < 1.4 ----------


def test_get_version_ignores_catalog_when_header_below_1_4() -> None:
    """ISO 32000-1 §7.5.2 forbids catalog ``/Version`` overrides on PDFs
    whose header is below 1.4. The reader must report the header version
    verbatim and ignore any catalog override (matching upstream's literal
    ``if (headerVersionFloat >= 1.4f)`` branch)."""
    doc = PDDocument()
    # Force the COSDocument header to 1.3 — older than the override threshold.
    doc.get_document().set_version(1.3)
    # Stamp a /Version on the catalog claiming 1.7. A strict-parity reader
    # must IGNORE this since the header is below 1.4.
    catalog_dict = doc.get_document_catalog().get_cos_object()
    catalog_dict.set_item(
        COSName.get_pdf_name("Version"), COSName.get_pdf_name("1.7")
    )
    assert doc.get_version() == pytest.approx(1.3)
    doc.close()


def test_get_version_uses_catalog_when_header_at_1_4() -> None:
    """When the header is at or above 1.4 the catalog version is honoured —
    upstream returns ``Math.max(headerVersionFloat, catalogVersionFloat)``."""
    doc = PDDocument()
    # Default header is 1.4 already; bump catalog to 1.7.
    catalog_dict = doc.get_document_catalog().get_cos_object()
    catalog_dict.set_item(
        COSName.get_pdf_name("Version"), COSName.get_pdf_name("1.7")
    )
    assert doc.get_version() == pytest.approx(1.7)
    doc.close()


def test_get_version_swallows_malformed_catalog_version() -> None:
    """A non-numeric catalog ``/Version`` should be logged-and-skipped,
    falling back to the header version. Mirrors upstream's
    ``NumberFormatException`` swallow."""
    doc = PDDocument()
    # Header is 1.4 default.
    catalog_dict = doc.get_document_catalog().get_cos_object()
    catalog_dict.set_item(
        COSName.get_pdf_name("Version"), COSName.get_pdf_name("oops")
    )
    # Catalog parse fails → fall back to header (1.4).
    assert doc.get_version() == pytest.approx(1.4)
    doc.close()


# ---------- get_fonts_to_close accessor ----------


def test_get_fonts_to_close_empty_by_default() -> None:
    """A fresh document has no fonts queued for close-on-exit."""
    doc = PDDocument()
    assert doc.get_fonts_to_close() == []
    doc.close()


def test_get_fonts_to_close_returns_live_backing_store() -> None:
    """:meth:`get_fonts_to_close` returns the document's own list — calls
    to :meth:`register_true_type_font_for_closing` show up immediately,
    and direct mutation propagates back to the document state."""
    doc = PDDocument()
    fonts = doc.get_fonts_to_close()
    assert fonts is doc.get_fonts_to_close()  # stable reference
    sentinel = object()
    doc.register_true_type_font_for_closing(sentinel)
    assert sentinel in fonts  # registration visible via accessor
    fonts.clear()
    # Mutation through the accessor flows back into the document.
    assert doc.get_fonts_to_close() == []
    doc.close()


# ---------- is_signature_added predicate ----------


def test_is_signature_added_false_on_fresh_document() -> None:
    doc = PDDocument()
    assert doc.is_signature_added() is False
    doc.close()


def test_is_signature_added_true_after_add_signature() -> None:
    """The flag flips true on the first :meth:`add_signature` call and
    stays sticky for the lifetime of the document — mirrors upstream's
    one-shot ``signatureAdded`` guard."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    src = PDDocument()
    src.add_page(PDPage())
    sink = io.BytesIO()
    src.save(sink)
    src.close()

    doc = PDDocument.load(io.BytesIO(sink.getvalue()))
    assert doc.is_signature_added() is False
    doc.add_signature(PDSignature())
    assert doc.is_signature_added() is True
    # Stays sticky even after the staged signature is consumed.
    out = io.BytesIO()
    handle = doc.save_incremental_for_external_signing(out)
    handle.set_signature(b"\x00")
    assert doc.is_signature_added() is True
    doc.close()


def test_is_signature_added_blocks_second_add_signature() -> None:
    """A second :meth:`add_signature` raises while ``is_signature_added``
    reports ``True`` — callers can pre-check via the predicate to avoid the
    exception path."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )

    src = PDDocument()
    src.add_page(PDPage())
    sink = io.BytesIO()
    src.save(sink)
    src.close()

    doc = PDDocument.load(io.BytesIO(sink.getvalue()))
    doc.add_signature(PDSignature())
    assert doc.is_signature_added() is True
    with pytest.raises(ValueError, match="Only one signature"):
        doc.add_signature(PDSignature())
    doc.close()


# ---------- private signing helpers (parity with upstream PDDocument) ----------


def test_subset_designated_fonts_drains_set() -> None:
    """``subset_designated_fonts`` calls ``subset()`` on every queued font
    and clears the backing set. Mirrors upstream
    ``PDDocument.subsetDesignatedFonts``."""

    class _FakeFont:
        def __init__(self) -> None:
            self.subset_called = 0

        def subset(self) -> None:
            self.subset_called += 1

    doc = PDDocument()
    f1, f2 = _FakeFont(), _FakeFont()
    doc.get_fonts_to_subset().add(f1)
    doc.get_fonts_to_subset().add(f2)

    doc.subset_designated_fonts()

    assert f1.subset_called == 1
    assert f2.subset_called == 1
    assert doc.get_fonts_to_subset() == set()
    doc.close()


def test_subset_designated_fonts_noop_on_empty() -> None:
    """No-op when the queue is empty (mirrors upstream's bare for-loop)."""
    doc = PDDocument()
    doc.subset_designated_fonts()
    assert doc.get_fonts_to_subset() == set()
    doc.close()


def test_subset_designated_fonts_skips_fonts_without_subset() -> None:
    """A queued object without a ``subset()`` method is silently dropped —
    we still clear the set, but don't raise."""

    class _NoSubset:
        pass

    doc = PDDocument()
    doc.get_fonts_to_subset().add(_NoSubset())
    doc.subset_designated_fonts()
    assert doc.get_fonts_to_subset() == set()
    doc.close()


def test_find_signature_field_returns_match() -> None:
    """``find_signature_field`` walks an iterator, returning the
    ``PDSignatureField`` whose ``/V`` is the COS object of ``sig_object``."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    doc = PDDocument()
    acro = PDAcroForm(doc)
    sig = PDSignature()
    field = PDSignatureField(acro)
    field.set_value(sig)

    other = PDTextField(acro)  # non-signature field is skipped
    found = PDDocument.find_signature_field(iter([other, field]), sig)
    assert found is field

    # No match — different signature.
    other_sig = PDSignature()
    not_found = PDDocument.find_signature_field(iter([other, field]), other_sig)
    assert not_found is None
    doc.close()


def test_check_signature_field_membership() -> None:
    """``check_signature_field`` returns True if the field is present in
    the iterator (compared by underlying COS dict)."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField

    doc = PDDocument()
    acro = PDAcroForm(doc)
    a, b, c = PDSignatureField(acro), PDSignatureField(acro), PDSignatureField(acro)
    assert PDDocument.check_signature_field(iter([a, b]), b) is True
    assert PDDocument.check_signature_field(iter([a, b]), c) is False
    doc.close()


def test_check_signature_annotation_membership() -> None:
    """``check_signature_annotation`` reports membership keyed off the
    underlying COS dict."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    a, b, c = PDAnnotationWidget(), PDAnnotationWidget(), PDAnnotationWidget()
    assert PDDocument.check_signature_annotation([a, b], b) is True
    assert PDDocument.check_signature_annotation([a, b], c) is False


def test_check_signature_annotation_handles_raw_cos_dict_entries() -> None:
    """Raw ``COSDictionary`` entries (no ``get_cos_object()``) compare
    directly — covers the ``annotations`` list yielding bare COS dicts."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    widget = PDAnnotationWidget()
    raw_cos = widget.get_cos_object()
    # Pretend the page returned the COS dict directly (some legacy paths).
    assert PDDocument.check_signature_annotation([raw_cos], widget) is True


def test_prepare_non_visible_signature_sets_zero_rect_and_appearance() -> None:
    """``prepare_non_visible_signature`` zeroes the widget rectangle and
    installs a normal-appearance stub so the dictionary is well-formed.
    Mirrors upstream's invisible-signature posture (PDFBox §535-548)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    doc = PDDocument()
    widget = PDAnnotationWidget()
    doc.prepare_non_visible_signature(widget)

    rect = widget.get_rectangle()
    assert rect is not None
    assert rect.get_lower_left_x() == 0.0
    assert rect.get_upper_right_x() == 0.0

    ap = widget.get_appearance()
    assert ap is not None
    assert ap.get_normal_appearance() is not None
    doc.close()


def test_assign_signature_rectangle_copies_when_widget_empty() -> None:
    """``assign_signature_rectangle`` adopts the template's /Rect when the
    widget has no usable rectangle yet."""
    from pypdfbox.cos import COSArray, COSInteger
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    widget = PDAnnotationWidget()
    template = COSDictionary()
    rect = COSArray()
    for v in (10, 20, 30, 40):
        rect.add(COSInteger.get(v))
    template.set_item(COSName.get_pdf_name("Rect"), rect)

    PDDocument.assign_signature_rectangle(widget, template)

    out = widget.get_rectangle()
    assert out is not None
    assert out.get_lower_left_x() == 10.0
    assert out.get_upper_right_y() == 40.0


def test_assign_signature_rectangle_preserves_existing() -> None:
    """When the widget already has a 4-entry rectangle, the template's
    /Rect is ignored — mirrors upstream's "preserve original" branch."""
    from pypdfbox.cos import COSArray, COSInteger
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    widget = PDAnnotationWidget()
    widget.set_rectangle(PDRectangle(1.0, 2.0, 3.0, 4.0))

    template = COSDictionary()
    rect = COSArray()
    for v in (10, 20, 30, 40):
        rect.add(COSInteger.get(v))
    template.set_item(COSName.get_pdf_name("Rect"), rect)

    PDDocument.assign_signature_rectangle(widget, template)
    out = widget.get_rectangle()
    assert out is not None
    assert out.get_lower_left_x() == 1.0  # untouched


def test_assign_appearance_dictionary_attaches_and_marks_direct() -> None:
    """``assign_appearance_dictionary`` wraps and forces the AP dict
    direct so it round-trips inside the widget."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    widget = PDAnnotationWidget()
    ap_dict = COSDictionary()
    PDDocument.assign_appearance_dictionary(widget, ap_dict)
    assert ap_dict.is_direct() is True
    assert widget.get_appearance() is not None


def test_assign_acro_form_default_resource_installs_when_missing() -> None:
    """When the AcroForm has no /DR, the template's /DR is adopted
    wholesale and marked direct + dirty."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

    doc = PDDocument()
    acro = PDAcroForm(doc)
    template = COSDictionary()
    new_dr = COSDictionary()
    template.set_item(COSName.get_pdf_name("DR"), new_dr)

    PDDocument.assign_acro_form_default_resource(acro, template)

    assert acro.get_default_resources() is not None
    assert (
        acro.get_cos_object().get_dictionary_object(COSName.get_pdf_name("DR"))
        is new_dr
    )
    assert new_dr.is_direct() is True
    doc.close()


def test_assign_acro_form_default_resource_noop_when_template_lacks_dr() -> None:
    """No /DR on the template → no-op (mirrors upstream's null-guard)."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

    doc = PDDocument()
    acro = PDAcroForm(doc)
    PDDocument.assign_acro_form_default_resource(acro, COSDictionary())
    assert acro.get_default_resources() is None
    doc.close()


def test_prepare_visible_signature_raises_on_incomplete_template() -> None:
    """Empty template → ``ValueError`` (≈ Java IllegalArgumentException)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

    doc = PDDocument()
    acro = PDAcroForm(doc)
    widget = PDAnnotationWidget()
    template = COSDocument()
    with pytest.raises(ValueError, match="Template is missing required objects"):
        doc.prepare_visible_signature(widget, acro, template)
    doc.close()
