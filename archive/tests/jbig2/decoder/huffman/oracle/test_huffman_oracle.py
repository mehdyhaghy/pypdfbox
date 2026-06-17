"""Live differential oracle for the JBIG2 Huffman entropy coder.

Drives upstream Apache PDFBox ``StandardTables.getTable(n)`` +
``HuffmanTable.decode(ImageInputStream)`` via ``oracle/probes/HuffmanProbe.java``
on fixed bit sequences, and asserts pypdfbox's ``StandardTables`` produces the
IDENTICAL decoded value sequence. This is the gold-standard parity check that the
15 standard tables' prefix lengths / range values are bit-exact (so symbol/text
region decoding in a later wave is correct).

The out-of-band sentinel is Java ``Long.MAX_VALUE`` (9223372036854775807);
pypdfbox's ``OutOfBandNode`` returns the same value.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.decoder.huffman.standard_tables import StandardTables
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(table_number: int, hexbytes: str, count: int) -> list[int]:
    table = StandardTables.get_table(table_number)
    iis = ImageInputStream(bytes.fromhex(hexbytes))
    return [table.decode(iis) for _ in range(count)]


# (table_number, hexbytes, count). Buffers are sized so the 32-bit high/low range
# reads never hit EOF; counts on the short-prefix tables exercise sequential
# decoding across byte boundaries.
_CASES = [
    # single decode, every table, all-zero bits (short low-end codes / lows)
    *[(n, "00000000000000000000", 1) for n in range(1, 16)],
    # single decode, every table, all-one bits (high-range / OOB lines)
    *[(n, "ffffffffffffffffffff", 1) for n in range(1, 16)],
    # single decode, every table, mixed nibble walk
    *[(n, "123456789abcdef01234", 1) for n in range(1, 16)],
    # single decode, every table, alternating 0xA5
    *[(n, "a5a5a5a5a5a5a5a5a5a5", 1) for n in range(1, 16)],
    # multi-value sequential decodes (cross byte boundaries) on short-prefix tables
    (14, "a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5", 8),
    (14, "0123456789abcdef0123456789abcdef", 8),
    (11, "0123456789abcdef0123456789abcdef", 6),
    (12, "0123456789abcdef0123456789abcdef", 4),
    (13, "fedcba9876543210fedcba9876543210", 4),
    (2, "00112233445566778899aabbccddeeff", 3),
]


@requires_oracle
@pytest.mark.parametrize(
    ("table_number", "hexbytes", "count"),
    _CASES,
    ids=[f"B{n}-{h[:8]}-x{c}" for (n, h, c) in _CASES],
)
def test_standard_table_decode_matches_pdfbox(table_number, hexbytes, count):
    java_out = run_probe_text("HuffmanProbe", str(table_number), hexbytes, str(count))
    java_values = [int(line) for line in java_out.split()]

    py_values = _py_decode(table_number, hexbytes, count)

    assert py_values == java_values
    assert len(py_values) == count
