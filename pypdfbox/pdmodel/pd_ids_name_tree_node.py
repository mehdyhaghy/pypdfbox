from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSString
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode


class PDIDSNameTreeNode(PDNameTreeNode[bytes]):
    """
    Name tree of digital identifiers (Web Capture). Mirrors PDFBox
    ``PDIDSNameTreeNode`` — the catalog ``/Names /IDS`` entry
    (PDF 32000-1 §7.7.4, Table 31; §14.10 Web Capture).

    Leaf values are PDF strings (raw bytes), so this subclass exposes
    them as Python ``bytes`` and packs them back as ``COSString`` on
    write.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> bytes:
        if not isinstance(base, COSString):
            raise OSError(
                f"Expected string for /IDS name tree leaf, got "
                f"{type(base).__name__}"
            )
        return base.get_bytes()

    def convert_value_to_cos(self, value: bytes) -> COSBase:
        return COSString(value)

    def create_child_node(self, dic: COSDictionary) -> PDIDSNameTreeNode:
        return PDIDSNameTreeNode(dic)


__all__ = ["PDIDSNameTreeNode"]
