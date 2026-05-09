from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem


def test_abstract_destination_get_cos_object_raises_not_implemented() -> None:
    destination = PDDestination()

    with pytest.raises(NotImplementedError):
        destination.get_cos_object()


def test_named_destination_bytes_constructor_uses_string_form() -> None:
    destination = PDNamedDestination(b"chapter-811")

    assert destination.is_string_form() is True
    assert destination.get_named_destination() == "chapter-811"


def test_fit_height_short_array_reports_left_unset() -> None:
    destination = PDPageFitHeightDestination(COSArray())

    assert destination.is_left_unset() is True


def test_fit_width_short_array_reports_top_unset() -> None:
    destination = PDPageFitWidthDestination(COSArray())

    assert destination.is_top_unset() is True


def test_fit_rectangle_short_array_reports_missing_top_unset() -> None:
    destination = PDPageFitRectangleDestination(COSArray())

    assert destination.is_top_unset() is True


def test_outline_text_color_rejects_array_with_non_numeric_component() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(
        COSName.C,
        COSArray([COSFloat(0.25), COSName.get_pdf_name("Bad"), COSFloat(0.75)]),
    )

    assert item.get_text_color() is None
