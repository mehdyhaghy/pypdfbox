from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_STRUCT_ELEM: COSName = COSName.get_pdf_name("StructElem")
_S: COSName = COSName.get_pdf_name("S")
_P: COSName = COSName.get_pdf_name("P")
_K: COSName = COSName.get_pdf_name("K")
_ID: COSName = COSName.get_pdf_name("ID")
_R: COSName = COSName.get_pdf_name("R")
_T: COSName = COSName.T  # type: ignore[attr-defined]
_LANG: COSName = COSName.get_pdf_name("Lang")
_ALT: COSName = COSName.get_pdf_name("Alt")
_E: COSName = COSName.get_pdf_name("E")
_ACTUAL_TEXT: COSName = COSName.get_pdf_name("ActualText")


class PDStructureElement:
    """
    A structure element (``/Type /StructElem`` dictionary). Mirrors PDFBox
    ``PDStructureElement``.

    This is the *lite* surface: typed attribute objects, class-name
    revisions, page (``/Pg``), the typed-parent chain, and the typed kid
    dispatch (marked-content reference / object reference / structure
    element walk) are deferred until later clusters land.
    """

    TYPE: str = "StructElem"

    def __init__(
        self,
        structure_element: COSDictionary | None = None,
        structure_type: str | None = None,
    ) -> None:
        self._element: COSDictionary = (
            structure_element if structure_element is not None else COSDictionary()
        )
        if self._element.get_dictionary_object(_TYPE) is None:
            self._element.set_item(_TYPE, _STRUCT_ELEM)
        if structure_type is not None:
            self.set_structure_type(structure_type)

    def get_cos_object(self) -> COSDictionary:
        return self._element

    # ---------- /S structure type ----------

    def get_structure_type(self) -> str | None:
        return self._element.get_name(_S)

    def set_structure_type(self, structure_type: str) -> None:
        self._element.set_name(_S, structure_type)

    # ---------- /P parent (raw COSBase; typed PDStructureNode deferred) ----

    def get_parent(self) -> COSBase | None:
        return self._element.get_dictionary_object(_P)

    def set_parent(self, parent: Any) -> None:
        if parent is None:
            self._element.remove_item(_P)
            return
        cos = parent.get_cos_object() if hasattr(parent, "get_cos_object") else parent
        self._element.set_item(_P, cos)

    # ---------- /ID ----------

    def get_id(self) -> str | None:
        return self._element.get_string(_ID)

    def set_id(self, id_: str | None) -> None:
        self._element.set_string(_ID, id_)

    # ---------- /R revision number ----------

    def get_revision_number(self) -> int:
        return self._element.get_int(_R, 0)

    def set_revision_number(self, revision_number: int) -> None:
        if revision_number < 0:
            raise ValueError("The revision number shall be > -1")
        self._element.set_int(_R, revision_number)

    # ---------- /T title ----------

    def get_title(self) -> str | None:
        return self._element.get_string(_T)

    def set_title(self, title: str | None) -> None:
        self._element.set_string(_T, title)

    # ---------- /Lang ----------

    def get_language(self) -> str | None:
        return self._element.get_string(_LANG)

    def set_language(self, language: str | None) -> None:
        self._element.set_string(_LANG, language)

    # ---------- /Alt ----------

    def get_alternate_description(self) -> str | None:
        return self._element.get_string(_ALT)

    def set_alternate_description(self, alternate_description: str | None) -> None:
        self._element.set_string(_ALT, alternate_description)

    # ---------- /E expanded form ----------

    def get_expanded_form(self) -> str | None:
        return self._element.get_string(_E)

    def set_expanded_form(self, expanded_form: str | None) -> None:
        self._element.set_string(_E, expanded_form)

    # ---------- /ActualText ----------

    def get_actual_text(self) -> str | None:
        return self._element.get_string(_ACTUAL_TEXT)

    def set_actual_text(self, actual_text: str | None) -> None:
        self._element.set_string(_ACTUAL_TEXT, actual_text)

    # ---------- /K kids (raw COSBase mixed children) ----------

    def get_kids(self) -> list[COSBase]:
        """
        Returns the raw ``/K`` children as a flat list of COSBase objects.

        Per PDF spec ``/K`` may be a single dict, a single integer (MCID),
        or a COSArray mixing structure-element dicts, marked-content
        references, object references, and integer MCIDs. Typed dispatch
        (PDStructureElement / PDMarkedContentReference / PDObjectReference)
        is deferred — callers receive raw COS entries.
        """
        k = self._element.get_dictionary_object(_K)
        if k is None:
            return []
        if isinstance(k, COSArray):
            out: list[COSBase] = []
            for i in range(k.size()):
                base = k.get_object(i)
                if base is not None:
                    out.append(base)
            return out
        return [k]

    def set_kids(self, kids: list[Any] | None) -> None:
        if not kids:
            self._element.remove_item(_K)
            return
        arr = COSArray()
        for kid in kids:
            arr.add(_to_cos(kid))
        self._element.set_item(_K, arr)

    def append_kid(self, kid: Any) -> None:
        cos_kid = _to_cos(kid)
        existing = self._element.get_dictionary_object(_K)
        if existing is None:
            self._element.set_item(_K, cos_kid)
            return
        if isinstance(existing, COSArray):
            existing.add(cos_kid)
            return
        arr = COSArray()
        arr.add(existing)
        arr.add(cos_kid)
        self._element.set_item(_K, arr)


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return value.get_cos_object()
    return value


__all__ = ["PDStructureElement"]
