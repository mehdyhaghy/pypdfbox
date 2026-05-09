from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.annotation_border import (
    AnnotationBorder,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


def test_wave364_legacy_border_uses_default_border_width() -> None:
    annotation = PDAnnotation()

    border = AnnotationBorder.get_annotation_border(annotation, None)

    assert border.width == 1.0
    assert border.dash_array is None
    assert border.underline is False


def test_wave364_legacy_border_reads_numeric_width_and_dash_array() -> None:
    annotation = PDAnnotation()
    dash = COSArray([COSInteger.get(4), COSFloat(1.5)])
    annotation.set_border(
        COSArray([COSInteger.get(0), COSInteger.get(0), COSFloat(2.25), dash])
    )

    border = AnnotationBorder.get_annotation_border(annotation, None)

    assert border.width == 2.25
    assert border.dash_array == [4.0, 1.5]
    assert border.underline is False


def test_wave364_legacy_border_ignores_nonnumeric_width() -> None:
    annotation = PDAnnotation()
    annotation.set_border(
        COSArray(
            [
                COSInteger.get(0),
                COSInteger.get(0),
                COSName.get_pdf_name("Wide"),
            ]
        )
    )

    border = AnnotationBorder.get_annotation_border(annotation, None)

    assert border.width == 0.0
    assert border.dash_array is None
    assert border.underline is False


def test_wave364_zero_dash_arrays_are_dropped_for_legacy_and_style_paths() -> None:
    annotation = PDAnnotation()
    annotation.set_border(
        COSArray(
            [
                COSInteger.get(0),
                COSInteger.get(0),
                COSInteger.get(3),
                COSArray([COSInteger.get(0), COSFloat(0.0)]),
            ]
        )
    )

    legacy_border = AnnotationBorder.get_annotation_border(annotation, None)

    border_style = PDBorderStyleDictionary()
    border_style.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    border_style.set_dash_style([0.0, 0.0])
    styled_border = AnnotationBorder.get_annotation_border(annotation, border_style)

    assert legacy_border.width == 3.0
    assert legacy_border.dash_array is None
    assert styled_border.width == 1.0
    assert styled_border.dash_array is None


def test_wave364_underline_style_sets_flag_without_dash_array() -> None:
    annotation = PDAnnotation()
    border_style = PDBorderStyleDictionary()
    border_style.set_width(5)
    border_style.set_style(PDBorderStyleDictionary.STYLE_UNDERLINE)

    border = AnnotationBorder.get_annotation_border(annotation, border_style)

    assert border.width == 5.0
    assert border.dash_array is None
    assert border.underline is True
