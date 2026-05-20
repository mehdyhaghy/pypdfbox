"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/state/RenderingIntentTest.java

Upstream baseline: PDFBox 3.0.x.
"""
from __future__ import annotations

from pypdfbox.pdmodel.graphics.state import RenderingIntent
from pypdfbox.pdmodel.graphics.state.rendering_mode import RenderingMode


def test_from_string_input_not_null_output_not_null() -> None:
    value = "AbsoluteColorimetric"
    retval = RenderingIntent.from_string(value)
    assert retval == RenderingIntent.ABSOLUTE_COLORIMETRIC


def test_from_string_input_not_null_output_not_null2() -> None:
    value = "RelativeColorimetric"
    retval = RenderingIntent.from_string(value)
    assert retval == RenderingIntent.RELATIVE_COLORIMETRIC


def test_from_string_input_not_null_output_not_null3() -> None:
    value = "Perceptual"
    retval = RenderingIntent.from_string(value)
    assert retval == RenderingIntent.PERCEPTUAL


def test_from_string_input_not_null_output_not_null4() -> None:
    value = "Saturation"
    retval = RenderingIntent.from_string(value)
    assert retval == RenderingIntent.SATURATION


def test_from_string_input_not_null_output_not_null5() -> None:
    value = ""
    retval = RenderingIntent.from_string(value)
    assert retval == RenderingIntent.RELATIVE_COLORIMETRIC


def test_string_value_output_not_null() -> None:
    object_under_test = RenderingIntent.ABSOLUTE_COLORIMETRIC
    retval = object_under_test.string_value()
    assert retval == "AbsoluteColorimetric"


def test_is_fill() -> None:
    object_under_test = RenderingMode.FILL
    retval = object_under_test.is_fill()
    assert retval is True
