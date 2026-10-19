"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSUpdateInfo.java

Upstream tests the ``COSUpdateInfo`` interface plus ``COSDocumentState``
machinery used by the incremental-save path.
"""

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSDocumentState,
    COSName,
    COSObject,
)


def test_is_set_need_to_be_update() -> None:
    origin = COSDocumentState()
    origin.set_parsing(False)

    test_cos_dictionary = COSDictionary()
    test_cos_dictionary.set_needs_to_be_updated(True)
    assert test_cos_dictionary.is_needs_to_be_updated() is False
    test_cos_dictionary.get_update_state().set_origin_document_state(origin)
    test_cos_dictionary.set_needs_to_be_updated(True)
    assert test_cos_dictionary.is_needs_to_be_updated() is True
    test_cos_dictionary.set_needs_to_be_updated(False)
    assert test_cos_dictionary.is_needs_to_be_updated() is False

    test_cos_object = COSObject(0)
    test_cos_object.set_needs_to_be_updated(True)
    assert test_cos_object.is_needs_to_be_updated() is False
    test_cos_object.get_update_state().set_origin_document_state(origin)
    test_cos_object.set_needs_to_be_updated(True)
    assert test_cos_object.is_needs_to_be_updated() is True
    test_cos_object.set_needs_to_be_updated(False)
    assert test_cos_object.is_needs_to_be_updated() is False


def test_set_origin_document_state_of_deeply_nested_structure() -> None:
    """PDFBOX-6200: linking a document state to a deeply nested structure
    must not overflow the stack."""
    origin = COSDocumentState()
    origin.set_parsing(False)

    # a chain of dictionaries, arrays and dereferenced indirect objects,
    # built from the end
    deepest = COSDictionary()
    current: COSBase = deepest
    for i in range(50_000):
        if i % 3 == 0:
            dictionary = COSDictionary()
            dictionary.set_item(COSName.get_pdf_name("Next"), current)
            current = dictionary
        elif i % 3 == 1:
            array = COSArray()
            array.add(current)
            current = array
        else:
            current = COSObject(0, resolved=current)
    root = current

    root.get_update_state().set_origin_document_state(origin)  # type: ignore[attr-defined]

    assert deepest.get_update_state().get_origin_document_state() is origin
    assert root.is_needs_to_be_updated()  # type: ignore[attr-defined]
    assert deepest.is_needs_to_be_updated()
