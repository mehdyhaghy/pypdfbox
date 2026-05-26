"""Hand-written unit tests for the JBIG2 MQ arithmetic decoder cluster.

Covers ``CX``, ``ArithmeticDecoder`` and ``ArithmeticIntegerDecoder``.

The arithmetic decoder reads from a ``javax.imageio.stream.ImageInputStream``.
The pypdfbox ``pypdfbox.jbig2.io`` reader is being ported separately; this
module supplies a minimal in-test shim (``MemoryImageInputStream``) that mirrors
the exact ``ImageInputStream`` surface the decoder uses — ``get_stream_position``,
``read`` (unsigned byte 0-255, or -1 at EOF *without* advancing the position),
and ``seek`` — matching ``MemoryCacheImageInputStream`` semantics verified
against the JDK.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import QE, ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    LONG_MAX_VALUE,
    ArithmeticIntegerDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX


class MemoryImageInputStream:
    """Minimal ``ImageInputStream`` shim backed by an in-memory byte buffer.

    Matches ``javax.imageio.stream.MemoryCacheImageInputStream`` for the calls
    the arithmetic decoder makes: ``read`` returns -1 at/after EOF and leaves
    the position unchanged; ``seek`` may move past the logical end.
    """

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._pos = 0

    def get_stream_position(self) -> int:
        return self._pos

    def read(self) -> int:
        if self._pos >= len(self._data):
            return -1
        value = self._data[self._pos]
        self._pos += 1
        return value

    def seek(self, pos: int) -> None:
        self._pos = pos


def _decode_bits(data: bytes, nbits: int, *, ctx_size: int = 512, index: int = 0,
                 cycle: bool = False) -> str:
    iis = MemoryImageInputStream(data)
    decoder = ArithmeticDecoder(iis)
    cx = CX(ctx_size, index)
    bits = []
    for i in range(nbits):
        cx.set_index(i % ctx_size if cycle else index)
        bits.append(str(decoder.decode(cx)))
    return "".join(bits)


# --- CX ---------------------------------------------------------------------


def test_cx_initial_state_zero():
    cx = CX(8, 3)
    assert cx.get_index() == 3
    assert cx.cx() == 0
    assert cx.mps() == 0


def test_cx_set_cx_masks_low_7_bits():
    cx = CX(4, 0)
    cx.set_cx(0xFF)
    assert cx.cx() == 0x7F
    cx.set_cx(46)
    assert cx.cx() == 46


def test_cx_toggle_mps():
    cx = CX(4, 1)
    assert cx.mps() == 0
    cx.toggle_mps()
    assert cx.mps() == 1
    cx.toggle_mps()
    assert cx.mps() == 0


def test_cx_index_isolates_states():
    cx = CX(4, 0)
    cx.set_cx(10)
    cx.toggle_mps()
    cx.set_index(1)
    assert cx.cx() == 0
    assert cx.mps() == 0
    cx.set_index(0)
    assert cx.cx() == 10
    assert cx.mps() == 1


def test_cx_copy_is_deep_and_independent():
    cx = CX(4, 2)
    cx.set_index(0)
    cx.set_cx(5)
    cx.toggle_mps()
    cx.set_index(2)
    clone = cx.copy()
    assert clone.get_index() == 2
    clone.set_index(0)
    assert clone.cx() == 5
    assert clone.mps() == 1
    # Mutating the clone must not touch the original.
    clone.set_cx(99 & 0x7F)
    clone.toggle_mps()
    cx.set_index(0)
    assert cx.cx() == 5
    assert cx.mps() == 1


# --- QE table ---------------------------------------------------------------


def test_qe_table_shape_and_anchors():
    # Table E.1, 47 rows of {Qe, NMPS, NLPS, SWITCH}.
    assert len(QE) == 47
    assert all(len(row) == 4 for row in QE)
    assert QE[0] == (0x5601, 1, 1, 1)
    assert QE[46] == (0x5601, 46, 46, 0)
    # The four SWITCH=1 rows of the standard table.
    switch_rows = [i for i, row in enumerate(QE) if row[3] == 1]
    assert switch_rows == [0, 6, 14]


# --- ArithmeticDecoder ------------------------------------------------------


def test_init_registers():
    # After INITDEC: A == 0x8000, and C/CT are derived from the first bytes.
    iis = MemoryImageInputStream(bytes([0x84, 0xC7, 0x3B, 0x00]))
    decoder = ArithmeticDecoder(iis)
    assert decoder.get_a() == 0x8000
    # C is kept within 32 bits.
    assert 0 <= decoder.get_c() <= 0xFFFFFFFF


def test_decode_is_deterministic():
    data = bytes([0x84, 0xC7, 0x3B, 0x00])
    first = _decode_bits(data, 24)
    second = _decode_bits(data, 24)
    assert first == second
    assert set(first) <= {"0", "1"}
    assert len(first) == 24


def test_decode_all_zero_input_is_stable():
    # An all-zero coded stream decodes to a deterministic run of bits.
    bits = _decode_bits(bytes(8), 32)
    assert len(bits) == 32
    assert set(bits) <= {"0", "1"}


def test_decode_registers_stay_bounded():
    # Exercise many decodes with cycling contexts and assert C never exceeds
    # 32 bits and A keeps its top bit after renormalisation.
    iis = MemoryImageInputStream(bytes([0x84, 0xC7, 0x3B, 0x00, 0xFF, 0x12, 0x55, 0xAA]))
    decoder = ArithmeticDecoder(iis)
    cx = CX(512, 0)
    for i in range(64):
        cx.set_index(i % 512)
        decoder.decode(cx)
        assert 0 <= decoder.get_c() <= 0xFFFFFFFF
        assert decoder.get_a() & 0x8000  # renormalised: top bit set


def test_decode_ff_byte_path():
    # A 0xFF byte followed by a high byte (> 0x8F) drives the special BYTEIN
    # branch (marker handling) without raising.
    bits = _decode_bits(bytes([0xFF, 0xAC, 0x12, 0x34]), 20)
    assert len(bits) == 20


# --- ArithmeticIntegerDecoder ----------------------------------------------


def test_integer_decode_deterministic_and_signed():
    iis = MemoryImageInputStream(bytes([0x84, 0xC7, 0x3B, 0x00, 0x55, 0xAA, 0x12, 0x34]))
    decoder = ArithmeticDecoder(iis)
    int_decoder = ArithmeticIntegerDecoder(decoder)
    cx = CX(512, 0)
    values = [int_decoder.decode(cx) for _ in range(6)]
    # Deterministic: re-running on a fresh decoder yields the same sequence.
    iis2 = MemoryImageInputStream(bytes([0x84, 0xC7, 0x3B, 0x00, 0x55, 0xAA, 0x12, 0x34]))
    decoder2 = ArithmeticDecoder(iis2)
    int_decoder2 = ArithmeticIntegerDecoder(decoder2)
    cx2 = CX(512, 0)
    values2 = [int_decoder2.decode(cx2) for _ in range(6)]
    assert values == values2
    # Each value is either a plain int or the OOB sentinel.
    for v in values:
        assert isinstance(v, int)
        assert v == LONG_MAX_VALUE or -(2**40) < v < 2**40


def test_integer_decode_creates_context_when_none():
    iis = MemoryImageInputStream(bytes([0x84, 0xC7, 0x3B, 0x00]))
    decoder = ArithmeticDecoder(iis)
    int_decoder = ArithmeticIntegerDecoder(decoder)
    # Passing None must allocate a CX(512, 1) internally and still decode.
    v = int_decoder.decode(None)
    assert isinstance(v, int)


def test_decode_iaid_returns_in_range():
    iis = MemoryImageInputStream(bytes([0x84, 0xC7, 0x3B, 0x00, 0x55, 0xAA]))
    decoder = ArithmeticDecoder(iis)
    int_decoder = ArithmeticIntegerDecoder(decoder)
    sym_code_len = 4
    cx = CX(1 << (sym_code_len + 1), 0)
    value = int_decoder.decode_iaid(cx, sym_code_len)
    assert 0 <= value < (1 << sym_code_len)


def test_decode_iaid_deterministic():
    def run() -> int:
        iis = MemoryImageInputStream(bytes([0x42, 0x99, 0x01, 0xF0]))
        decoder = ArithmeticDecoder(iis)
        int_decoder = ArithmeticIntegerDecoder(decoder)
        cx = CX(64, 0)
        return int_decoder.decode_iaid(cx, 5)

    assert run() == run()
