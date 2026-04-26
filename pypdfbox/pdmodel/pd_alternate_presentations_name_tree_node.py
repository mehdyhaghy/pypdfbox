from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDAlternatePresentationsNameTreeNode(PDNameTreeNode[COSDictionary]):
    """
    Name tree of alternate-presentation (slideshow) dictionaries.
    Mirrors PDFBox ``PDAlternatePresentationsNameTreeNode`` — the
    catalog ``/Names /AlternatePresentations`` entry (PDF 32000-1
    §7.7.4, Table 31; §13.5 Alternate presentations).

    Leaf values are slideshow dictionaries, exposed here as raw
    ``COSDictionary``.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> COSDictionary:
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Expected dictionary for /AlternatePresentations name tree "
                f"leaf, got {type(base).__name__}"
            )
        return base

    def convert_value_to_cos(self, value: COSDictionary) -> COSBase:
        return value

    def create_child_node(
        self, dic: COSDictionary
    ) -> PDAlternatePresentationsNameTreeNode:
        return PDAlternatePresentationsNameTreeNode(dic)


__all__ = ["PDAlternatePresentationsNameTreeNode"]
