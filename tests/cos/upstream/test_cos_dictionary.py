"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/COSDictionaryTest.java
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream


def test_cos_dictionary_not_equals_cos_stream() -> None:
    cos_dictionary = COSDictionary()
    cos_stream = COSStream()
    cos_dictionary.set_item(COSName.BE, COSName.BE)  # type: ignore[attr-defined]
    cos_dictionary.set_int(COSName.LENGTH, 0)  # type: ignore[attr-defined]
    cos_stream.set_item(COSName.BE, COSName.BE)  # type: ignore[attr-defined]
    assert cos_dictionary != cos_stream, (
        "a COSDictionary shall not be equal to a COSStream with the same dictionary entries"
    )
    assert cos_stream != cos_dictionary, (
        "a COSStream shall not be equal to a COSDictionary with the same dictionary entries"
    )
    cos_stream.close()
