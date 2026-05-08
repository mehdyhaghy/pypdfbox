from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSNull
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode

from .pd_destination import PDDestination
from .pd_page_destination import PDPageDestination


class PDDestinationNameTreeNode(PDNameTreeNode[PDPageDestination | None]):
    """
    Name tree of explicit page destinations. Mirrors PDFBox
    ``PDDestinationNameTreeNode`` — concrete subclass of
    ``PDNameTreeNode<PDPageDestination | None>`` for the catalog's
    ``/Names /Dests`` entry.

    Leaf values are constructed via :meth:`PDDestination.create`; valid
    leaves resolve to ``PDPageDestination`` instances, while malformed
    entries resolve to ``None`` for tolerant name-tree lookup.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    # ---------- generic name-tree extension points ----------

    def convert_cos_to_value(self, base: COSBase) -> PDPageDestination | None:
        # Mirrors upstream's ``convertCOSToPD``: when the leaf value is a
        # COSDictionary, the actual destination lives under the ``/D`` key
        # (named-destination indirection inlined into the leaf entry).
        from pypdfbox.cos import COSDictionary as _COSDictionary
        from pypdfbox.cos import COSName as _COSName

        destination_base: COSBase | None = base
        if isinstance(base, _COSDictionary):
            destination_base = base.get_dictionary_object(_COSName.get_pdf_name("D"))
        try:
            destination = PDDestination.create(destination_base)
        except OSError:
            # PDFBOX-5975: malformed tree entries must surface as ``None``, not
            # abort name-tree lookup.
            return None
        if isinstance(destination, PDPageDestination):
            return destination
        # PDFBOX-5975: an invalid tree entry must surface as ``None``, not an
        # exception — mirrors upstream behaviour added for the same JIRA.
        return None

    def convert_value_to_cos(self, value: PDPageDestination | None) -> COSBase:
        if value is None:
            return COSNull.NULL
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
