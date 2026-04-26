"""Ported from pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
annotation/PDSquareAnnotationTest.java (PDFBox 3.0.x)."""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationSquare


def test_create_default_square_annotation() -> None:
    annotation = PDAnnotationSquare()
    assert annotation.get_cos_object().get_item(COSName.TYPE) == COSName.get_pdf_name("Annot")  # type: ignore[attr-defined]
    assert (
        annotation.get_cos_object().get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        == PDAnnotationSquare.SUB_TYPE
    )


# createWithAppearance / validateAppearance: skipped — depend on
# PDBorderStyleDictionary, PDColor, PDDeviceRGB, constructAppearances,
# and the appearance-stream content-stream tokeniser, none of which ship
# in pdmodel cluster #5 lite.
