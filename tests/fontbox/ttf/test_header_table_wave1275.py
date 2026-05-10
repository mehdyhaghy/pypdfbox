"""Wave 1275 — HeaderTable.read_headers fast-path parity."""

from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.header_table import HeaderTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders


def _build_head_bytes(mac_style: int) -> bytes:
    """Build the 54-byte ``head`` table prefix consumed by ``read_headers``.

    Layout (44 bytes skipped, then a 2-byte unsigned short macStyle):
      version (4) + fontRevision (4) + checkSumAdjustment (4) +
      magicNumber (4) + flags (2) + unitsPerEm (2) + created (8) +
      modified (8) + xMin (2) + yMin (2) + xMax (2) + yMax (2) +
      macStyle (2) + lowestRecPPEM (2) + fontDirectionHint (2) +
      indexToLocFormat (2) + glyphDataFormat (2)
    """
    return b"\x00" * 44 + struct.pack(">H", mac_style) + b"\x00" * 8


def test_header_table_read_headers_extracts_mac_style() -> None:
    # macStyle=0x0003 == bold + italic flags both on.
    raw = _build_head_bytes(mac_style=0x0003)
    stream = MemoryTTFDataStream(raw)
    headers = FontHeaders()
    table = HeaderTable()

    table.read_headers(None, stream, headers)  # type: ignore[arg-type]

    assert headers.get_header_mac_style() == 0x0003
    # Side-effect: the table's mac_style field is also populated, so a
    # follow-up accessor matches without re-reading.
    assert table.get_mac_style() == 0x0003


def test_header_table_read_headers_default_zero() -> None:
    raw = _build_head_bytes(mac_style=0x0000)
    stream = MemoryTTFDataStream(raw)
    headers = FontHeaders()
    HeaderTable().read_headers(None, stream, headers)  # type: ignore[arg-type]
    assert headers.get_header_mac_style() == 0
