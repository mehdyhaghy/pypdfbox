"""Wave 1351 coverage boost: ``FDFAnnotationFreeText`` /RD parse-error swallow.

Targets lines 169-170 of
``pypdfbox/pdmodel/fdf/fdf_annotation_free_text.py`` — the
``except (TypeError, ValueError): return None`` arm of
``get_fringe()`` when ``/RD`` is a 4-entry COSArray but the entries
are non-numeric.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationFreeText


def test_get_fringe_returns_none_when_entries_non_numeric() -> None:
    """4-entry /RD whose entries are non-numeric COSNames triggers
    ``PDRectangle.from_cos_array`` to raise ``TypeError``; the
    annotation swallows it and returns ``None``.
    """
    annot = COSDictionary()
    annot.set_name("Subtype", "FreeText")
    arr = COSArray()
    for _ in range(4):
        arr.add(COSName.A)
    annot.set_item(COSName.get_pdf_name("RD"), arr)
    ann = FDFAnnotationFreeText(annot)
    assert ann.get_fringe() is None
