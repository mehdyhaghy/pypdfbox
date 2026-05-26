"""Hand-written tests for the JBIG2 custom-table segment (type 53).

Table parses the code-table flags (B.2.1), lowest value (B.2.2) and highest
value (B.2.3). The buffer layout of the segment data is:

* 1 byte of flags: bit 7 must be 0; bits 4-6 = HTRS-1; bits 1-3 = HTPS-1;
  bit 0 = HTOOB.
* 4 bytes HTLOW (signed).
* 4 bytes HTHIGH (signed).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.table import Table


def _flags(ht_rs: int, ht_ps: int, ht_oob: int) -> int:
    # bits 4-6 store HTRS-1, bits 1-3 store HTPS-1, bit 0 is HTOOB; bit 7 is 0.
    return (((ht_rs - 1) & 0x07) << 4) | (((ht_ps - 1) & 0x07) << 1) | (ht_oob & 0x01)


def _table_data(ht_rs: int, ht_ps: int, ht_oob: int, ht_low: int, ht_high: int) -> bytes:
    return (
        bytes([_flags(ht_rs, ht_ps, ht_oob)])
        + struct.pack(">i", ht_low)
        + struct.pack(">i", ht_high)
    )


def _parse(data: bytes) -> Table:
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    table = Table()
    table.init(None, sis)
    return table


def test_parses_flags_and_bounds():
    table = _parse(_table_data(ht_rs=4, ht_ps=2, ht_oob=1, ht_low=0, ht_high=255))
    assert table.get_ht_rs() == 4
    assert table.get_ht_ps() == 2
    assert table.get_ht_oob() == 1
    assert table.get_ht_low() == 0
    assert table.get_ht_high() == 255


def test_out_of_band_zero():
    table = _parse(_table_data(ht_rs=1, ht_ps=1, ht_oob=0, ht_low=-5, ht_high=10))
    assert table.get_ht_oob() == 0
    assert table.get_ht_rs() == 1
    assert table.get_ht_ps() == 1
    assert table.get_ht_low() == -5
    assert table.get_ht_high() == 10


def test_reserved_bit_7_must_be_zero():
    # Set bit 7 of the flags byte; parsing must reject it.
    data = bytearray(_table_data(ht_rs=1, ht_ps=1, ht_oob=0, ht_low=0, ht_high=1))
    data[0] |= 0x80
    with pytest.raises(InvalidHeaderValueException):
        _parse(bytes(data))


def test_sub_input_stream_exposed():
    data = _table_data(ht_rs=2, ht_ps=3, ht_oob=1, ht_low=1, ht_high=2)
    table = _parse(data)
    assert table.get_sub_input_stream() is not None
