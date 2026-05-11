from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_RD: COSName = COSName.get_pdf_name("RD")
_SY: COSName = COSName.get_pdf_name("SY")


class FDFAnnotationCaret(FDFAnnotation):
    """FDF Caret annotation — ``/Subtype /Caret``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationCaret`` (Java
    lines 32-138).
    """

    SUBTYPE: str = "Caret"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /RD fringe rectangle ----------

    def set_fringe(self, fringe: PDRectangle | None) -> None:
        """Set the fringe rectangle (``/RD``).

        Mirrors upstream ``setFringe(PDRectangle)`` (Java line 97).
        """
        if fringe is None:
            self._annot.remove_item(_RD)
            return
        self._annot.set_item(_RD, fringe.to_cos_array())

    def get_fringe(self) -> PDRectangle | None:
        """Return the fringe rectangle (``/RD``) or ``None``.

        Mirrors upstream ``getFringe()`` (Java line 108).
        """
        rd = self._annot.get_dictionary_object(_RD)
        if isinstance(rd, COSArray) and len(rd) >= 4:
            try:
                return PDRectangle.from_cos_array(rd)
            except (TypeError, ValueError):
                return None
        return None

    def init_fringe(self, fringe: str | None) -> None:
        """Initialise ``/RD`` from an XFDF ``fringe`` attribute string.

        Mirrors upstream private ``initFringe(Element)`` (Java line 79).
        """
        if fringe is None or not fringe:
            return
        rect = self.create_rectangle_from_attributes(
            fringe, "Error: wrong amount of numbers in attribute 'fringe'"
        )
        self.set_fringe(rect)

    # ---------- /SY symbol ----------

    def set_symbol(self, symbol: str | None) -> None:
        """Set the caret symbol (``/SY`` — ``"None"`` or ``"P"``).

        Mirrors upstream ``setSymbol(String)`` (Java line 119).
        """
        new_symbol = "None"
        if symbol == "paragraph":
            new_symbol = "P"
        self._annot.set_string(_SY, new_symbol)

    def get_symbol(self) -> str | None:
        """Return the caret symbol (``/SY``) or ``None``.

        Mirrors upstream ``getSymbol()`` (Java line 134).
        """
        return self._annot.get_string(_SY)


__all__ = ["FDFAnnotationCaret"]
