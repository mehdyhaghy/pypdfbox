from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDPagesNameTreeNode(PDNameTreeNode[COSDictionary]):
    """
    Name tree of named page references. Mirrors PDFBox
    ``PDPagesNameTreeNode`` — the catalog ``/Names /Pages`` entry, used
    to give individual page objects symbolic names (PDF 32000-1 §7.7.4,
    Table 31).

    Leaf values are exposed as the raw ``COSDictionary`` page reference;
    no higher-level page wrapper is constructed here to keep this module
    free of a back-reference to the page-tree implementation.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> COSDictionary:
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Expected dictionary for /Pages name tree leaf, got "
                f"{type(base).__name__}"
            )
        return base

    def convert_value_to_cos(self, value: COSDictionary) -> COSBase:
        return value

    def create_child_node(self, dic: COSDictionary) -> PDPagesNameTreeNode:
        return PDPagesNameTreeNode(dic)


__all__ = ["PDPagesNameTreeNode"]
