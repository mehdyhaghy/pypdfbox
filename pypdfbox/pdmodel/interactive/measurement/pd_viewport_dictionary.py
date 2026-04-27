from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

if TYPE_CHECKING:
    from .pd_measure_dictionary import PDMeasureDictionary

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_BBOX: COSName = COSName.get_pdf_name("BBox")
_NAME: COSName = COSName.get_pdf_name("Name")
_MEASURE: COSName = COSName.get_pdf_name("Measure")


class PDViewportDictionary:
    """This class represents a viewport dictionary.

    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.interactive.measurement.PDViewportDictionary``.
    """

    TYPE = "Viewport"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        """Return the underlying ``COSDictionary``."""
        return self._dict

    def get_type(self) -> str:
        """Return the type of the viewport dictionary, always ``"Viewport"``."""
        return self.TYPE

    def get_b_box(self) -> PDRectangle | None:
        """Retrieve the rectangle specifying the location of the viewport."""
        bbox = self._dict.get_dictionary_object(_BBOX)
        if isinstance(bbox, COSArray):
            return PDRectangle.from_cos_array(bbox)
        return None

    def set_b_box(self, rectangle: PDRectangle | None) -> None:
        """Set the rectangle specifying the location of the viewport."""
        if rectangle is None:
            self._dict.remove_item(_BBOX)
            return
        self._dict.set_item(_BBOX, rectangle.get_cos_object())

    def get_name(self) -> str | None:
        """Retrieve the name of the viewport."""
        return self._dict.get_name(_NAME)

    def set_name(self, name: str | None) -> None:
        """Set the name of the viewport."""
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)

    def get_measure(self) -> PDMeasureDictionary | None:
        """Retrieve the measure dictionary."""
        from .pd_measure_dictionary import PDMeasureDictionary

        base = self._dict.get_dictionary_object(_MEASURE)
        if isinstance(base, COSDictionary):
            return PDMeasureDictionary(base)
        return None

    def set_measure(self, measure: PDMeasureDictionary | None) -> None:
        """Set the measure dictionary."""
        if measure is None:
            self._dict.remove_item(_MEASURE)
            return
        self._dict.set_item(_MEASURE, measure.get_cos_object())


__all__ = ["PDViewportDictionary"]
