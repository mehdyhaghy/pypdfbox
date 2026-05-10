"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/COSDocumentTest.java
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSDocument, COSName, COSObjectKey


def test_pdfbox6132() -> None:
    document = COSDocument()
    # Map<COSObjectKey, Long> with a null key — PDFBOX-6132 corrupted xref
    # entry. add_xref_table must silently skip the null key without raising.
    xref_table: dict = {None: 10}
    document.add_xref_table(xref_table)
    assert document.get_objects_by_type(COSName.T) == []  # type: ignore[attr-defined]
    assert document.get_linearized_dictionary() is None
    document.close()


def test_get_xref_table() -> None:
    # Mirrors PDFBox COSDocumentTest#testGetXrefTable: round-trip a table
    # built directly via add_xref_table and confirm getXrefTable() returns
    # exactly what was stored (minus null keys).
    document = COSDocument()
    expected = {
        COSObjectKey(1, 0): 0,
        COSObjectKey(2, 0): 17,
        COSObjectKey(3, 0): 200,
    }
    document.add_xref_table(dict(expected))
    assert document.get_xref_table() == expected
    document.close()


def test_get_object() -> None:
    # Mirrors PDFBox: getObject(COSObjectKey) returns null for keys that have
    # not been registered.
    document = COSDocument()
    assert document.get_object(COSObjectKey(99, 0)) is None
    placeholder = document.get_object_from_pool(COSObjectKey(99, 0))
    assert document.get_object(COSObjectKey(99, 0)) is placeholder
    document.close()


def test_set_warn_missing_close() -> None:
    # Mirrors PDFBox: setWarnMissingClose toggles the finalizer warning. We
    # only assert that the setter is callable and idempotent.
    document = COSDocument()
    document.set_warn_missing_close(False)
    document.set_warn_missing_close(True)
    document.close()


def test_set_is_xref_stream() -> None:
    # Mirrors PDFBox: setIsXRefStream/isXRefStream marker round-trip.
    document = COSDocument()
    assert not document.is_xref_stream()
    document.set_is_xref_stream(True)
    assert document.is_xref_stream()
    document.close()


def test_set_highest_xref_object_number() -> None:
    # Mirrors PDFBox: setHighestXRefObjectNumber stores the value used by the
    # writer when allocating new objects.
    document = COSDocument()
    document.set_highest_xref_object_number(123)
    assert document.get_highest_xref_object_number() == 123
    document.close()


def test_get_encryption_dictionary() -> None:
    # Encryption dictionary is resolved from the trailer's /Encrypt entry.
    document = COSDocument()
    enc = COSDictionary()
    enc.set_int("V", 4)
    trailer = COSDictionary()
    trailer.set_item(COSName.ENCRYPT, enc)  # type: ignore[attr-defined]
    document.set_trailer(trailer)
    assert document.get_encryption_dictionary() is enc
    document.close()


def test_get_linearized_dictionary_none_for_nonlinearized() -> None:
    # Mirrors PDFBox COSDocumentTest#testPDFBox6132 (extracted): with no
    # /Linearized-bearing dict in the pool, the lookup returns None.
    document = COSDocument()
    document.add_xref_table({COSObjectKey(1, 0): 100})
    assert document.get_linearized_dictionary() is None
    document.close()


def test_objects_by_type_skips_pool_entries_with_no_xref_membership() -> None:
    # Mirrors PDFBox COSDocumentTest behavior — objects without an entry in
    # the xref table still resolve via the pool. PDFBOX-6132 specifically
    # ensures a null xref key does not poison the lookup.
    from pypdfbox.cos.cos_object import COSObject

    document = COSDocument()
    page = COSDictionary()
    page.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))  # type: ignore[attr-defined]
    pool_obj = COSObject(1, 0)
    pool_obj.set_object(page)
    document._objects[COSObjectKey(1, 0)] = pool_obj
    # PDFBOX-6132: corrupted xref entry — must be tolerated.
    document.add_xref_table({None: 10})
    assert document.get_objects_by_type(COSName.get_pdf_name("Page")) == [pool_obj]
    document.close()


def test_set_decrypted_one_way() -> None:
    # Mirrors PDFBox: setDecrypted has no boolean parameter — it only flips
    # the flag from False to True.
    document = COSDocument()
    assert document.is_decrypted() is False
    document.set_decrypted()
    assert document.is_decrypted() is True
    document.close()
