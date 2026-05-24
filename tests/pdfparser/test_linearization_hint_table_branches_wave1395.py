"""Wave 1395 — close residual error branches in
``pypdfbox/pdfparser/linearization_hint_table.py``.

Targets:

* Line 181 — ``_BitReader.read`` rejects a negative bit width with
  :class:`HintTableParseError`.
* Lines 213-214 — ``_read_u16`` raises when fewer than 2 bytes remain.
* Lines 221-222 — ``_read_u32`` raises when fewer than 4 bytes remain.

These mirror the upstream Java spec-checks (PDF 32000-1 §F.4) for the
Page Offset Hint Table reader.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfparser.linearization_hint_table import (
    HintTableParseError,
    _BitReader,
    _read_u16,
    _read_u32,
)


def test_bit_reader_rejects_negative_bit_width() -> None:
    reader = _BitReader(b"\xff\xff")
    with pytest.raises(HintTableParseError, match="negative bit width"):
        reader.read(-1)


def test_read_u16_raises_when_source_too_short() -> None:
    with pytest.raises(HintTableParseError, match="u16"):
        _read_u16(b"\x01", 0)


def test_read_u16_raises_when_offset_past_end() -> None:
    with pytest.raises(HintTableParseError, match="u16"):
        _read_u16(b"\x01\x02", 1)


def test_read_u32_raises_when_source_too_short() -> None:
    with pytest.raises(HintTableParseError, match="u32"):
        _read_u32(b"\x00\x01\x02", 0)


def test_read_u32_raises_when_offset_past_end() -> None:
    with pytest.raises(HintTableParseError, match="u32"):
        _read_u32(b"\x00\x01\x02\x03", 1)
