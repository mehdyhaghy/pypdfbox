"""CCITT fax decoder Huffman tree node.

Mirrors the private static inner class
``CCITTFaxDecoderStream.Node`` in upstream PDFBox. Promoted to a
module-level class because Python doesn't have Java's nested-class
visibility model; users should treat this as an implementation detail of
:mod:`pypdfbox.filter.ccitt_fax_decoder_stream`.
"""

from __future__ import annotations


class Node:
    """One node in the CCITT Huffman decoding tree.

    A node is either a leaf (``is_leaf=True``) carrying a run-length
    ``value`` (> 63 indicates a non-terminating make-up code), or an
    interior node with ``left`` / ``right`` children. The ``can_be_fill``
    flag marks the all-zero path used by fill bits before an EOL.
    """

    __slots__ = ("left", "right", "value", "can_be_fill", "is_leaf")

    def __init__(self) -> None:
        self.left: Node | None = None
        self.right: Node | None = None
        self.value: int = 0  # > 63 → non-terminating make-up code
        self.can_be_fill: bool = False
        self.is_leaf: bool = False

    def set(self, next_bit: bool, node: Node) -> None:
        """Attach ``node`` as the child reached by reading ``next_bit``."""
        if not next_bit:
            self.left = node
        else:
            self.right = node

    def walk(self, next_bit: bool) -> Node | None:
        """Return the child reached by reading ``next_bit``, or ``None``
        if the branch is missing (caller should treat as a decode error).
        """
        return self.right if next_bit else self.left

    def to_string(self) -> str:
        """Mirror upstream ``CCITTFaxDecoderStream.Node.toString``."""
        return f"[leaf={self.is_leaf}, value={self.value}, canBeFill={self.can_be_fill}]"

    def __repr__(self) -> str:
        return self.to_string()
