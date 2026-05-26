"""Out-of-band leaf node of a Huffman prefix-code tree.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.OutOfBandNode``.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.node import Node
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream

# Java ``Long.MAX_VALUE`` — the sentinel returned for the out-of-band code.
LONG_MAX_VALUE = 0x7FFFFFFFFFFFFFFF


class OutOfBandNode(Node):
    """Represents an out-of-band node in a Huffman tree."""

    def __init__(self, c: object) -> None:
        # Upstream takes the Code but ignores it; the OOB code carries no range.
        pass

    def decode(self, iis: ImageInputStream) -> int:
        return LONG_MAX_VALUE
