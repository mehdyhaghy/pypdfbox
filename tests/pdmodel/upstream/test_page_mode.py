"""Ported from upstream PDFBox 3.0:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PageModeTest.java``."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.page_mode import PageMode


def test_from_string_input_not_null_output_not_null() -> None:
    value = "FullScreen"
    retval = PageMode.from_string(value)
    assert retval == PageMode.FULL_SCREEN


def test_from_string_input_not_null_output_not_null2() -> None:
    value = "UseThumbs"
    retval = PageMode.from_string(value)
    assert retval == PageMode.USE_THUMBS


def test_from_string_input_not_null_output_not_null3() -> None:
    value = "UseOC"
    retval = PageMode.from_string(value)
    assert retval == PageMode.USE_OPTIONAL_CONTENT


def test_from_string_input_not_null_output_not_null4() -> None:
    value = "UseNone"
    retval = PageMode.from_string(value)
    assert retval == PageMode.USE_NONE


def test_from_string_input_not_null_output_not_null5() -> None:
    value = "UseAttachments"
    retval = PageMode.from_string(value)
    assert retval == PageMode.USE_ATTACHMENTS


def test_from_string_input_not_null_output_not_null6() -> None:
    value = "UseOutlines"
    retval = PageMode.from_string(value)
    assert retval == PageMode.USE_OUTLINES


def test_from_string_input_not_null_output_illegal_argument_exception() -> None:
    # Upstream raises ``IllegalArgumentException``; the Python analogue is
    # ``ValueError``.
    with pytest.raises(ValueError):
        PageMode.from_string("")


def test_from_string_input_not_null_output_illegal_argument_exception2() -> None:
    with pytest.raises(ValueError):
        PageMode.from_string("Dulacb`ecj")


def test_string_value_output_not_null() -> None:
    object_under_test = PageMode.USE_OPTIONAL_CONTENT
    retval = object_under_test.string_value()
    assert retval == "UseOC"
