"""Wave 1351 coverage boost: ``FDFAnnotationFreeText`` /RD lenient coercion.

Exercises ``get_fringe()`` when ``/RD`` is a 4-entry COSArray whose
entries are non-numeric. Mirroring upstream ``new PDRectangle(COSArray)``,
``PDRectangle.from_cos_array`` coerces each non-numeric slot to ``0.0``
and normalizes corners, so the annotation returns a real (zeroed)
rectangle rather than ``None``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationFreeText
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_get_fringe_coerces_non_numeric_entries_to_zero_rectangle() -> None:
    """4-entry /RD whose entries are non-numeric COSNames: every slot
    coerces to ``0.0`` (matching upstream ``new PDRectangle(COSArray)``),
    so the annotation returns ``PDRectangle(0, 0, 0, 0)``.
    """
    annot = COSDictionary()
    annot.set_name("Subtype", "FreeText")
    arr = COSArray()
    for _ in range(4):
        arr.add(COSName.A)
    annot.set_item(COSName.get_pdf_name("RD"), arr)
    ann = FDFAnnotationFreeText(annot)
    assert ann.get_fringe() == PDRectangle(0.0, 0.0, 0.0, 0.0)
