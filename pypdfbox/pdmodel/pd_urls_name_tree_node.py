from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDURLSNameTreeNode(PDNameTreeNode[COSDictionary]):
    """
    Name tree of URL alias dictionaries (Web Capture). Mirrors PDFBox
    ``PDURLSNameTreeNode`` — the catalog ``/Names /URLS`` entry
    (PDF 32000-1 §7.7.4, Table 31; §14.10 Web Capture).

    Leaf values are URL alias dictionaries, exposed here as raw
    ``COSDictionary``.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> COSDictionary:
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Expected dictionary for /URLS name tree leaf, got "
                f"{type(base).__name__}"
            )
        return base

    def convert_value_to_cos(self, value: COSDictionary) -> COSBase:
        return value

    def create_child_node(self, dic: COSDictionary) -> PDURLSNameTreeNode:
        return PDURLSNameTreeNode(dic)


__all__ = ["PDURLSNameTreeNode"]
