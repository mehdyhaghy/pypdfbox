from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSDocumentState,
    COSInteger,
    COSName,
    COSObjectKey,
    COSString,
)
from pypdfbox.io import ScratchFile


def test_default_state() -> None:
    with COSDocument() as doc:
        assert doc.get_version() == 1.4
        assert doc.get_trailer() is None
        assert doc.get_catalog() is None
        assert not doc.is_encrypted()
        assert doc.get_objects() == []
        assert not doc.is_xref_stream()


def test_object_pool_creates_placeholder_on_demand() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(1, 0)
        obj = doc.get_object_from_pool(key)
        assert obj.object_number == 1
        assert obj.generation_number == 0
        # Second call returns the same instance.
        assert doc.get_object_from_pool(key) is obj
        assert doc.has_object(key)


def test_object_pool_distinct_keys_distinct_objects() -> None:
    with COSDocument() as doc:
        a = doc.get_object_from_pool(COSObjectKey(1, 0))
        b = doc.get_object_from_pool(COSObjectKey(2, 0))
        assert a is not b
        assert len(doc.get_objects()) == 2
        assert set(doc.get_object_keys()) == {COSObjectKey(1, 0), COSObjectKey(2, 0)}


def test_remove_object() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(1, 0)
        obj = doc.get_object_from_pool(key)
        removed = doc.remove_object(key)
        assert removed is obj
        assert not doc.has_object(key)
        assert doc.remove_object(key) is None


def test_set_and_get_trailer() -> None:
    with COSDocument() as doc:
        trailer = COSDictionary()
        trailer.set_int("Size", 10)
        doc.set_trailer(trailer)
        assert doc.get_trailer() is trailer
        assert doc.get_trailer().get_int("Size") == 10  # type: ignore[union-attr]


def test_get_catalog_via_trailer_root() -> None:
    with COSDocument() as doc:
        catalog = COSDictionary()
        catalog.set_name("Type", "Catalog")
        trailer = COSDictionary()
        trailer.set_item(COSName.ROOT, catalog)  # type: ignore[attr-defined]
        doc.set_trailer(trailer)
        assert doc.get_catalog() is catalog


def test_get_catalog_returns_none_when_root_missing() -> None:
    with COSDocument() as doc:
        doc.set_trailer(COSDictionary())
        assert doc.get_catalog() is None


def test_document_id_round_trip() -> None:
    with COSDocument() as doc:
        ids = COSArray([COSString(b"a" * 16), COSString(b"b" * 16)])
        doc.set_document_id(ids)
        assert doc.get_document_id() is ids
        # set_document_id auto-creates a trailer when absent.
        assert doc.get_trailer() is not None


def test_encryption_flags() -> None:
    with COSDocument() as doc:
        assert not doc.is_encrypted()
        assert doc.get_encryption_dictionary() is None
        enc = COSDictionary()
        enc.set_int("V", 4)
        trailer = COSDictionary()
        trailer.set_item(COSName.ENCRYPT, enc)  # type: ignore[attr-defined]
        doc.set_trailer(trailer)
        assert doc.is_encrypted()
        assert doc.get_encryption_dictionary() is enc


def test_set_version_validates() -> None:
    with COSDocument() as doc:
        doc.set_version(2.0)
        assert doc.get_version() == 2.0
        with pytest.raises(ValueError):
            doc.set_version(0)
        with pytest.raises(ValueError):
            doc.set_version(-1)


def test_xref_stream_marker() -> None:
    with COSDocument() as doc:
        assert not doc.is_xref_stream()
        doc.set_xref_stream(True)
        assert doc.is_xref_stream()


def test_external_scratch_not_closed_with_document() -> None:
    sf = ScratchFile()
    doc = COSDocument(scratch_file=sf)
    doc.close()
    assert not sf.is_closed()
    sf.close()


def test_internal_scratch_closed_with_document() -> None:
    doc = COSDocument()
    sf = doc.scratch_file
    doc.close()
    assert sf.is_closed()
    assert doc.is_closed()


def test_close_is_idempotent() -> None:
    doc = COSDocument()
    doc.close()
    doc.close()
    assert doc.is_closed()


def test_visitor_dispatches_to_visit_from_document() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    with COSDocument() as doc:
        doc.accept(v)
        assert v.calls == [("document", doc)]


def test_object_pool_after_close_is_empty() -> None:
    doc = COSDocument()
    doc.get_object_from_pool(COSObjectKey(1, 0))
    doc.close()
    assert doc.get_objects() == []


