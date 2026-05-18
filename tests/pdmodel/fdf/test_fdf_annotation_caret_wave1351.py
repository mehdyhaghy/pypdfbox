"""Wave 1351 coverage boost: ``FDFAnnotationCaret`` /RD parse-error swallow.

Targets lines 48-49 of
``pypdfbox/pdmodel/fdf/fdf_annotation_caret.py`` — the
``except (TypeError, ValueError): return None`` arm of
``get_fringe()`` when ``/RD`` is a 4-entry COSArray but the entries
are non-numeric (``PDRectangle.from_cos_array`` raises ``TypeError``).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationCaret


def test_get_fringe_returns_none_when_entries_non_numeric() -> None:
    """4-entry /RD whose entries are non-numeric COSNames triggers
    ``PDRectangle.from_cos_array`` to raise ``TypeError``; the
    annotation swallows it and returns ``None``.
    """
    annot = COSDictionary()
    annot.set_name("Subtype", "Caret")
    arr = COSArray()
    for _ in range(4):
        arr.add(COSName.A)  # non-numeric — triggers TypeError
    annot.set_item(COSName.get_pdf_name("RD"), arr)
    caret = FDFAnnotationCaret(annot)
    assert caret.get_fringe() is None
