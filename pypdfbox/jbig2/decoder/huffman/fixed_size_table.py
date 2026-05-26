"""A fixed-size Huffman table.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.FixedSizeTable``.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.huffman_table import Code, HuffmanTable


class FixedSizeTable(HuffmanTable):
    """Represents a fixed size Huffman table."""

    def __init__(self, run_code_table: list[Code]) -> None:
        super().__init__()
        self.init_tree(run_code_table)
