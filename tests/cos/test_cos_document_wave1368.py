"""Wave 1368 — COSDocument trailer + pool + xref invariants.

Round-out tests for paths not yet covered:

* ``get_object_from_pool`` creates a placeholder ``COSObject`` on first
  miss and returns the same instance on subsequent lookups.
* ``get_object`` does NOT auto-create — it returns ``None`` for unknown
  keys.
* ``set_trailer`` / ``get_catalog`` / ``get_document_id`` round-trip.
* ``set_document_id`` auto-creates the trailer on demand.
* ``set_encryption_dictionary`` auto-creates the trailer on demand.
* ``add_xref_table`` skips ``None`` keys (PDFBOX-6132 corrupt entry).
* ``add_xref_table`` populates ``get_xref_table`` so the writer can read
  offsets back.
* ``get_objects_by_type`` matches single-type and dual-type overloads,
  ignores non-dictionary values, and ignores entries lacking a ``/Type``.
* ``set_version`` / ``set_start_xref`` / ``set_highest_xref_object_number``
  store their argument verbatim with no validation (upstream is a bare field
  assignment — oracle-confirmed, wave 1537).
* ``close`` is idempotent.
* ``is_encrypted`` returns ``False`` without a trailer.
* ``__enter__`` / ``__exit__`` close the document.
* ``create_cos_stream`` copies a supplied dictionary into the new stream.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSString,
)

# ---------- pool dispatch ----------


def test_get_object_from_pool_creates_placeholder_once() -> None:
    doc = COSDocument()
    key = COSObjectKey(5, 0)
    a = doc.get_object_from_pool(key)
    b = doc.get_object_from_pool(key)
    assert a is b
    assert isinstance(a, COSObject)
    assert a.object_number == 5
    doc.close()


def test_get_object_returns_none_for_unknown_key() -> None:
    doc = COSDocument()
    assert doc.get_object(COSObjectKey(99, 0)) is None
    doc.close()


def test_has_object_reflects_pool_state() -> None:
    doc = COSDocument()
    key = COSObjectKey(1, 0)
    assert doc.has_object(key) is False
    doc.get_object_from_pool(key)
    assert doc.has_object(key) is True
    doc.close()


def test_get_objects_returns_pool_in_insertion_order() -> None:
    doc = COSDocument()
    keys = [COSObjectKey(i, 0) for i in (3, 1, 2)]
    refs = [doc.get_object_from_pool(k) for k in keys]
    assert doc.get_objects() == refs
    assert doc.get_object_keys() == keys
    doc.close()


def test_remove_object_removes_pool_entry() -> None:
    doc = COSDocument()
    key = COSObjectKey(7, 0)
    ref = doc.get_object_from_pool(key)
    removed = doc.remove_object(key)
    assert removed is ref
    assert doc.has_object(key) is False
    # Subsequent remove returns None.
    assert doc.remove_object(key) is None
    doc.close()


def test_get_key_returns_none_for_unowned_object() -> None:
    doc = COSDocument()
    stray = COSDictionary()
    assert doc.get_key(stray) is None
    doc.close()


def test_get_key_returns_owner_key() -> None:
    doc = COSDocument()
    key = COSObjectKey(8, 0)
    cos_obj = doc.get_object_from_pool(key)
    cos_obj.set_object(COSDictionary([("X", COSInteger.get(1))]))
    inner = cos_obj.get_object()
    found_key = doc.get_key(inner)
    assert found_key == key
    doc.close()


# ---------- trailer / catalog / id ----------


def test_get_trailer_is_none_by_default() -> None:
    doc = COSDocument()
    assert doc.get_trailer() is None
    assert doc.get_catalog() is None
    assert doc.get_document_id() is None
    assert doc.is_encrypted() is False
    assert doc.get_encryption_dictionary() is None
    doc.close()


def test_set_trailer_round_trip() -> None:
    doc = COSDocument()
    trailer = COSDictionary()
    doc.set_trailer(trailer)
    assert doc.get_trailer() is trailer
    doc.close()


def test_get_catalog_resolves_trailer_root() -> None:
    doc = COSDocument()
    catalog = COSDictionary([("Type", COSName.get_pdf_name("Catalog"))])
    trailer = COSDictionary([("Root", catalog)])
    doc.set_trailer(trailer)
    assert doc.get_catalog() is catalog
    doc.close()


def test_get_catalog_returns_none_for_non_dict_root() -> None:
    doc = COSDocument()
    trailer = COSDictionary([("Root", COSInteger.get(7))])
    doc.set_trailer(trailer)
    assert doc.get_catalog() is None
    doc.close()


def test_set_document_id_auto_creates_trailer() -> None:
    doc = COSDocument()
    ids = COSArray([COSString("abc"), COSString("def")])
    doc.set_document_id(ids)
    assert doc.get_trailer() is not None
    assert doc.get_document_id() is ids
    doc.close()


def test_get_document_id_returns_none_for_non_array_entry() -> None:
    doc = COSDocument()
    trailer = COSDictionary([("ID", COSString("not-an-array"))])
    doc.set_trailer(trailer)
    assert doc.get_document_id() is None
    doc.close()


def test_set_encryption_dictionary_auto_creates_trailer() -> None:
    doc = COSDocument()
    enc = COSDictionary([("V", COSInteger.get(4))])
    doc.set_encryption_dictionary(enc)
    assert doc.is_encrypted() is True
    assert doc.get_encryption_dictionary() is enc
    doc.close()


def test_is_encrypted_false_without_encrypt_key() -> None:
    doc = COSDocument()
    doc.set_trailer(COSDictionary())
    assert doc.is_encrypted() is False
    doc.close()


def test_set_decrypted_is_one_way() -> None:
    doc = COSDocument()
    assert doc.is_decrypted() is False
    doc.set_decrypted()
    assert doc.is_decrypted() is True
    # No way to clear; second call is a no-op.
    doc.set_decrypted()
    assert doc.is_decrypted() is True
    doc.close()


# ---------- xref table ----------


def test_add_xref_table_skips_none_keys() -> None:
    doc = COSDocument()
    table = {COSObjectKey(1, 0): 100, None: 200, COSObjectKey(2, 0): 300}
    doc.add_xref_table(table)  # type: ignore[arg-type]
    xref = doc.get_xref_table()
    assert COSObjectKey(1, 0) in xref
    assert COSObjectKey(2, 0) in xref
    assert None not in xref
    doc.close()


def test_add_xref_table_creates_pool_entries() -> None:
    doc = COSDocument()
    key = COSObjectKey(10, 0)
    doc.add_xref_table({key: 1234})
    assert doc.has_object(key)
    assert doc.get_xref_table()[key] == 1234
    doc.close()


def test_add_x_ref_table_alias_calls_through() -> None:
    doc = COSDocument()
    key = COSObjectKey(11, 0)
    doc.add_x_ref_table({key: 4321})
    assert doc.get_xref_table()[key] == 4321
    doc.close()


# ---------- get_objects_by_type ----------


def test_get_objects_by_type_returns_matching_objects() -> None:
    doc = COSDocument()
    key_a = COSObjectKey(1, 0)
    key_b = COSObjectKey(2, 0)
    key_c = COSObjectKey(3, 0)
    ref_a = doc.get_object_from_pool(key_a)
    ref_b = doc.get_object_from_pool(key_b)
    ref_c = doc.get_object_from_pool(key_c)
    ref_a.set_object(COSDictionary([("Type", COSName.get_pdf_name("Page"))]))
    ref_b.set_object(COSDictionary([("Type", COSName.get_pdf_name("Font"))]))
    ref_c.set_object(COSDictionary([("Type", COSName.get_pdf_name("Page"))]))
    pages = doc.get_objects_by_type("Page")
    assert ref_a in pages
    assert ref_c in pages
    assert ref_b not in pages
    doc.close()


def test_get_objects_by_type_dual_overload() -> None:
    doc = COSDocument()
    key_a = COSObjectKey(1, 0)
    key_b = COSObjectKey(2, 0)
    ref_a = doc.get_object_from_pool(key_a)
    ref_b = doc.get_object_from_pool(key_b)
    ref_a.set_object(COSDictionary([("Type", COSName.get_pdf_name("Font"))]))
    ref_b.set_object(COSDictionary([("Type", COSName.get_pdf_name("CIDFontType0"))]))
    fonts = doc.get_objects_by_type("Font", "CIDFontType0")
    assert ref_a in fonts
    assert ref_b in fonts
    doc.close()


def test_get_objects_by_type_skips_non_dict_payloads() -> None:
    doc = COSDocument()
    key = COSObjectKey(1, 0)
    ref = doc.get_object_from_pool(key)
    ref.set_object(COSInteger.get(99))
    assert doc.get_objects_by_type("Page") == []
    doc.close()


def test_get_objects_by_type_skips_dict_without_type_key() -> None:
    doc = COSDocument()
    key = COSObjectKey(1, 0)
    ref = doc.get_object_from_pool(key)
    ref.set_object(COSDictionary())
    assert doc.get_objects_by_type("Page") == []
    doc.close()


# ---------- version / xref-stream / hybrid flags ----------


def test_set_version_accepts_non_positive() -> None:
    # Upstream PDFBox 3.0.7 ``setVersion`` is a bare field assignment with no
    # validation — zero / negative / downgrade values are stored verbatim
    # (oracle-confirmed, wave 1537). Match that lenient contract.
    doc = COSDocument()
    doc.set_version(0)
    assert doc.get_version() == pytest.approx(0.0)
    doc.set_version(-1.7)
    assert doc.get_version() == pytest.approx(-1.7)
    doc.close()


def test_set_version_round_trip() -> None:
    doc = COSDocument()
    doc.set_version(1.7)
    assert doc.get_version() == pytest.approx(1.7)
    doc.close()


def test_set_start_xref_accepts_negative() -> None:
    # Upstream ``setStartXref`` stores the argument verbatim with no sign
    # check (oracle-confirmed, wave 1537).
    doc = COSDocument()
    doc.set_start_xref(-1)
    assert doc.get_start_xref() == -1
    doc.close()


def test_set_highest_xref_object_number_accepts_negative() -> None:
    # Upstream ``setHighestXRefObjectNumber`` stores the argument verbatim
    # with no sign check (oracle-confirmed, wave 1537).
    doc = COSDocument()
    doc.set_highest_xref_object_number(-1)
    assert doc.get_highest_xref_object_number() == -1
    doc.close()


def test_set_xref_stream_flag_round_trip() -> None:
    doc = COSDocument()
    assert doc.is_xref_stream() is False
    doc.set_is_xref_stream(True)
    assert doc.is_xref_stream() is True
    # Token-split alias.
    assert doc.is_x_ref_stream() is True
    doc.set_is_x_ref_stream(False)
    assert doc.is_xref_stream() is False
    doc.close()


def test_hybrid_xref_flag_is_one_way() -> None:
    doc = COSDocument()
    assert doc.has_hybrid_xref() is False
    doc.set_has_hybrid_xref()
    assert doc.has_hybrid_xref() is True
    assert doc.has_hybrid_x_ref() is True
    doc.close()


# ---------- lifecycle ----------


def test_close_is_idempotent() -> None:
    doc = COSDocument()
    doc.close()
    assert doc.is_closed() is True
    # Second close must not raise.
    doc.close()
    assert doc.is_closed() is True


def test_context_manager_closes_on_exit() -> None:
    with COSDocument() as doc:
        assert doc.is_closed() is False
    assert doc.is_closed() is True


def test_close_clears_pool_and_xref() -> None:
    doc = COSDocument()
    doc.get_object_from_pool(COSObjectKey(1, 0))
    doc.add_xref_table({COSObjectKey(2, 0): 100})
    doc.close()
    assert doc.get_objects() == []
    assert doc.get_xref_table() == {}


# ---------- create_cos_stream ----------


def test_create_cos_stream_copies_dictionary_entries() -> None:
    doc = COSDocument()
    seed = COSDictionary(
        [
            ("Length", COSInteger.get(7)),
            ("Type", COSName.get_pdf_name("Foo")),
        ]
    )
    stream = doc.create_cos_stream(seed)
    assert stream.get_int("Length") == 7
    assert stream.get_name("Type") == "Foo"
    stream.close()
    doc.close()


def test_create_cos_stream_uses_document_scratch() -> None:
    doc = COSDocument()
    stream = doc.create_cos_stream()
    # The stream borrows the document scratch — closing the stream must
    # not close the document scratch.
    stream.close()
    assert doc.scratch_file.is_closed() is False
    doc.close()
    assert doc.scratch_file.is_closed() is True


def test_visitor_dispatch_visit_from_document() -> None:
    from tests.cos.helpers import RecordingVisitor

    doc = COSDocument()
    visitor = RecordingVisitor()
    doc.accept(visitor)
    assert visitor.calls == [("document", doc)]
    doc.close()


def test_repr_contains_version_and_objects() -> None:
    doc = COSDocument()
    rendered = repr(doc)
    assert "COSDocument" in rendered
    assert "version=" in rendered
    assert "objects=" in rendered
    doc.close()
