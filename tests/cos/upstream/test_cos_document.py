"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/COSDocumentTest.java
"""

from __future__ import annotations

from pypdfbox.cos import COSDocument, COSName


def test_pdfbox6132() -> None:
    document = COSDocument()
    # Map<COSObjectKey, Long> with a null key — PDFBOX-6132 corrupted xref
    # entry. add_xref_table must silently skip the null key without raising.
    xref_table: dict = {None: 10}
    document.add_xref_table(xref_table)
    assert document.get_objects_by_type(COSName.T) == []  # type: ignore[attr-defined]
    assert document.get_linearized_dictionary() is None
    document.close()