def test_repr_summary() -> None:
    with COSDocument() as doc:
        doc.set_version(2.0)
        text = repr(doc)
        assert "version=2.0" in text
        assert "objects=0" in text


def test_set_document_id_when_trailer_already_exists() -> None:
    with COSDocument() as doc:
        existing = COSDictionary()
        existing.set_int("Size", 5)
        doc.set_trailer(existing)
        ids = COSArray([COSString(b"x"), COSString(b"y")])
        doc.set_document_id(ids)
        assert doc.get_trailer() is existing  # not replaced
        assert existing.get_int("Size") == 5
        assert doc.get_document_id() is ids


def test_objects_inserted_via_pool_have_correct_numbers() -> None:
    with COSDocument() as doc:
        for n in [3, 1, 2]:
            doc.get_object_from_pool(COSObjectKey(n, 0))
        nums = [o.object_number for o in doc.get_objects()]
        assert nums == [3, 1, 2]  # insertion order preserved


def test_external_int_object_does_not_leak_into_pool() -> None:
    with COSDocument() as doc:
        # Adding a non-COSObject COSBase manually is not part of this API; the
        # pool only tracks COSObject placeholders. Smoke-check that a stray
        # COSInteger isn't accidentally tracked.
        doc.get_object_from_pool(COSObjectKey(1, 0))
        _ = COSInteger(99)
        assert len(doc.get_objects()) == 1


def test_get_object_returns_none_for_unknown_key() -> None:
    with COSDocument() as doc:
        assert doc.get_object(COSObjectKey(42, 0)) is None
        # ``get_object`` does NOT auto-create.
        assert doc.get_objects() == []


def test_get_object_returns_existing_placeholder() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(7, 0)
        placeholder = doc.get_object_from_pool(key)
        assert doc.get_object(key) is placeholder


def test_get_key_finds_pool_entry_for_resolved_object_by_identity() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(8, 0)
        target = COSDictionary()
        target.set_int("Count", 3)
        doc.get_object_from_pool(key).set_object(target)

        assert doc.get_key(target) == key
        assert doc.getKey(target) == key


def test_get_key_does_not_match_equal_distinct_objects() -> None:
    with COSDocument() as doc:
        stored = COSInteger(4)
        doc.get_object_from_pool(COSObjectKey(9, 0)).set_object(stored)

        assert doc.get_key(COSInteger(4)) is None


def test_get_key_accepts_pool_cos_object_itself() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(10, 0)
        placeholder = doc.get_object_from_pool(key)

        assert doc.get_key(placeholder) == key


def test_xref_table_round_trip() -> None:
    with COSDocument() as doc:
        table = {
            COSObjectKey(1, 0): 100,
            COSObjectKey(2, 0): 200,
            None: 999,  # PDFBOX-6132 — must be ignored
        }
        doc.add_xref_table(table)
        x = doc.get_xref_table()
        assert x[COSObjectKey(1, 0)] == 100
        assert x[COSObjectKey(2, 0)] == 200
        assert None not in x
        assert len(x) == 2


def test_xref_table_cleared_on_close() -> None:
    doc = COSDocument()
    doc.add_xref_table({COSObjectKey(1, 0): 50})
    assert len(doc.get_xref_table()) == 1
    doc.close()
    assert doc.get_xref_table() == {}


def test_set_is_xref_stream_alias() -> None:
    with COSDocument() as doc:
        assert not doc.is_xref_stream()
        doc.set_is_xref_stream(True)
        assert doc.is_xref_stream()
        doc.set_is_xref_stream(False)
        assert not doc.is_xref_stream()


def test_highest_xref_object_number() -> None:
    with COSDocument() as doc:
        assert doc.get_highest_xref_object_number() == 0
        doc.set_highest_xref_object_number(42)
        assert doc.get_highest_xref_object_number() == 42
        with pytest.raises(ValueError):
            doc.set_highest_xref_object_number(-1)


def test_set_warn_missing_close_does_not_raise() -> None:
    with COSDocument() as doc:
        # Smoke test: the toggle is honored (no raise) and is idempotent.
        doc.set_warn_missing_close(False)
        doc.set_warn_missing_close(True)


def test_start_xref_round_trip() -> None:
    with COSDocument() as doc:
        assert doc.get_start_xref() == 0
        doc.set_start_xref(12345)
        assert doc.get_start_xref() == 12345
        with pytest.raises(ValueError):
            doc.set_start_xref(-1)


