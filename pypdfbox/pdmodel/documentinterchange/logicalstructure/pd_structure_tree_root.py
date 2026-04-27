from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode

from .pd_structure_class_map import PDStructureClassMap
from .pd_structure_element import PDStructureElement
from .pd_structure_node import PDStructureNode

_ID_TREE: COSName = COSName.get_pdf_name("IDTree")
_PARENT_TREE: COSName = COSName.get_pdf_name("ParentTree")
_PARENT_TREE_NEXT_KEY: COSName = COSName.get_pdf_name("ParentTreeNextKey")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_CLASS_MAP: COSName = COSName.get_pdf_name("ClassMap")

_STRUCT_TREE_ROOT_NAME: str = "StructTreeRoot"


class PDStructureTreeRoot(PDStructureNode):
    """
    Root of a PDF logical-structure tree (``/StructTreeRoot`` dictionary).
    Mirrors PDFBox ``PDStructureTreeRoot``.

    Lite surface: ``/K`` returns typed children where known, preserving raw
    COS fallback; ``/ParentTree`` returns a typed number-tree wrapper with raw
    COS values; ``/ClassMap`` returns a :class:`PDStructureClassMap` typed
    wrapper exposing ``PDAttributeObject``-typed entries.
    """

    def __init__(self, struct_tree_root: COSDictionary | None = None) -> None:
        super().__init__(
            struct_tree_root if struct_tree_root is not None else _STRUCT_TREE_ROOT_NAME
        )
        # Backwards-compat alias for callers / subclasses that referenced ``_root``.
        self._root: COSDictionary = self._dictionary

    # ---------- /K kids ----------
    #
    # PDStructureNode provides ``get_kids`` / ``set_kids`` / ``append_kid`` /
    # ``remove_kid``; we keep no override here.

    # ---------- /RoleMap ----------

    def get_role_map(self) -> dict[str, str]:
        """
        Returns a Python dict mapping non-standard structure-type names to
        standard structure types. Entries that are not ``/Name`` values
        are skipped (upstream returns the underlying mixed map; we narrow
        to string-to-string for the lite scaffold).
        """
        rm = self._dictionary.get_dictionary_object(_ROLE_MAP)
        out: dict[str, str] = {}
        if not isinstance(rm, COSDictionary):
            return out
        for key, value in rm.entry_set():
            if isinstance(value, COSName):
                out[key.get_name()] = value.get_name()
        return out

    def set_role_map(self, role_map: dict[str, str] | None) -> None:
        if role_map is None:
            self._dictionary.remove_item(_ROLE_MAP)
            return
        rm = COSDictionary()
        for key, value in role_map.items():
            rm.set_name(key, value)
        self._dictionary.set_item(_ROLE_MAP, rm)

    # ---------- /ClassMap ----------

    def get_class_map(self) -> PDStructureClassMap | None:
        """
        Returns the ``/ClassMap`` as a :class:`PDStructureClassMap` typed
        wrapper, or ``None`` when the entry is absent.

        Mirrors upstream ``PDStructureTreeRoot.getClassMap`` semantics; we
        return a typed wrapper instead of a raw ``Map<String,Object>``.
        """
        cm = self._dictionary.get_dictionary_object(_CLASS_MAP)
        if not isinstance(cm, COSDictionary):
            return None
        return PDStructureClassMap(cm)

    def set_class_map(
        self, class_map: PDStructureClassMap | dict[str, Any] | None
    ) -> None:
        """Write the ``/ClassMap`` entry.

        Accepts a :class:`PDStructureClassMap`, a raw ``dict`` whose values
        are :class:`PDAttributeObject` (or lists of them) or raw COS
        dictionaries / arrays, or ``None``/empty to remove the entry."""
        if class_map is None:
            self._dictionary.remove_item(_CLASS_MAP)
            return
        if isinstance(class_map, PDStructureClassMap):
            if class_map.is_empty():
                self._dictionary.remove_item(_CLASS_MAP)
                return
            self._dictionary.set_item(_CLASS_MAP, class_map.get_cos_object())
            return
        if not class_map:
            self._dictionary.remove_item(_CLASS_MAP)
            return
        cm = COSDictionary()
        for name, value in class_map.items():
            if isinstance(value, list):
                arr = COSArray()
                for entry in value:
                    arr.add(_to_cos(entry))
                cm.set_item(name, arr)
            else:
                cm.set_item(name, _to_cos(value))
        self._dictionary.set_item(_CLASS_MAP, cm)

    # ---------- /IDTree ----------

    def get_id_tree(self) -> PDNameTreeNode[PDStructureElement] | None:
        id_tree = self._dictionary.get_dictionary_object(_ID_TREE)
        if not isinstance(id_tree, COSDictionary):
            return None
        return PDStructureElementNameTreeNode(id_tree)

    def set_id_tree(self, id_tree: Any) -> None:
        if id_tree is None:
            self._dictionary.remove_item(_ID_TREE)
            return
        cos = id_tree.get_cos_object() if hasattr(id_tree, "get_cos_object") else id_tree
        self._dictionary.set_item(_ID_TREE, cos)

    # ---------- /ParentTree ----

    def get_parent_tree(self) -> PDStructureElementNumberTreeNode | None:
        parent_tree = self._dictionary.get_dictionary_object(_PARENT_TREE)
        if not isinstance(parent_tree, COSDictionary):
            return None
        return PDStructureElementNumberTreeNode(parent_tree)

    def set_parent_tree(self, parent_tree: Any) -> None:
        if parent_tree is None:
            self._dictionary.remove_item(_PARENT_TREE)
            return
        cos = (
            parent_tree.get_cos_object()
            if hasattr(parent_tree, "get_cos_object")
            else parent_tree
        )
        self._dictionary.set_item(_PARENT_TREE, cos)

    # ---------- /ParentTreeNextKey ----------

    def get_parent_tree_next_key(self) -> int:
        return self._dictionary.get_int(_PARENT_TREE_NEXT_KEY, 0)

    def set_parent_tree_next_key(self, key: int) -> None:
        self._dictionary.set_int(_PARENT_TREE_NEXT_KEY, key)

    # ---------- convenience lookups ----------

    def get_struct_element_for_id(self, id_string: str) -> PDStructureElement | None:
        """Look up a ``PDStructureElement`` by ``/ID`` via the ``/IDTree``.
        Returns ``None`` when the ``/IDTree`` is absent or the id is not found.
        Mirrors upstream ``PDStructureTreeRoot.getStructElementForID``."""
        if id_string is None:
            return None
        id_tree = self.get_id_tree()
        if id_tree is None:
            return None
        return id_tree.get_value(id_string)

    def get_struct_element_for_mcid(
        self, page: Any, mcid: int
    ) -> PDStructureElement | None:
        """Look up the ``PDStructureElement`` that owns the marked-content
        sequence with id ``mcid`` on ``page``. Resolves via
        ``/StructParents`` → ``/ParentTree`` → array indexed by mcid.
        Returns ``None`` when any link is missing.
        Mirrors upstream ``PDStructureTreeRoot.getStructElementForMCID``."""
        if page is None:
            return None
        struct_parents = page.get_struct_parents()
        if struct_parents < 0:
            return None
        parent_tree = self.get_parent_tree()
        if parent_tree is None:
            return None
        entry = parent_tree.get_value(struct_parents)
        if not isinstance(entry, COSArray):
            return None
        if mcid < 0 or mcid >= entry.size():
            return None
        target = entry.get_object(mcid)
        if not isinstance(target, COSDictionary):
            return None
        return PDStructureElement(target)


