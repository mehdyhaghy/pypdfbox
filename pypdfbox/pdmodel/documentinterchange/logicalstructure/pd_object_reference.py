from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PG: COSName = COSName.get_pdf_name("Pg")
_OBJ: COSName = COSName.get_pdf_name("Obj")


class PDObjectReference:
    """
    An object reference (``/Type /OBJR`` dictionary). Mirrors PDFBox
    ``PDObjectReference``.

    Lite surface: typed ``PDPage`` (``/Pg``), typed annotations / XObjects
    behind ``/Obj``, and ``get_referenced_object`` are deferred. ``/Obj``
    is exposed as a raw ``COSBase`` (the indirect reference target).
    """

    TYPE: str = "OBJR"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dictionary: COSDictionary = COSDictionary()
            self._dictionary.set_name(_TYPE, self.TYPE)
        else:
            self._dictionary = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /Pg page (raw COSDictionary; typed PDPage deferred) ----

    def get_pg(self) -> COSDictionary | None:
        pg = self._dictionary.get_dictionary_object(_PG)
        return pg if isinstance(pg, COSDictionary) else None

    def set_pg(self, page: COSDictionary | None) -> None:
        if page is None:
            self._dictionary.remove_item(_PG)
            return
        cos = page.get_cos_object() if hasattr(page, "get_cos_object") else page
        self._dictionary.set_item(_PG, cos)

    # ---------- /Obj referenced object (raw COSBase) ----

    def get_obj(self) -> COSBase | None:
        return self._dictionary.get_dictionary_object(_OBJ)

    def set_obj(self, obj: COSBase | None) -> None:
        if obj is None:
            self._dictionary.remove_item(_OBJ)
            return
        cos = obj.get_cos_object() if hasattr(obj, "get_cos_object") else obj
        self._dictionary.set_item(_OBJ, cos)


__all__ = ["PDObjectReference"]
