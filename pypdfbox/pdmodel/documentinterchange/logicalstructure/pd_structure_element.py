from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_structure_node import PDStructureNode

_S: COSName = COSName.get_pdf_name("S")
_P: COSName = COSName.get_pdf_name("P")
_ID: COSName = COSName.get_pdf_name("ID")
_R: COSName = COSName.get_pdf_name("R")
_T: COSName = COSName.T  # type: ignore[attr-defined]
_LANG: COSName = COSName.get_pdf_name("Lang")
_ALT: COSName = COSName.get_pdf_name("Alt")
_E: COSName = COSName.get_pdf_name("E")
_ACTUAL_TEXT: COSName = COSName.get_pdf_name("ActualText")
_A: COSName = COSName.get_pdf_name("A")
_C: COSName = COSName.get_pdf_name("C")

_STRUCT_ELEM_NAME: str = "StructElem"


class PDStructureElement(PDStructureNode):
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
        super().__init__(structure_element if structure_element is not None else _STRUCT_ELEM_NAME)
        # Backwards-compat alias for callers / subclasses that referenced ``_element``.
        self._element: COSDictionary = self._dictionary
        if structure_type is not None:
            self.set_structure_type(structure_type)

    # ---------- /S structure type ----------

    def get_structure_type(self) -> str | None:
        return self._dictionary.get_name(_S)

    def set_structure_type(self, structure_type: str) -> None:
        self._dictionary.set_name(_S, structure_type)

    # ---------- /P parent (raw COSBase; typed PDStructureNode deferred) ----

    def get_parent(self) -> COSBase | None:
        return self._dictionary.get_dictionary_object(_P)

    def set_parent(self, parent: Any) -> None:
        if parent is None:
            self._dictionary.remove_item(_P)
            return
        cos = parent.get_cos_object() if hasattr(parent, "get_cos_object") else parent
        self._dictionary.set_item(_P, cos)

    # ---------- /ID ----------

    def get_id(self) -> str | None:
        return self._dictionary.get_string(_ID)

    def set_id(self, id_: str | None) -> None:
        self._dictionary.set_string(_ID, id_)

    # ---------- /R revision number ----------

    def get_revision_number(self) -> int:
        return self._dictionary.get_int(_R, 0)

    def set_revision_number(self, revision_number: int) -> None:
        if revision_number < 0:
            raise ValueError("The revision number shall be > -1")
        self._dictionary.set_int(_R, revision_number)

    # ---------- /T title ----------

    def get_title(self) -> str | None:
        return self._dictionary.get_string(_T)

    def set_title(self, title: str | None) -> None:
        self._dictionary.set_string(_T, title)

    # ---------- /Lang ----------

    def get_language(self) -> str | None:
        return self._dictionary.get_string(_LANG)

    def set_language(self, language: str | None) -> None:
        self._dictionary.set_string(_LANG, language)

    # ---------- /Alt ----------

    def get_alternate_description(self) -> str | None:
        return self._dictionary.get_string(_ALT)

    def set_alternate_description(self, alternate_description: str | None) -> None:
        self._dictionary.set_string(_ALT, alternate_description)

    # ---------- /E expanded form ----------

    def get_expanded_form(self) -> str | None:
        return self._dictionary.get_string(_E)

    def set_expanded_form(self, expanded_form: str | None) -> None:
        self._dictionary.set_string(_E, expanded_form)

    # ---------- /ActualText ----------

    def get_actual_text(self) -> str | None:
        return self._dictionary.get_string(_ACTUAL_TEXT)

    def set_actual_text(self, actual_text: str | None) -> None:
        self._dictionary.set_string(_ACTUAL_TEXT, actual_text)

    # ---------- /K kids ----------
    #
    # ``get_kids`` / ``set_kids`` / ``append_kid`` / ``remove_kid`` come from
    # PDStructureNode. Both the lite element surface and the base node treat
    # ``/K`` as a flat list of raw COSBase entries (single dict / single int
    # MCID / mixed COSArray) and use identical promotion semantics.

    # ---------- /A attributes ----------

    def get_attributes(self) -> "Revisions[PDAttributeObject]":
        from .pd_attribute_object import PDAttributeObject
        from .revisions import Revisions

        a = self._dictionary.get_dictionary_object(_A)
        if isinstance(a, COSArray):
            return Revisions(a)
        revs: Revisions[PDAttributeObject] = Revisions()
        if isinstance(a, COSDictionary):
            revs.add_object(PDAttributeObject(a), self.get_revision_number())
        return revs

    def set_attributes(self, attributes: "Revisions[PDAttributeObject] | None") -> None:
        if attributes is None:
            self._dictionary.remove_item(_A)
            return
        self._dictionary.set_item(_A, attributes.to_cos_array())

    # ---------- /C class names ----------

    def get_class_names(self) -> "Revisions[COSName]":
        from .revisions import Revisions

        c = self._dictionary.get_dictionary_object(_C)
        if isinstance(c, COSArray):
            return Revisions(c)
        revs: Revisions[COSName] = Revisions()
        if isinstance(c, COSName):
            revs.add_object(c, self.get_revision_number())
        return revs

    def set_class_names(self, class_names: "Revisions[COSName] | None") -> None:
        if class_names is None:
            self._dictionary.remove_item(_C)
            return
        self._dictionary.set_item(_C, class_names.to_cos_array())


__all__ = ["PDStructureElement"]
