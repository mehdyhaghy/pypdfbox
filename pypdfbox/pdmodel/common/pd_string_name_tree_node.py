from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSString

from .pd_name_tree_node import PDNameTreeNode


class PDStringNameTreeNode(PDNameTreeNode[str]):
    """
    Concrete ``PDNameTreeNode`` whose leaf values are plain text strings.

    Useful for the catalog name dictionaries that map names to text
    payloads (e.g. legacy ``/JavaScript`` script bodies stored as strings,
    or any ad hoc string-keyed name tree). Subclasses with structured
    values should derive directly from ``PDNameTreeNode``.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> str:
        if not isinstance(base, COSString):
            raise OSError(
                f"Expected COSString in name tree leaf, got {type(base).__name__}"
            )
        return base.get_string()

    def convert_value_to_cos(self, value: str) -> COSBase:
        return COSString(value)

    def create_child_node(self, dic: COSDictionary) -> PDStringNameTreeNode:
        return PDStringNameTreeNode(dic)


__all__ = ["PDStringNameTreeNode"]
