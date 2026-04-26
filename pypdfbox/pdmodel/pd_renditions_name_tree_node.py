from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDRenditionsNameTreeNode(PDNameTreeNode[COSDictionary]):
    """
    Name tree of rendition dictionaries. Mirrors PDFBox
    ``PDRenditionsNameTreeNode`` — the catalog ``/Names /Renditions``
    entry (PDF 32000-1 §7.7.4, Table 31; §13.2 Multimedia).

    Leaf values are rendition dictionaries, exposed here as raw
    ``COSDictionary``; rendition-type wrappers are not yet ported.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> COSDictionary:
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Expected dictionary for /Renditions name tree leaf, got "
                f"{type(base).__name__}"
            )
        return base

    def convert_value_to_cos(self, value: COSDictionary) -> COSBase:
        return value

    def create_child_node(self, dic: COSDictionary) -> PDRenditionsNameTreeNode:
        return PDRenditionsNameTreeNode(dic)


__all__ = ["PDRenditionsNameTreeNode"]
