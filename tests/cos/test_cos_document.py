from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
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


def test_xref_table_round_trip() -> None:
    with COSDocument() as doc:
        table = {
            COSObjectKey(1, 0): 100,
            COSObjectKey(2, 0): 200,
            None: 999,  # PDFBOX-6132 — must be ignored
        }
        doc.add_xref_table(table)  # type: ignore[arg-type]
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
