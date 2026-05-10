"""Ported from upstream PDFBox ``FDFFieldTest``.

Upstream Java path:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/fdf/FDFFieldTest.java``
(PDFBox 3.0.x).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream, COSString
from pypdfbox.pdmodel.fdf import FDFField


def test_cos_string_value() -> None:
    """Upstream: ``testCOSStringValue``."""
    test_string = "Test value"
    test_cos_string = COSString(test_string)

    field = FDFField()
    field.set_value(test_cos_string)

    assert field.get_cos_value() == test_cos_string
    assert field.get_value() == test_string


def test_text_as_cos_stream_value() -> None:
    """Upstream: ``testTextAsCOSStreamValue``."""
    test_string = "Test value"
    stream = COSStream()
    stream.set_data(test_string.encode("ascii"))

    field = FDFField()
    field.set_value(stream)

    assert field.get_value() == test_string


def test_cos_name_value() -> None:
    """Upstream: ``testCOSNameValue``."""
    test_string = "Yes"
    test_cos_name = COSName.get_pdf_name(test_string)

    field = FDFField()
    field.set_value(test_cos_name)

    assert field.get_cos_value() == test_cos_name
    assert field.get_value() == test_string


def test_cos_array_value() -> None:
    """Upstream: ``testCOSArrayValue``."""
    test_list = ["A", "B"]
    test_cos_array = COSArray()
    for item in test_list:
        test_cos_array.add(COSString(item))

    field = FDFField()
    field.set_value(test_cos_array)

    assert field.get_cos_value() == test_cos_array
    assert field.get_value() == test_list


# --- supplemental coverage for getters/setters mirrored from upstream ---


def test_kids_round_trip() -> None:
    parent = FDFField()
    parent.set_partial_field_name("group")
    child = FDFField()
    child.set_partial_field_name("inner")
    parent.set_kids([child])

    kids = parent.get_kids()
    assert kids is not None and len(kids) == 1
    assert kids[0].get_partial_field_name() == "inner"
