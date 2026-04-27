from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSName

_TYPE: COSName = COSName.get_pdf_name("Type")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_ANNOT: COSName = COSName.get_pdf_name("Annot")
_PAGE: COSName = COSName.get_pdf_name("Page")
_NM: COSName = COSName.get_pdf_name("NM")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_T: COSName = COSName.get_pdf_name("T")
_RECT: COSName = COSName.get_pdf_name("Rect")
_C: COSName = COSName.get_pdf_name("C")
_F: COSName = COSName.get_pdf_name("F")
_NAME: COSName = COSName.get_pdf_name("Name")
_M: COSName = COSName.get_pdf_name("M")


class FDFAnnotation:
    """Base class for an FDF annotation entry inside ``/Annots``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotation``. Subtype-specific
    classes (e.g. ``FDFAnnotationText``, ``FDFAnnotationFreeText``) are
    deferred to a later wave; this base exposes the common entries that all
    FDF annotation dictionaries share (``/Page``, ``/NM``, ``/Contents``,
    ``/T`` author, ``/Rect``, ``/C`` colour, ``/F`` flags, ``/Name``,
    ``/M`` modified).
    """

    def __init__(self, annot: COSDictionary | None = None) -> None:
        self._annot: COSDictionary = annot if annot is not None else COSDictionary()
        # Stamp /Type Annot when none present (matches upstream constructor).
        if self._annot.get_dictionary_object(_TYPE) is None:
            self._annot.set_item(_TYPE, _ANNOT)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._annot

    # ---------- /Page (0-based page index) ----------

    def get_page(self) -> int:
        return self._annot.get_int(_PAGE)

    def set_page(self, page: int) -> None:
        self._annot.set_int(_PAGE, page)

    # ---------- /NM unique name ----------

    def get_name(self) -> str | None:
        return self._annot.get_string(_NM)

    def set_name(self, name: str | None) -> None:
        self._annot.set_string(_NM, name)

    # ---------- /Contents ----------

    def get_contents(self) -> str | None:
        return self._annot.get_string(_CONTENTS)

    def set_contents(self, contents: str | None) -> None:
        self._annot.set_string(_CONTENTS, contents)

    # ---------- /T (author / title) ----------

    def get_title(self) -> str | None:
        return self._annot.get_string(_T)

    def set_title(self, title: str | None) -> None:
        self._annot.set_string(_T, title)

    # ---------- /Subtype ----------

    def get_subtype(self) -> str | None:
        v = self._annot.get_dictionary_object(_SUBTYPE)
        if isinstance(v, COSName):
            return v.name
        return None

    def set_subtype(self, subtype: str | None) -> None:
        if subtype is None:
            self._annot.remove_item(_SUBTYPE)
        else:
            self._annot.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))

    # ---------- /Rect (4-element float array) ----------

    def get_rectangle(self) -> tuple[float, float, float, float] | None:
        v = self._annot.get_dictionary_object(_RECT)
        if isinstance(v, COSArray) and len(v) == 4:
            return (
                _as_float(v[0]),
                _as_float(v[1]),
                _as_float(v[2]),
                _as_float(v[3]),
            )
        return None

    def set_rectangle(self, rect: tuple[float, float, float, float] | None) -> None:
        if rect is None:
            self._annot.remove_item(_RECT)
            return
        arr = COSArray()
        for v in rect:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_RECT, arr)

    # ---------- /C colour (3-element RGB float array) ----------

    def get_color(self) -> tuple[float, float, float] | None:
        v = self._annot.get_dictionary_object(_C)
        if isinstance(v, COSArray) and len(v) == 3:
            return (_as_float(v[0]), _as_float(v[1]), _as_float(v[2]))
        return None

    def set_color(self, color: tuple[float, float, float] | None) -> None:
        if color is None:
            self._annot.remove_item(_C)
            return
        arr = COSArray()
        for v in color:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_C, arr)

    # ---------- /F flags ----------

    def get_flags(self) -> int:
        return self._annot.get_int(_F, 0)

    def set_flags(self, flags: int) -> None:
        self._annot.set_int(_F, flags)

    # ---------- /Name (icon name etc.) ----------

    def get_name_attribute(self) -> str | None:
        v = self._annot.get_dictionary_object(_NAME)
        if isinstance(v, COSName):
            return v.name
        return None

    def set_name_attribute(self, name: str | None) -> None:
        if name is None:
            self._annot.remove_item(_NAME)
        else:
            self._annot.set_item(_NAME, COSName.get_pdf_name(name))

    # ---------- /M modified date (string) ----------

    def get_modified_date(self) -> str | None:
        return self._annot.get_string(_M)

    def set_modified_date(self, date: str | None) -> None:
        self._annot.set_string(_M, date)

    # ---------- factory ----------

    @classmethod
    def create(cls, annot: COSDictionary) -> "FDFAnnotation":
        """Dispatch to the concrete ``FDFAnnotation`` subtype based on
        ``/Subtype``. Mirrors ``FDFAnnotation.create(COSDictionary)`` upstream.

        Falls back to the bare ``FDFAnnotation`` base when the subtype is
        unknown or absent so callers always receive a usable wrapper.
        """
        sub = annot.get_dictionary_object(_SUBTYPE)
        if isinstance(sub, COSName):
            name = sub.name
        else:
            name = None

        # Lazy-import to avoid an import cycle: subtypes import this module.
        if name == "Text":
            from .fdf_annotation_text import FDFAnnotationText

            return FDFAnnotationText(annot)
        if name == "FreeText":
            from .fdf_annotation_free_text import FDFAnnotationFreeText

            return FDFAnnotationFreeText(annot)
        if name == "Square":
            from .fdf_annotation_square import FDFAnnotationSquare

            return FDFAnnotationSquare(annot)
        if name == "Circle":
            from .fdf_annotation_circle import FDFAnnotationCircle

            return FDFAnnotationCircle(annot)
        if name == "Line":
            from .fdf_annotation_line import FDFAnnotationLine

            return FDFAnnotationLine(annot)
        return cls(annot)


def _as_float(v: COSBase | Any) -> float:
    val = getattr(v, "value", None)
    if isinstance(val, (int, float)):
        return float(val)
    return 0.0