class PDStructureElementNameTreeNode(PDNameTreeNode[PDStructureElement]):
    """
    Concrete name-tree node used for ``/IDTree``. Mirrors upstream
    ``org.apache.pdfbox.pdmodel.PDStructureElementNameTreeNode`` (kept
    private to this module — the upstream class lives directly in
    ``pdmodel``; we colocate here until callers need a public symbol).
    """

    def convert_cos_to_value(self, base: COSBase) -> PDStructureElement:
        if not isinstance(base, COSDictionary):
            raise TypeError(
                f"IDTree value must be COSDictionary, got {type(base).__name__}"
            )
        return PDStructureElement(base)

    def convert_value_to_cos(self, value: PDStructureElement) -> COSBase:
        return value.get_cos_object()

    def create_child_node(self, dic: COSDictionary) -> PDStructureElementNameTreeNode:
        return PDStructureElementNameTreeNode(dic)


class PDStructureElementNumberTreeNode(PDNumberTreeNode[COSBase]):
    """
    Concrete number-tree node used for ``/ParentTree``. Values are exposed as
    raw COS entries because parent-tree leaves may be either a structure
    element dictionary or an array indexed by MCID.
    """

    def convert_cos_to_value(self, base: COSBase) -> COSBase:
        return base

    def convert_value_to_cos(self, value: COSBase) -> COSBase:
        return _to_cos(value)

    def create_child_node(self, dic: COSDictionary) -> PDStructureElementNumberTreeNode:
        return PDStructureElementNumberTreeNode(dic)


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return value.get_cos_object()
    return value


__all__ = [
    "PDStructureClassMap",
    "PDStructureElementNameTreeNode",
    "PDStructureElementNumberTreeNode",
    "PDStructureTreeRoot",
]
