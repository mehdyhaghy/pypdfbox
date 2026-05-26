"""Internal (branch) node of a Huffman prefix-code tree.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.InternalNode``.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.node import Node
from pypdfbox.jbig2.decoder.huffman.out_of_band_node import OutOfBandNode
from pypdfbox.jbig2.decoder.huffman.value_node import ValueNode
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


class InternalNode(Node):
    """An internal node of a Huffman tree. It contains two child nodes."""

    def __init__(self, depth: int = 0) -> None:
        self.depth = depth
        self.zero: Node | None = None
        self.one: Node | None = None

    def append(self, c: object) -> None:
        # ignore unused codes
        if c.prefix_length == 0:
            return

        shift = c.prefix_length - 1 - self.depth

        if shift < 0:
            raise ValueError("Negative shifting is not possible.")

        bit = (c.code >> shift) & 1
        if shift == 0:
            if c.range_length == -1:
                # the child will be a OutOfBand
                if bit == 1:
                    if self.one is not None:
                        raise RuntimeError(f"already have a OOB for {c}")
                    self.one = OutOfBandNode(c)
                else:
                    if self.zero is not None:
                        raise RuntimeError(f"already have a OOB for {c}")
                    self.zero = OutOfBandNode(c)
            else:
                # the child will be a ValueNode
                if bit == 1:
                    if self.one is not None:
                        raise RuntimeError(f"already have a ValueNode for {c}")
                    self.one = ValueNode(c)
                else:
                    if self.zero is not None:
                        raise RuntimeError(f"already have a ValueNode for {c}")
                    self.zero = ValueNode(c)
        else:
            # the child will be an InternalNode
            if bit == 1:
                if self.one is None:
                    self.one = InternalNode(self.depth + 1)
                self.one.append(c)
            else:
                if self.zero is None:
                    self.zero = InternalNode(self.depth + 1)
                self.zero.append(c)

    def decode(self, iis: ImageInputStream) -> int:
        b = iis.read_bit()
        n = self.zero if b == 0 else self.one
        return n.decode(iis)

    def __str__(self) -> str:
        pad = "   " * self.depth
        return f"\n{pad}0: {self.zero}\n{pad}1: {self.one}\n"