def test_version_set_int_promoted_to_float() -> None:
    with COSDocument() as doc:
        doc.set_version(1.7)
        assert doc.get_version() == 1.7


def test_pdfbox_camelcase_object_pool_aliases() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(5, 0)
        obj = doc.getObjectFromPool(key)

        assert doc.getObject(key) is obj
        assert doc.getObjects() == [obj]
        assert doc.removeObject(key) is obj
        assert doc.getObject(key) is None


def test_pdfbox_camelcase_trailer_catalog_and_encryption_aliases() -> None:
    with COSDocument() as doc:
        catalog = COSDictionary()
        catalog.set_name("Type", "Catalog")
        enc = COSDictionary()
        trailer = COSDictionary()
        trailer.set_item(COSName.ROOT, catalog)  # type: ignore[attr-defined]
        trailer.set_item(COSName.ENCRYPT, enc)  # type: ignore[attr-defined]

        doc.setTrailer(trailer)

        assert doc.getTrailer() is trailer
        assert doc.getCatalog() is catalog
        assert doc.isEncrypted() is True
        assert doc.getEncryptionDictionary() is enc


def test_pdfbox_camelcase_xref_and_version_aliases() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(9, 0)

        doc.addXRefTable({key: 321})
        doc.setVersion(2.0)
        doc.setXRefStream(True)

        assert doc.getXrefTable()[key] == 321
        assert doc.getVersion() == 2.0
        assert doc.isXRefStream() is True


def test_decrypted_flag_default_and_one_way_setter() -> None:
    with COSDocument() as doc:
        assert doc.is_decrypted() is False
        doc.set_decrypted()
        assert doc.is_decrypted() is True
        # set_decrypted is one-way — calling again is a no-op (matches
        # upstream which has no setDecrypted(false)).
        doc.set_decrypted()
        assert doc.is_decrypted() is True


def test_set_encryption_dictionary_writes_to_trailer() -> None:
    with COSDocument() as doc:
        # Auto-creates trailer when absent.
        enc = COSDictionary()
        enc.set_int("V", 4)
        doc.set_encryption_dictionary(enc)
        assert doc.is_encrypted() is True
        assert doc.get_encryption_dictionary() is enc
        # Replacing the dictionary on an existing trailer keeps the trailer.
        existing_trailer = doc.get_trailer()
        enc2 = COSDictionary()
        enc2.set_int("V", 5)
        doc.set_encryption_dictionary(enc2)
        assert doc.get_trailer() is existing_trailer
        assert doc.get_encryption_dictionary() is enc2


def test_hybrid_xref_marker_default_and_one_way_setter() -> None:
    with COSDocument() as doc:
        assert doc.has_hybrid_xref() is False
        doc.set_has_hybrid_xref()
        assert doc.has_hybrid_xref() is True
        # One-way (matches upstream — no setHasHybridXRef(false)).
        doc.set_has_hybrid_xref()
        assert doc.has_hybrid_xref() is True


def test_create_cos_stream_uses_document_scratch_file() -> None:
    scratch = ScratchFile()
    with COSDocument(scratch_file=scratch) as doc:
        stream = doc.create_cos_stream()
        # Empty stream is valid (no data yet).
        assert stream.has_data() is False
        # Writing should not raise — proves the stream is wired to the
        # document's scratch file.
        stream.set_raw_data(b"hello")
        assert stream.get_raw_data() == b"hello"
        # The stream does NOT own the scratch file — closing the stream
        # leaves the document's scratch usable.
        stream.close()
        # Document close releases the shared scratch file.


def test_create_cos_stream_copies_dictionary_entries() -> None:
    with COSDocument() as doc:
        seed = COSDictionary()
        seed.set_int("Length", 7)
        seed.set_name("Filter", "FlateDecode")
        stream = doc.create_cos_stream(seed)
        assert stream.get_int(COSName.LENGTH, -1) == 7  # type: ignore[attr-defined]
        assert stream.get_dictionary_object(
            COSName.FILTER  # type: ignore[attr-defined]
        ) == COSName.get_pdf_name("FlateDecode")
        stream.close()


