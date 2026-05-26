"""Base class for all Huffman table types.

Port of ``org.apache.pdfbox.jbig2.decoder.huffman.HuffmanTable`` (including its
inner ``Code`` line structure). Implements the standard prefix-code assignment
of ISO/IEC 14492:2001 (ITU-T Rec. T.88) Annex B.3.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.internal_node import InternalNode
from pypdfbox.jbig2.decoder.huffman.value_node import bit_pattern
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


class Code:
    """A single line (code) for use in Huffman tables."""

    def __init__(
        self, prefix_length: int, range_length: int, range_low: int, is_lower_range: bool
    ) -> None:
        self.prefix_length = prefix_length
        self.range_length = range_length
        self.range_low = range_low
        self.is_lower_range = is_lower_range
        self.code = -1

    def __str__(self) -> str:
        prefix = bit_pattern(self.code, self.prefix_length) if self.code != -1 else "?"
        return f"{prefix}/{self.prefix_length}/{self.range_length}/{self.range_low}"


class HuffmanTable:
    """Base class for all types of Huffman tables."""

    def __init__(self) -> None:
        self.root_node = InternalNode()

    def init_tree(self, code_table: list[Code]) -> None:
        self._preprocess_codes(code_table)

        for c in code_table:
            self.root_node.append(c)

    def decode(self, iis: ImageInputStream) -> int:
        return self.root_node.decode(iis)

    def __str__(self) -> str:
        return f"{self.root_node}\n"

    @staticmethod
    def code_table_to_string(code_table: list[Code]) -> str:
        return "".join(f"{c}\n" for c in code_table)

    def _preprocess_codes(self, code_table: list[Code]) -> None:
        # Annex B.3 1) - build the histogram
        max_prefix_length = 0
        for c in code_table:
            max_prefix_length = max(max_prefix_length, c.prefix_length)

        len_count = [0] * (max_prefix_length + 1)
        for c in code_table:
            len_count[c.prefix_length] += 1

        first_code = [0] * (len(len_count) + 1)
        len_count[0] = 0

        # Annex B.3 3)
        for cur_len in range(1, len(len_count) + 1):
            # Mirrors the upstream expression verbatim, including its operator
            # precedence: ``(firstCode[curLen - 1] + (lenCount[curLen - 1]) << 1)``
            # binds as ``(firstCode[curLen - 1] + lenCount[curLen - 1]) << 1``.
            first_code[cur_len] = (first_code[cur_len - 1] + len_count[cur_len - 1]) << 1
            cur_code = first_code[cur_len]
            for code in code_table:
                if code.prefix_length == cur_len:
                    code.code = cur_code
                    cur_code += 1
