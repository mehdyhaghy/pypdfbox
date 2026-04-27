from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_K: COSName = COSName.get_pdf_name("K")
_STRUCT_TREE_ROOT_NAME: str = "StructTreeRoot"
_STRUCT_ELEM_NAME: str = "StructElem"


class PDStructureNode:
    """
    Base node in the logical-structure tree. Mirrors PDFBox
    ``PDStructureNode`` (the abstract parent of ``PDStructureTreeRoot`` and
    ``PDStructureElement``).

    Lite surface: typed kid dispatch (PDStructureElement /
    PDMarkedContentReference / PDObjectReference / int MCID), the typed
    parent chain, and ``insertBefore`` overloads are deferred. Unknown ``/K``
    entries are preserved as raw COS objects.
    """

    def __init__(
        self,
        structure_type_for_create: str | COSDictionary | None = None,
    ) -> None:
        if isinstance(structure_type_for_create, COSDictionary):
            self._dictionary: COSDictionary = structure_type_for_create
        elif isinstance(structure_type_for_create, str):
            self._dictionary = COSDictionary()
            self._dictionary.set_name(_TYPE, structure_type_for_create)
        else:
            self._dictionary = COSDictionary()

    @staticmethod
    def create(node: COSDictionary) -> PDStructureNode:
        """
        Dispatch a ``COSDictionary`` to the matching typed wrapper:
        ``StructTreeRoot`` → ``PDStructureTreeRoot``;
        ``StructElem`` (or no ``/Type``) → ``PDStructureElement``.
        """
        if not isinstance(node, COSDictionary):
            raise TypeError(
                f"PDStructureNode.create expects COSDictionary, got {type(node).__name__}"
            )
        type_name = node.get_name(_TYPE)
        if type_name == _STRUCT_TREE_ROOT_NAME:
            from .pd_structure_tree_root import PDStructureTreeRoot

            return PDStructureTreeRoot(node)
        if type_name is None or type_name == _STRUCT_ELEM_NAME:
            from .pd_structure_element import PDStructureElement

            return PDStructureElement(node)
        raise ValueError(
            "Dictionary must not include a Type entry with a value that is "
            "neither StructTreeRoot nor StructElem."
        )

    @staticmethod
    def wrap_kid(kid: Any) -> Any:
        """Dispatch a /K kid entry to a typed wrapper based on /Type, or
        return the raw int / COSBase. Ints are MCIDs (marked content ids)."""
        from pypdfbox.cos import COSDictionary, COSInteger

        from .pd_marked_content_reference import PDMarkedContentReference
        from .pd_object_reference import PDObjectReference

        if isinstance(kid, COSInteger):
            return kid.value
        if isinstance(kid, COSDictionary):
            type_name = kid.get_name(_TYPE)
            if type_name == "MCR":
                return PDMarkedContentReference(kid)
            if type_name == "OBJR":
                return PDObjectReference(kid)
            if type_name == "StructElem":
                from .pd_structure_element import PDStructureElement

                return PDStructureElement(kid)
        return kid

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_type(self) -> str | None:
        return self._dictionary.get_name(_TYPE)

    # ---------- /K kids ----------

    def get_kids(self) -> list[Any]:
        """
        Returns the typed ``/K`` children. ``/K`` may be a single structure
        element dictionary, a single integer MCID, or a COSArray mixing
        dictionaries, integer MCIDs, and marked-content references. Known
        structure-tree dictionaries are wrapped; unknown entries are returned
        unchanged as raw COS fallback.
        """
        k = self._dictionary.get_dictionary_object(_K)
        if k is None:
            return []
        if isinstance(k, COSArray):
            out: list[Any] = []
            for i in range(k.size()):
                base = k.get_object(i)
                if base is not None:
                    out.append(self.wrap_kid(base))
            return out
        return [self.wrap_kid(k)]

    def set_kids(self, kids: list[Any] | None) -> None:
        if not kids:
            self._dictionary.remove_item(_K)
            return
        arr = COSArray()
        for kid in kids:
            arr.add(_to_cos(kid))
        self._dictionary.set_item(_K, arr)

    def append_kid(self, kid: Any) -> None:
        if kid is None:
            return
        cos_kid = _to_cos(kid)
        existing = self._dictionary.get_dictionary_object(_K)
        if existing is None:
            self._dictionary.set_item(_K, cos_kid)
            return
        if isinstance(existing, COSArray):
            existing.add(cos_kid)
            return
        arr = COSArray()
        arr.add(existing)
        arr.add(cos_kid)
        self._dictionary.set_item(_K, arr)

    def remove_kid(self, kid: Any) -> bool:
        if kid is None:
            return False
        cos_kid = _to_cos(kid)
        existing = self._dictionary.get_dictionary_object(_K)
        if existing is None:
            return False
        if isinstance(existing, COSArray):
            removed = _remove_array_kid(existing, cos_kid)
            if existing.size() == 1:
                only = existing.get_object(0)
                if only is not None:
                    self._dictionary.set_item(_K, only)
            return removed
        if _same_kid(existing, cos_kid):
            self._dictionary.remove_item(_K)
            return True
        return False


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return value.get_cos_object()
    if isinstance(value, int) and not isinstance(value, bool):
        return COSInteger.get(value)
    return value


def _remove_array_kid(array: COSArray, cos_kid: COSBase) -> bool:
    if array.remove_object(cos_kid):
        return True
    for i in range(array.size()):
        if _same_kid(array.get_object(i), cos_kid):
            array.remove_at(i)
            return True
    return False


def _same_kid(left: Any, right: Any) -> bool:
    if left is right:
        return True
    if isinstance(left, COSInteger) and isinstance(right, COSInteger):
        return left.value == right.value
    if isinstance(left, COSInteger) and isinstance(right, int) and not isinstance(right, bool):
        return left.value == right
    if isinstance(left, int) and not isinstance(left, bool) and isinstance(right, COSInteger):
        return left == right.value
    return left == right


__all__ = ["PDStructureNode"]