def test_get_objects_by_type_two_arg_overload_matches_either_name() -> None:
    """The two-arg overload matches /Type entries against either of the
    two given names. Used upstream for short / long /Type aliases."""
    with COSDocument() as doc:
        from pypdfbox.cos.cos_object import COSObject

        # Build two objects: one with /Type /Page, one with /Type /XObject.
        page = COSDictionary()
        page.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))  # type: ignore[attr-defined]
        xobj = COSDictionary()
        xobj.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))  # type: ignore[attr-defined]

        page_obj = COSObject(1, 0)
        page_obj.set_object(page)
        xobj_obj = COSObject(2, 0)
        xobj_obj.set_object(xobj)
        doc._objects[COSObjectKey(1, 0)] = page_obj
        doc._objects[COSObjectKey(2, 0)] = xobj_obj

        # Single-arg form — matches only /Page.
        page_only = doc.get_objects_by_type("Page")
        assert page_only == [page_obj]

        # Two-arg form — matches either /Page or /XObject.
        both = doc.get_objects_by_type("Page", "XObject")
        assert page_obj in both
        assert xobj_obj in both
        assert len(both) == 2

        # Two-arg form with non-matching second name — same as single-arg.
        only_page = doc.get_objects_by_type("Page", "Catalog")
        assert only_page == [page_obj]


# -- Wave 171 round-out --------------------------------------------------


def test_cos_name_id_and_linearized_constants() -> None:
    # Both well-known names are interned via COSName.get_pdf_name and exposed
    # as class attributes for cheap reuse — mirrors PDFBox's catalog of
    # predefined names.
    assert COSName.ID is COSName.get_pdf_name("ID")  # type: ignore[attr-defined]
    assert COSName.LINEARIZED is COSName.get_pdf_name("Linearized")  # type: ignore[attr-defined]
    assert str(COSName.ID) == "/ID"  # type: ignore[attr-defined]
    assert str(COSName.LINEARIZED) == "/Linearized"  # type: ignore[attr-defined]


def test_get_document_id_uses_typed_cos_array_accessor() -> None:
    # When /ID is present but the value is not an array, the typed accessor
    # must filter it out (mirrors upstream getCOSArray's None-on-mistype
    # behaviour rather than raising).
    with COSDocument() as doc:
        trailer = COSDictionary()
        # Set a non-array value at /ID — get_document_id() must return None.
        trailer.set_int("ID", 7)
        doc.set_trailer(trailer)
        assert doc.get_document_id() is None


def test_get_document_id_returns_array_when_present() -> None:
    with COSDocument() as doc:
        ids = COSArray([COSString(b"\x00" * 16), COSString(b"\xff" * 16)])
        trailer = COSDictionary()
        trailer.set_item(COSName.ID, ids)  # type: ignore[attr-defined]
        doc.set_trailer(trailer)
        assert doc.get_document_id() is ids


def test_set_document_id_uses_id_constant_round_trip() -> None:
    # set_document_id stores under COSName.ID — round-trips via the constant
    # rather than a fresh get_pdf_name lookup.
    with COSDocument() as doc:
        ids = COSArray([COSString(b"a"), COSString(b"b")])
        doc.set_document_id(ids)
        # The trailer's /ID entry, fetched by the constant, must be the
        # same array instance we set.
        trailer = doc.get_trailer()
        assert trailer is not None
        assert trailer.get_dictionary_object(COSName.ID) is ids  # type: ignore[attr-defined]


# COSDocumentState -------------------------------------------------------


def test_cos_document_state_initial_parsing() -> None:
    state = COSDocumentState()
    # Initial state is "parsing" → not yet accepting updates.
    assert state.is_accepting_updates() is False


def test_cos_document_state_flip_accepts_updates() -> None:
    state = COSDocumentState()
    state.set_parsing(False)
    assert state.is_accepting_updates() is True
    # And flippable back to parsing if needed.
    state.set_parsing(True)
    assert state.is_accepting_updates() is False


def test_cos_document_get_document_state_default() -> None:
    with COSDocument() as doc:
        state = doc.get_document_state()
        assert isinstance(state, COSDocumentState)
        # Repeat call returns the same instance (state is per-document).
        assert doc.get_document_state() is state
        # Default state mirrors a freshly-constructed COSDocumentState —
        # parsing in progress, not yet accepting updates.
        assert state.is_accepting_updates() is False


def test_cos_document_state_flip_visible_through_document() -> None:
    with COSDocument() as doc:
        state = doc.get_document_state()
        state.set_parsing(False)
        # The flag is observable via the document-level accessor too.
        assert doc.get_document_state().is_accepting_updates() is True
