from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode

from .pd_destination import PDDestination
from .pd_page_destination import PDPageDestination


class PDDestinationNameTreeNode(PDNameTreeNode[PDPageDestination]):
    """
    Name tree of explicit page destinations. Mirrors PDFBox
    ``PDDestinationNameTreeNode`` — concrete subclass of
    ``PDNameTreeNode<PDPageDestination>`` for the catalog's
    ``/Names /Dests`` entry.

    Leaf values are constructed via :meth:`PDDestination.create`; only
    ``PDPageDestination`` instances are valid leaves (named-destination
    indirection is not chained from inside another name tree).
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    # ---------- generic name-tree extension points ----------

    def convert_cos_to_value(self, base: COSBase) -> PDPageDestination:
        destination = PDDestination.create(base)
        if not isinstance(destination, PDPageDestination):
            raise OSError(
                f"Expected PDPageDestination in destination name tree leaf, got "
                f"{type(destination).__name__}"
            )
        return destination

    def convert_value_to_cos(self, value: PDPageDestination) -> COSBase:
        return value.get_cos_object()

    def create_child_node(self, dic: COSDictionary) -> PDDestinationNameTreeNode:
        return PDDestinationNameTreeNode(dic)

    # ---------- back-compat shims ----------

    def set_value(self, name: str, destination: PDPageDestination | None) -> None:
        """Legacy single-entry setter — routes through the generic
        ``get_names``/``set_names`` pair so the underlying ``/Names`` array
        stays consistent with name-tree semantics."""
        current = self.get_names() or {}
        if destination is None:
            current.pop(name, None)
        else:
            current[name] = destination
        self.set_names(current if current else None)

    def names(self) -> list[str]:
        """Legacy alias returning the sorted leaf-name list (back-compat
        with the previous flat-/Names wrapper)."""
        names = self.get_names()
        return sorted(names) if names else []


__all__ = ["PDDestinationNameTreeNode"]
