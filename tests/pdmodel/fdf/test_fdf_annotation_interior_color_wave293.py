from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.fdf import (
    FDFAnnotationCircle,
    FDFAnnotationLine,
    FDFAnnotationSquare,
)


@pytest.mark.parametrize(
    "annotation_cls",
    [FDFAnnotationSquare, FDFAnnotationCircle, FDFAnnotationLine],
)
def test_interior_color_presence_and_clear_helpers(annotation_cls: type) -> None:
    annotation = annotation_cls()

    assert annotation.has_interior_color() is False

    annotation.set_interior_color((0.1, 0.2, 0.3))
    assert annotation.has_interior_color() is True
    assert annotation.get_interior_color() == pytest.approx((0.1, 0.2, 0.3), abs=1e-6)

    annotation.clear_interior_color()
    assert annotation.has_interior_color() is False
    assert annotation.get_interior_color() is None


@pytest.mark.parametrize(
    "annotation_cls",
    [FDFAnnotationSquare, FDFAnnotationCircle, FDFAnnotationLine],
)
def test_malformed_interior_color_reports_absent(annotation_cls: type) -> None:
    annotation = annotation_cls()
    annotation.get_cos_object().set_item(
        COSName.get_pdf_name("IC"),
        COSArray(
            [
                COSInteger.get(1),
                COSName.get_pdf_name("Bad"),
                COSInteger.get(3),
            ]
        ),
    )

    assert annotation.get_interior_color() is None
    assert annotation.has_interior_color() is False
