"""Huffman entropy-coder subpackage of the JBIG2 port.

Mirrors ``org.apache.pdfbox.jbig2.decoder.huffman``: the prefix-code tree
(``Node`` / ``InternalNode`` / ``ValueNode`` / ``OutOfBandNode``), the
``HuffmanTable`` base class with its inner ``Code`` line structure, the
``FixedSizeTable`` and ``EncodedTable`` concrete tables, and ``StandardTables``
(the 15 standard tables B.1-B.15 of ISO/IEC 14492:2001, ITU-T Rec. T.88,
Annex B). These drive the optional Huffman-coded path of JBIG2 symbol and text
region decoding.
"""
