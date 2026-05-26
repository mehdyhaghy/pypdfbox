"""A Huffman table decoded from an embedded JBIG2 table segment.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.EncodedTable``. Implements the
table-line decoding of ISO/IEC 14492:2001 (ITU-T Rec. T.88) Annex B.2.

The ``table`` argument is a ``pypdfbox.jbig2.segments.Table`` (ported in a later
wave); this class only relies on its accessor surface — ``get_sub_input_stream``,
``get_ht_low``, ``get_ht_high``, ``get_ht_ps``, ``get_ht_rs``, ``get_ht_oob``.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.huffman_table import Code, HuffmanTable


class EncodedTable(HuffmanTable):
    """Represents an encoded Huffman table."""

    def __init__(self, table: object) -> None:
        super().__init__()
        self.table = table
        self.parse_table()

    def parse_table(self) -> None:
        sis = self.table.get_sub_input_stream()

        code_table: list[Code] = []

        cur_range_low = self.table.get_ht_low()

        # Annex B.2 5) - decode table lines
        while cur_range_low < self.table.get_ht_high():
            pref_len = int(sis.read_bits(self.table.get_ht_ps()))
            range_len = int(sis.read_bits(self.table.get_ht_rs()))
            range_low = cur_range_low

            code_table.append(Code(pref_len, range_len, range_low, False))

            cur_range_low += 1 << range_len

        # Annex B.2 6)
        pref_len = int(sis.read_bits(self.table.get_ht_ps()))

        # Annex B.2 7) - lower range table line
        #
        # Made some correction. Spec specifies an incorrect variable -> Replaced
        # highPrefLen with lowPrefLen
        range_len = 32
        range_low = self.table.get_ht_low() - 1
        code_table.append(Code(pref_len, range_len, range_low, True))

        # Annex B.2 8)
        pref_len = int(sis.read_bits(self.table.get_ht_ps()))

        # Annex B.2 9) - upper range table line
        range_len = 32
        range_low = self.table.get_ht_high()
        code_table.append(Code(pref_len, range_len, range_low, False))

        # Annex B.2 10) - out-of-band table line
        if self.table.get_ht_oob() == 1:
            pref_len = int(sis.read_bits(self.table.get_ht_ps()))
            code_table.append(Code(pref_len, -1, -1, False))

        self.init_tree(code_table)
