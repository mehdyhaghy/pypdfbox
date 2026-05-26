"""Value (leaf) node of a Huffman prefix-code tree.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.ValueNode``.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.node import Node
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


class ValueNode(Node):
    """Represents a value node in a Huffman tree. It is a leaf of a tree."""

    def __init__(self, c: object) -> None:
        self.range_len = c.range_length
        self.range_low = c.range_low
        self.is_lower_range = c.is_lower_range

    def decode(self, iis: ImageInputStream) -> int:
        if self.is_lower_range:
            # B.4 4)
            return self.range_low - iis.read_bits(self.range_len)
        else:
            # B.4 5)
            return self.range_low + iis.read_bits(self.range_len)


def bit_pattern(v: int, length: int) -> str:
    """Render the low ``length`` bits of ``v`` as a big-endian bit string."""
    result = []
    for i in range(1, length + 1):
        result.append("1" if (v >> (length - i)) & 1 else "0")
    return "".join(result)
