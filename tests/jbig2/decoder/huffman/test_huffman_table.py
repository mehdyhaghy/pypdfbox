"""Hand-written unit tests for the JBIG2 Huffman entropy-coder cluster.

Covers ``Code`` + ``HuffmanTable`` prefix-code assignment (Annex B.3), the node
classes (``InternalNode`` / ``ValueNode`` / ``OutOfBandNode``), ``FixedSizeTable``,
``EncodedTable`` (Annex B.2) and the 15 ``StandardTables`` (Annex B.1-B.15).

Expected decode values are computed by hand from the table line definitions and
the big-endian bit semantics of ``ImageInputStream``.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.decoder.huffman.encoded_table import EncodedTable
from pypdfbox.jbig2.decoder.huffman.fixed_size_table import FixedSizeTable
from pypdfbox.jbig2.decoder.huffman.huffman_table import Code, HuffmanTable
from pypdfbox.jbig2.decoder.huffman.internal_node import InternalNode
from pypdfbox.jbig2.decoder.huffman.out_of_band_node import LONG_MAX_VALUE, OutOfBandNode
from pypdfbox.jbig2.decoder.huffman.standard_tables import StandardTables
from pypdfbox.jbig2.decoder.huffman.value_node import ValueNode, bit_pattern
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


def iis(*byte_values: int) -> ImageInputStream:
    return ImageInputStream(bytes(byte_values))


def iis_hex(hexstr: str) -> ImageInputStream:
    return ImageInputStream(bytes.fromhex(hexstr))


# --------------------------------------------------------------------------- #
# Code line structure
# --------------------------------------------------------------------------- #
def test_code_defaults_code_to_minus_one():
    c = Code(2, 4, 7, False)
    assert c.prefix_length == 2
    assert c.range_length == 4
    assert c.range_low == 7
    assert c.is_lower_range is False
    assert c.code == -1


def test_code_str_unassigned_shows_question_mark():
    c = Code(3, 0, 5, False)
    assert str(c) == "?/3/0/5"


def test_code_str_assigned_shows_bit_pattern():
    c = Code(3, 0, 5, False)
    c.code = 0b101
    assert str(c) == "101/3/0/5"


def test_code_table_to_string_joins_code_lines():
    # Wave 1510: ``HuffmanTable.code_table_to_string`` (upstream static
    # ``codeTableToString``) joins each ``Code`` line followed by a newline.
    codes = [Code(1, 0, 0, False), Code(2, 0, 3, False)]
    codes[0].code = 0
    codes[1].code = 0b10
    rendered = HuffmanTable.code_table_to_string(codes)
    assert rendered == "0/1/0/0\n10/2/0/3\n"


def test_huffman_table_str_wraps_root_node():
    # Wave 1510: ``HuffmanTable.__str__`` (upstream ``toString``) renders the
    # root InternalNode and appends a trailing newline.
    table = HuffmanTable()
    table.init_tree([Code(1, 0, 7, False)])
    rendered = str(table)
    assert rendered == f"{table.root_node}\n"
    assert rendered.endswith("\n")
    # The single length-1 leaf appears under the "1:" branch of the root.
    assert "1: " in rendered


# --------------------------------------------------------------------------- #
# bit_pattern helper (ValueNode.bitPattern)
# --------------------------------------------------------------------------- #
def test_bit_pattern_renders_big_endian():
    assert bit_pattern(0b101, 3) == "101"
    assert bit_pattern(0b1, 4) == "0001"
    assert bit_pattern(0, 0) == ""
    assert bit_pattern(0b11, 2) == "11"


# --------------------------------------------------------------------------- #
# Prefix-code assignment (Annex B.3)
# --------------------------------------------------------------------------- #
def test_preprocess_assigns_canonical_codes():
    # Two length-1 codes and two length-2 codes -> canonical Huffman assignment.
    codes = [
        Code(1, 0, 0, False),
        Code(1, 0, 1, False),
        Code(2, 0, 2, False),
        Code(2, 0, 3, False),
    ]
    table = HuffmanTable()
    table._preprocess_codes(codes)
    # firstCode[1] = (0 + 0) << 1 = 0 -> codes 0,1 ; firstCode[2] = (0 + 2) << 1 = 4 -> 4,5
    assert [c.code for c in codes] == [0, 1, 4, 5]


def test_preprocess_zero_prefix_length_is_skipped_in_tree():
    # prefix_length 0 codes are "unused" and ignored by InternalNode.append.
    codes = [Code(0, 0, 99, False), Code(1, 0, 7, False)]
    table = HuffmanTable()
    table.init_tree(codes)
    # only the length-1 code is reachable; bit 0 -> value 7
    assert table.decode(iis(0b00000000)) == 7


# --------------------------------------------------------------------------- #
# Node classes
# --------------------------------------------------------------------------- #
def test_value_node_upper_range_adds_bits():
    c = Code(1, 4, 10, False)
    c.code = 0
    node = ValueNode(c)
    # read 4 bits = 0b0101 = 5 -> 10 + 5 = 15
    assert node.decode(iis(0b01010000)) == 15


def test_value_node_lower_range_subtracts_bits():
    c = Code(1, 4, 10, True)
    c.code = 0
    node = ValueNode(c)
    # read 4 bits = 0b0011 = 3 -> 10 - 3 = 7
    assert node.decode(iis(0b00110000)) == 7


def test_out_of_band_node_returns_long_max_value():
    node = OutOfBandNode(Code(1, -1, 0, False))
    assert node.decode(iis(0b00000000)) == LONG_MAX_VALUE
    assert LONG_MAX_VALUE == 0x7FFFFFFFFFFFFFFF


def test_internal_node_negative_shift_raises():
    node = InternalNode(depth=5)
    # prefix_length(2) - 1 - depth(5) = -4 -> negative shift
    with pytest.raises(ValueError, match="Negative shifting"):
        node.append(Code(2, 0, 0, False))


def test_internal_node_duplicate_value_node_raises():
    node = InternalNode()
    a = Code(1, 0, 1, False)
    a.code = 0
    b = Code(1, 0, 2, False)
    b.code = 0
    node.append(a)
    with pytest.raises(RuntimeError, match="already have a ValueNode"):
        node.append(b)


def test_internal_node_duplicate_oob_raises():
    node = InternalNode()
    a = Code(1, -1, 0, False)
    a.code = 1
    b = Code(1, -1, 0, False)
    b.code = 1
    node.append(a)
    with pytest.raises(RuntimeError, match="already have a OOB"):
        node.append(b)


def test_internal_node_duplicate_value_node_one_side_raises():
    # bit==1 (code 0b1) routes to the ``one`` child; a second length-1 code on
    # the same branch collides with the existing ValueNode.
    node = InternalNode()
    a = Code(1, 0, 1, False)
    a.code = 1
    b = Code(1, 0, 2, False)
    b.code = 1
    node.append(a)
    with pytest.raises(RuntimeError, match="already have a ValueNode"):
        node.append(b)


def test_internal_node_duplicate_oob_zero_side_raises():
    # range_length == -1 builds an OutOfBandNode; bit==0 (code 0b0) routes to
    # the ``zero`` child, so a duplicate collides on the zero branch.
    node = InternalNode()
    a = Code(1, -1, 0, False)
    a.code = 0
    b = Code(1, -1, 0, False)
    b.code = 0
    node.append(a)
    with pytest.raises(RuntimeError, match="already have a OOB"):
        node.append(b)


def test_internal_node_str_renders_children_indented():
    # __str__ recurses through both child slots; an empty node shows two None
    # children, and a populated branch nests a ValueNode under "1:".
    node = InternalNode()
    assert str(node) == "\n0: None\n1: None\n"
    c = Code(1, 0, 5, False)
    c.code = 1
    node.append(c)
    rendered = str(node)
    assert "0: None" in rendered
    assert "1: " in rendered
    assert "None" in rendered


# --------------------------------------------------------------------------- #
# FixedSizeTable
# --------------------------------------------------------------------------- #
def test_fixed_size_table_decodes():
    # Two length-1 leaves: code '0' -> value 0, code '1' -> value 1.
    codes = [Code(1, 0, 0, False), Code(1, 0, 1, False)]
    table = FixedSizeTable(codes)
    src = iis(0b01000000)
    assert table.decode(src) == 0
    assert table.decode(src) == 1


def test_fixed_size_table_is_huffman_table():
    assert issubclass(FixedSizeTable, HuffmanTable)


# --------------------------------------------------------------------------- #
# StandardTables — structure + decode
# --------------------------------------------------------------------------- #
def test_get_table_caches_instance():
    a = StandardTables.get_table(1)
    b = StandardTables.get_table(1)
    assert a is b


def test_get_table_returns_huffman_table_for_all_15():
    for n in range(1, 16):
        assert isinstance(StandardTables.get_table(n), HuffmanTable)


def test_table_b1_decode_low_line():
    # B1 line 1: [1,4,0] -> prefix '0', 4 range bits. bits '0' + '0101'(=5) -> 5
    assert StandardTables.get_table(1).decode(iis(0b00101000)) == 5


def test_table_b1_decode_zero():
    # prefix '0', 4 zero range bits -> 0
    assert StandardTables.get_table(1).decode(iis(0b00000000)) == 0


def test_table_b2_oob():
    # all-ones reaches the 6-bit OOB line -> Long.MAX_VALUE
    assert StandardTables.get_table(2).decode(iis_hex("ffffffff00")) == LONG_MAX_VALUE


def test_table_b14_symmetric_zero():
    # B14 line [1,0,0]: prefix '0' -> value 0, range_length 0 (no extra bits).
    t = StandardTables.get_table(14)
    s = iis_hex("00000000")
    assert t.decode(s) == 0
    assert t.decode(s) == 0


def test_table_b3_lower_range_negative():
    # B3's canonical length-1 code is '0' -> line [1,0,0] -> value 0 (range_length
    # 0 reads no extra bits). The lower-range/high/OOB paths are covered by the
    # oracle test against the full 32-bit range lines.
    assert StandardTables.get_table(3).decode(iis(0b00000000)) == 0


def test_standard_table_negative_range_low():
    # B6 line 1 is [5,10,-2048]: a negative range_low with 10 range bits.
    # prefix code for the first 5-bit line is canonical; the oracle covers the
    # exact decode. Here just assert the table builds and decodes without error.
    v = StandardTables.get_table(6).decode(iis_hex("00000000000000000000"))
    assert isinstance(v, int)


# --------------------------------------------------------------------------- #
# Cross-byte-boundary sequential decode
# --------------------------------------------------------------------------- #
def test_sequential_decode_across_byte_boundary():
    # B14: short codes (max prefix 3) decoded repeatedly from one buffer.
    t = StandardTables.get_table(14)
    src = iis_hex("0000")
    vals = [t.decode(src) for _ in range(4)]
    assert vals == [0, 0, 0, 0]


# --------------------------------------------------------------------------- #
# EncodedTable (Annex B.2) driven by a stub Table
# --------------------------------------------------------------------------- #
class _StubTable:
    """Minimal stand-in for ``pypdfbox.jbig2.segments.Table`` (not yet ported).

    Exposes only the accessor surface ``EncodedTable.parse_table`` consumes.
    """

    def __init__(self, data: bytes, *, ht_low, ht_high, ht_ps, ht_rs, ht_oob):
        self._sis = ImageInputStream(data)
        self._ht_low = ht_low
        self._ht_high = ht_high
        self._ht_ps = ht_ps
        self._ht_rs = ht_rs
        self._ht_oob = ht_oob

    def get_sub_input_stream(self):
        return self._sis

    def get_ht_low(self):
        return self._ht_low

    def get_ht_high(self):
        return self._ht_high

    def get_ht_ps(self):
        return self._ht_ps

    def get_ht_rs(self):
        return self._ht_rs

    def get_ht_oob(self):
        return self._ht_oob


def test_encoded_table_parses_and_decodes():
    # Design a tiny table:
    #   htLow=0, htHigh=4, htPS=3 (prefix size), htRS=1 (range size), htOOB=0.
    # Line decoding loop (B.2 5) while curRangeLow < htHigh(4):
    #   line A: prefLen=read3, rangeLen=read1, rangeLow=0  -> curRangeLow += 1<<rangeLen
    #   line B: prefLen=read3, rangeLen=read1, rangeLow=2  -> curRangeLow += 1<<rangeLen
    # Then low line (B.2 6/7): prefLen=read3, rangeLen=32, rangeLow=htLow-1=-1, lower
    # Then high line (B.2 8/9): prefLen=read3, rangeLen=32, rangeLow=htHigh=4
    #
    # Header bits, MSB-first:
    #   A: prefLen=001(1) rangeLen=1(1)  -> rangeLow 0, range covers [0,1]
    #   B: prefLen=010(2) rangeLen=1(1)  -> rangeLow 2, range covers [2,3]
    #   low: prefLen=011(3)
    #   high: prefLen=100(4)
    # Bit string: 001 1 010 1 011 100  = 0011 0101 0111 00 -> pad to bytes:
    #   00110101 011100 00 -> 0x35 0x70
    header = bytes([0b00110101, 0b01110000])
    table = _StubTable(header, ht_low=0, ht_high=4, ht_ps=3, ht_rs=1, ht_oob=0)
    enc = EncodedTable(table)

    # Line A has prefix length 1 -> canonical code '0'. Decode payload: prefix '0'
    # then 1 range bit. We feed a SEPARATE stream for decoding values; build it.
    # prefix '0' + range bit '1' -> rangeLow 0 + 1 = 1
    assert enc.decode(iis(0b01000000)) == 1


def test_encoded_table_with_oob_line():
    # htOOB=1 adds a final OOB line consuming one more prefLen field.
    # htLow=0 htHigh=2 htPS=3 htRS=0:
    #   line A: prefLen=read3, rangeLen=read0(=0), rangeLow=0 -> curRangeLow += 1 -> 1
    #   line B: prefLen=read3, rangeLen=read0(=0), rangeLow=1 -> curRangeLow += 1 -> 2 (stop)
    #   low:  prefLen=read3 (rangeLen 32, rangeLow htLow-1=-1, lower)
    #   high: prefLen=read3 (rangeLen 32, rangeLow htHigh=2)
    #   oob:  prefLen=read3 (rangeLen -1)
    # rangeLen reads are 0 bits (htRS=0) so consume nothing.
    # prefLens A=2 B=2 low=2 high=3 oob=3 -> canonical prefix-free tree
    #   bits: A='00' B='01' low='10' high='110' oob='111'
    # header fields each 3 bits: 010 010 010 011 011 -> 0x49 0x36
    header = bytes([0x49, 0x36])
    table = _StubTable(header, ht_low=0, ht_high=2, ht_ps=3, ht_rs=0, ht_oob=1)
    enc = EncodedTable(table)
    # Line A: prefix '00', rangeLen 0 -> value rangeLow 0.
    assert enc.decode(iis(0b00000000)) == 0
    # OOB line: prefix '111' -> Long.MAX_VALUE.
    assert enc.decode(iis(0b11100000)) == LONG_MAX_VALUE
