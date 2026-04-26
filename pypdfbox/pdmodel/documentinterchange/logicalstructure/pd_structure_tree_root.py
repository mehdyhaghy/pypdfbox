from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode

from .pd_structure_element import PDStructureElement

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_STRUCT_TREE_ROOT: COSName = COSName.STRUCT_TREE_ROOT  # type: ignore[attr-defined]
_K: COSName = COSName.get_pdf_name("K")
_ID_TREE: COSName = COSName.get_pdf_name("IDTree")
_PARENT_TREE: COSName = COSName.get_pdf_name("ParentTree")
_PARENT_TREE_NEXT_KEY: COSName = COSName.get_pdf_name("ParentTreeNextKey")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_CLASS_MAP: COSName = COSName.get_pdf_name("ClassMap")


class PDStructureTreeRoot:
    """
    Root of a PDF logical-structure tree (``/StructTreeRoot`` dictionary).
    Mirrors PDFBox ``PDStructureTreeRoot``.

    Lite surface: ``/K`` returns raw COS children (no typed
    PDStructureElement walk yet); ``/ParentTree`` returns the raw
    ``COSDictionary`` (no typed ``PDNumberTreeNode<PDParentTreeValue>``
    yet); ``/ClassMap`` returns the raw Python ``dict`` of COSBase entries
    (no ``PDAttributeObject`` typed wrap yet).
    """

    def __init__(self, struct_tree_root: COSDictionary | None = None) -> None:
        self._root: COSDictionary = (
            struct_tree_root if struct_tree_root is not None else COSDictionary()
        )
        if self._root.get_dictionary_object(_TYPE) is None:
            self._root.set_item(_TYPE, _STRUCT_TREE_ROOT)

    def get_cos_object(self) -> COSDictionary:
        return self._root

    # ---------- /K kids ----------

    def get_kids(self) -> list[COSBase] | None:
        """
        Returns the raw ``/K`` children. ``/K`` may be a single structure
        element dictionary or a COSArray mixing dictionaries, integer
        MCIDs, and marked-content references. Typed dispatch is deferred —
        callers receive a flat list of raw COSBase entries (or ``None`` if
        ``/K`` is absent).
        """
        k = self._root.get_dictionary_object(_K)
        if k is None:
            return None
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
            self._root.remove_item(_K)
            return
        arr = COSArray()
        for kid in kids:
            arr.add(_to_cos(kid))
        self._root.set_item(_K, arr)

    # ---------- /RoleMap ----------

    def get_role_map(self) -> dict[str, str]:
        """
        Returns a Python dict mapping non-standard structure-type names to
        standard structure types. Entries that are not ``/Name`` values
        are skipped (upstream returns the underlying mixed map; we narrow
        to string-to-string for the lite scaffold).
        """
        rm = self._root.get_dictionary_object(_ROLE_MAP)
        out: dict[str, str] = {}
        if not isinstance(rm, COSDictionary):
            return out
        for key, value in rm.entry_set():
            if isinstance(value, COSName):
                out[key.get_name()] = value.get_name()
        return out

    def set_role_map(self, role_map: dict[str, str] | None) -> None:
        if role_map is None:
            self._root.remove_item(_ROLE_MAP)
            return
        rm = COSDictionary()
        for key, value in role_map.items():
            rm.set_name(key, value)
        self._root.set_item(_ROLE_MAP, rm)

    # ---------- /ClassMap ----------

    def get_class_map(self) -> dict[str, Any]:
        """
        Returns the raw class map. Values are kept as raw COSBase entries
        (single ``COSDictionary`` or list of COSBase from a ``COSArray``)
        — typed ``PDAttributeObject`` wrapping is deferred.
        """
        cm = self._root.get_dictionary_object(_CLASS_MAP)
        out: dict[str, Any] = {}
        if not isinstance(cm, COSDictionary):
            return out
        for key, base in cm.entry_set():
            if isinstance(base, COSArray):
                items: list[COSBase] = []
                for i in range(base.size()):
                    item = base.get_object(i)
                    if item is not None:
                        items.append(item)
                out[key.get_name()] = items
            else:
                out[key.get_name()] = base
        return out

    def set_class_map(self, class_map: dict[str, Any] | None) -> None:
        if not class_map:
            self._root.remove_item(_CLASS_MAP)
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
        self._root.set_item(_CLASS_MAP, cm)

    # ---------- /IDTree ----------

    def get_id_tree(self) -> PDNameTreeNode[PDStructureElement] | None:
        id_tree = self._root.get_dictionary_object(_ID_TREE)
        if not isinstance(id_tree, COSDictionary):
            return None
        return PDStructureElementNameTreeNode(id_tree)

    def set_id_tree(self, id_tree: Any) -> None:
        if id_tree is None:
            self._root.remove_item(_ID_TREE)
            return
        cos = id_tree.get_cos_object() if hasattr(id_tree, "get_cos_object") else id_tree
        self._root.set_item(_ID_TREE, cos)

    # ---------- /ParentTree (raw — typed PDNumberTreeNode deferred) ----

    def get_parent_tree(self) -> COSBase | None:
        return self._root.get_dictionary_object(_PARENT_TREE)

    def set_parent_tree(self, parent_tree: Any) -> None:
        if parent_tree is None:
            self._root.remove_item(_PARENT_TREE)
            return
        cos = (
            parent_tree.get_cos_object()
            if hasattr(parent_tree, "get_cos_object")
            else parent_tree
        )
        self._root.set_item(_PARENT_TREE, cos)

    # ---------- /ParentTreeNextKey ----------

    def get_parent_tree_next_key(self) -> int:
        return self._root.get_int(_PARENT_TREE_NEXT_KEY, 0)

    def set_parent_tree_next_key(self, key: int) -> None:
        self._root.set_int(_PARENT_TREE_NEXT_KEY, key)


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


def _to_cos(value: Any) -> COSBase:
    if hasattr(value, "get_cos_object"):
        return value.get_cos_object()
    return value


__all__ = ["PDStructureElementNameTreeNode", "PDStructureTreeRoot"]
