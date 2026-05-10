from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_DA: COSName = COSName.get_pdf_name("DA")
_Q: COSName = COSName.get_pdf_name("Q")
_DS: COSName = COSName.get_pdf_name("DS")
_CL: COSName = COSName.get_pdf_name("CL")
_RD: COSName = COSName.get_pdf_name("RD")
# Upstream uses COSName.ROTATE which resolves to the PDF name "Rotate".
_ROTATE: COSName = COSName.get_pdf_name("Rotate")
_LE: COSName = COSName.get_pdf_name("LE")


class FDFAnnotationFreeText(FDFAnnotation):
    """FDF free text annotation - ``/Subtype /FreeText``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationFreeText``.
    """

    SUBTYPE: str = "FreeText"

    # /Q justification constants (PDF 32000-1 §12.7.3.3 Table 230). Kept as
    # pypdfbox conveniences; upstream exposes the integer-as-string only.
    QUADDING_LEFT: int = 0
    QUADDING_CENTERED: int = 1
    QUADDING_RIGHT: int = 2

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /CL callout line (4- or 6-element float array) ----------

    def set_callout(self, callout: list[float] | None) -> None:
        """Set the coordinates of the callout line.

        Mirrors upstream ``setCallout(float[])`` (lines 132-137). ``None``
        removes the entry; pypdfbox accepts ``None`` while upstream relies on
        ``setFloatArray`` which requires a non-null reference.
        """
        if callout is None:
            self._annot.remove_item(_CL)
            return
        arr = COSArray([COSFloat(float(c)) for c in callout])
        self._annot.set_item(_CL, arr)

    def get_callout(self) -> list[float] | None:
        """Return the callout line coordinates, or ``None`` when /CL is absent.

        Mirrors upstream ``getCallout()`` (lines 147-151).
        """
        v = self._annot.get_dictionary_object(_CL)
        if isinstance(v, COSArray):
            return v.to_float_array()
        return None

    # ---------- /Q justification ----------

    def set_justification(self, justification: str | int) -> None:
        """Set the form of quadding (justification) of the annotation text.

        Mirrors upstream ``setJustification(String)`` (lines 158-170): values
        ``"centered"`` -> 1, ``"right"`` -> 2, anything else -> 0. As a
        pypdfbox convenience we also accept an int (used by the existing
        QUADDING_* constants and round-trip tests).
        """
        if isinstance(justification, str):
            if justification == "centered":
                quadding = 1
            elif justification == "right":
                quadding = 2
            else:
                quadding = 0
        else:
            quadding = int(justification)
        self._annot.set_int(_Q, quadding)

    def get_justification(self) -> str:
        """Return the quadding (justification) of the annotation text.

        Mirrors upstream ``getJustification()`` (lines 177-180), which returns
        the integer value as a string (e.g. ``"0"``, ``"1"``, ``"2"``).
        """
        return str(self._annot.get_int(_Q, 0))

    def get_justification_int(self) -> int:
        """Return the raw integer quadding value (pypdfbox convenience)."""
        return self._annot.get_int(_Q, 0)

    # ---------- /Rotate clockwise rotation ----------

    def set_rotation(self, rotation: int) -> None:
        """Set the clockwise rotation in degrees.

        Mirrors upstream ``setRotation(int)`` (lines 187-190).
        """
        self._annot.set_int(_ROTATE, int(rotation))

    def get_rotation(self) -> str | None:
        """Return the clockwise rotation in degrees as a string.

        Mirrors upstream ``getRotation()`` (lines 197-200) which returns the
        ``/Rotate`` value via ``getString``; that yields ``None`` when absent
        and the integer's decimal representation when present.
        """
        return self._annot.get_string(_ROTATE)

    # ---------- /DA default appearance ----------

    def set_default_appearance(self, appearance: str | None) -> None:
        """Set the default appearance string.

        Mirrors upstream ``setDefaultAppearance(String)`` (lines 207-210).
        """
        self._annot.set_string(_DA, appearance)

    def get_default_appearance(self) -> str | None:
        """Return the default appearance string.

        Mirrors upstream ``getDefaultAppearance()`` (lines 217-221).
        """
        return self._annot.get_string(_DA)

    # ---------- /DS default style string ----------

    def set_default_style(self, style: str | None) -> None:
        """Set the default style string.

        Mirrors upstream ``setDefaultStyle(String)`` (lines 228-231).
        """
        self._annot.set_string(_DS, style)

    def get_default_style(self) -> str | None:
        """Return the default style string.

        Mirrors upstream ``getDefaultStyle()`` (lines 238-241).
        """
        return self._annot.get_string(_DS)

    # ---------- /RD fringe rectangle ----------

    def set_fringe(self, fringe: PDRectangle | None) -> None:
        """Set the fringe rectangle.

        Mirrors upstream ``setFringe(PDRectangle)`` (lines 250-253). The fringe
        is the difference between the annotation rectangle and where drawing
        actually occurs (e.g. for /BE border-effect insets).
        """
        if fringe is None:
            self._annot.remove_item(_RD)
            return
        self._annot.set_item(_RD, fringe.to_cos_array())

    def get_fringe(self) -> PDRectangle | None:
        """Return the fringe rectangle.

        Mirrors upstream ``getFringe()`` (lines 261-265).
        """
        v = self._annot.get_dictionary_object(_RD)
        if isinstance(v, COSArray) and len(v) >= 4:
            try:
                return PDRectangle.from_cos_array(v)
            except (TypeError, ValueError):
                return None
        return None

    # ---------- /LE line-ending style ----------

    def set_line_ending_style(self, style: str | None) -> None:
        """Set the line-ending style.

        Mirrors upstream ``setLineEndingStyle(String)`` (lines 272-275).
        """
        if style is None:
            self._annot.remove_item(_LE)
        else:
            self._annot.set_item(_LE, COSName.get_pdf_name(style))

    def get_line_ending_style(self) -> str | None:
        """Return the line-ending style for the start point.

        Mirrors upstream ``getLineEndingStyle()`` (lines 282-285).
        """
        return self._annot.get_name_as_string(_LE)

    # ---------- XFDF init helpers (protected, mirror upstream private) ----------

    def init_callout(self, callout: str | None) -> None:
        """Initialise /CL from an XFDF ``callout`` attribute string.

        Mirrors upstream ``initCallout(Element)`` (lines 113-122). Accepts the
        attribute value directly (comma-separated floats); empty/None is a
        no-op so callers can forward ``element.getAttribute("callout")``.
        """
        if callout is None or not callout:
            return
        values = self.parse_floats(callout.split(","))
        self.set_callout(values)

    def init_fringe(self, fringe: str | None) -> None:
        """Initialise /RD from an XFDF ``fringe`` attribute string.

        Mirrors upstream ``initFringe(Element)`` (lines 102-111). Accepts the
        attribute value directly (comma-separated 4-tuple); empty/None is a
        no-op so callers can forward ``element.getAttribute("fringe")``.
        Raises :class:`OSError` (Python equivalent of Java ``IOException``)
        when the value is not exactly four floats.
        """
        if fringe is None or not fringe:
            return
        rect = self.create_rectangle_from_attributes(
            fringe, "Error: wrong amount of numbers in attribute 'fringe'"
        )
        self.set_fringe(rect)


__all__ = ["FDFAnnotationFreeText"]
