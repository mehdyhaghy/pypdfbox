from __future__ import annotations

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.annotation_border import (
    AnnotationBorder,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


def test_wave325_dashed_border_style_without_dash_array_uses_default() -> None:
    annotation = PDAnnotation()
    border_style = PDBorderStyleDictionary()
    border_style.set_style(PDBorderStyleDictionary.STYLE_DASHED)

    border = AnnotationBorder.get_annotation_border(annotation, border_style)

    assert border.width == 1.0
    assert border.underline is False
    assert border.dash_array == [3.0]
    stored_dash = border_style.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("D")
    )
    assert isinstance(stored_dash, COSArray)
    assert stored_dash.to_float_array() == [3.0]
