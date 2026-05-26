"""Base class for the nodes of a Huffman prefix-code tree.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.Node``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


class Node(ABC):
    """Base class for all nodes in a Huffman tree."""

    @abstractmethod
    def decode(self, iis: ImageInputStream) -> int:
        """Decode one value from ``iis`` by descending the tree."""
        raise NotImplementedError
