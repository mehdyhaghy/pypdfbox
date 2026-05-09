"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSUpdateInfo.java

Upstream tests the ``COSUpdateInfo`` interface plus ``COSDocumentState``
machinery used by the incremental-save path.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSDocumentState, COSObject


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
