from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDTemplatesNameTreeNode(PDNameTreeNode[COSDictionary]):
    """
    Name tree of named page templates. Mirrors PDFBox
    ``PDTemplatesNameTreeNode`` — the catalog ``/Names /Templates``
    entry (PDF 32000-1 §7.7.4, Table 31). Each leaf is a visible page
    template used for forms-style spawning.

    Leaf values are exposed as the raw ``COSDictionary``; spawning logic
    is not wrapped here.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> COSDictionary:
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Expected dictionary for /Templates name tree leaf, got "
                f"{type(base).__name__}"
            )
        return base

    def convert_value_to_cos(self, value: COSDictionary) -> COSBase:
        return value

    def create_child_node(self, dic: COSDictionary) -> PDTemplatesNameTreeNode:
        return PDTemplatesNameTreeNode(dic)


__all__ = ["PDTemplatesNameTreeNode"]
