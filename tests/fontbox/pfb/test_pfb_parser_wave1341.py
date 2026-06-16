"""Wave 1341 coverage-boost tests for ``PfbParser``.

Targets the unreached error paths and the path-based constructor:

* ``Path`` / ``str`` source — exercises :meth:`__init__` line 43
  (``Path(source).read_bytes()``).
* graceful EOF after a complete record sequence missing the
  ``0x80 0x03`` terminator (lines 76-77 — the ``if total > 0: break``
  branch).
* EOF after a stray ``0x80`` start marker (line 83 —
  ``"EOF while reading PFB header"``).
* invalid record type byte (line 88 —
  ``"Incorrect record type: ..."``).
* EOF mid-size-field (line 91 — ``"EOF while reading PFB size"``).
* declared record size larger than the input (line 102 —
  ``"record size ... would be larger than the input"``).
* EOF mid-payload (line 107 — ``"EOF while reading PFB font"``).

Line 78 ("PFB header missing" after ``stream.read`` returns empty with
``total == 0``) is dead behind the 18-byte minimum check at line 66 —
no input large enough to reach the inner loop can hit that branch.
Line 100 ("negative size") is also dead because ``size`` is composed
from four unsigned bytes (always 0..0xFFFFFFFF). Line 113
("total record size would be larger than the input") is unreachable —
each record consumes ``6 + size`` bytes, so ``sum(size) <= len(pfb)``
strictly. Flagged in the wave report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.pfb.pfb_parser import PfbParser


def _record(record_type: int, payload: bytes) -> bytes:
    size = len(payload)
    return bytes(
        [
            0x80,
            record_type,
            size & 0xFF,
            (size >> 8) & 0xFF,
            (size >> 16) & 0xFF,
            (size >> 24) & 0xFF,
        ]
    ) + payload


def _build_pfb(ascii_body: bytes, binary_body: bytes, *, terminator: bool = True) -> bytes:
    blob = _record(0x01, ascii_body) + _record(0x02, binary_body)
    if terminator:
        blob += bytes([0x80, 0x03])
    return blob


def test_parser_from_path(tmp_path: Path) -> None:
    """Construction via :class:`pathlib.Path` exercises the path-read
    branch (``__init__`` line 43)."""
    blob = _build_pfb(b"%!PS-AdobeFont\n", b"\x10\x20\x30", terminator=True)
    p = tmp_path / "test.pfb"
    p.write_bytes(blob)
    parser = PfbParser(p)
    assert parser.size() > 0
    lengths = parser.get_lengths()
    assert lengths[0] == len(b"%!PS-AdobeFont\n")
    assert lengths[1] == 3


def test_parser_from_str_path(tmp_path: Path) -> None:
    blob = _build_pfb(b"ascii\n", b"\xff", terminator=True)
    p = tmp_path / "test_str.pfb"
    p.write_bytes(blob)
    parser = PfbParser(str(p))
    assert parser.get_segment2() == b"\xff"


def test_eof_after_records_without_terminator() -> None:
    """A valid record stream that simply ends without the ``0x80 0x03``
    terminator must be accepted gracefully (lines 75-77 — the
    ``total > 0`` branch breaks instead of raising)."""
    blob = _build_pfb(b"ascii_payload\n", b"binary", terminator=False)
    parser = PfbParser(blob)
    # Records were assembled correctly even though no terminator was
    # written — the parser falls out of the loop on EOF.
    assert parser.get_segment1() == b"ascii_payload\n"
    assert parser.get_segment2() == b"binary"


def test_eof_after_start_marker_raises() -> None:
    """A trailing stray ``0x80`` with no following record-type byte
    triggers ``"EOF while reading PFB header"`` (line 83)."""
    blob = _record(0x01, b"x" * 14) + bytes([0x80])  # 6 + 14 + 1 = 21 bytes
    assert len(blob) >= PfbParser.PFB_HEADER_LENGTH
    with pytest.raises(OSError, match="EOF while reading PFB header"):
        PfbParser(blob)


def test_invalid_record_type_raises() -> None:
    """A record-type byte that is neither ``0x01`` / ``0x02`` / ``0x03``
    is rejected with ``"Incorrect record type"`` (line 88)."""
    blob = _record(0x01, b"x" * 14) + bytes([0x80, 0x99])
    with pytest.raises(OSError, match="Incorrect record type"):
        PfbParser(blob)


def test_eof_in_size_field_raises() -> None:
    """EOF mid-way through reading the 4-byte size field triggers
    ``"EOF while reading PFB size"`` (line 91)."""
    blob = _record(0x01, b"x" * 12) + bytes([0x80, 0x01, 0x01, 0x02])
    assert len(blob) >= PfbParser.PFB_HEADER_LENGTH
    with pytest.raises(OSError, match="EOF while reading PFB size"):
        PfbParser(blob)


def test_record_size_larger_than_input_raises() -> None:
    """A record claiming a positive payload larger than the entire blob is
    rejected with "would be larger than the input"."""
    # First record: minimal ASCII (18 bytes, satisfies >= header length).
    # Second record header: 0x80 0x01 + a large *positive* size (top bit
    # clear so it stays positive under the signed decode), no payload.
    pad = _record(0x01, b"a" * 12)  # 18 bytes
    blob = pad + bytes([0x80, 0x01]) + (0x7FFFFFFF).to_bytes(4, "little")
    with pytest.raises(OSError, match="would be larger than the input"):
        PfbParser(blob)


def test_record_size_top_bit_set_is_negative() -> None:
    """A 4-byte size with the high bit set decodes as a *negative* Java int
    and is rejected with "is negative" — matching upstream PfbParser, which
    composes the size as a signed 32-bit value (wave 1561 parity fix; the
    decode was previously unsigned, mis-reporting "larger than the input").
    Oracle (PDFBox 3.0.7): ``record size -1 is negative`` for 0xFFFFFFFF."""
    pad = _record(0x01, b"a" * 12)  # 18 bytes
    blob = pad + bytes([0x80, 0x01, 0xFF, 0xFF, 0xFF, 0xFF])
    with pytest.raises(OSError, match="record size -1 is negative"):
        PfbParser(blob)


def test_eof_in_payload_raises() -> None:
    """A record header that declares a payload size short of EOF (but
    not above ``len(pfb)``) raises ``"EOF while reading PFB font"``
    (line 107)."""
    # First record declares size=64 but supplies only 5 payload bytes.
    # Pad so total file is large enough that ``size <= len(pfb)``
    # passes (64 + 6 header + extras must be at least 64); declared
    # size 24 with only 5 payload bytes and 30 total bytes works.
    blob = (
        bytes([0x80, 0x01, 24, 0, 0, 0])  # header: type=1, size=24
        + b"short"                          # 5-byte payload
        + b"\x00" * 20                      # 20 padding bytes — read returns these as payload
    )
    # Total = 6 + 5 + 20 = 31 bytes. size=24 < 31, so line 101 passes.
    # The 24-byte read returns "short" + 19 padding bytes = 24 bytes...
    # which actually succeeds. To force a short read we need declared
    # size > actual remaining bytes. Adjust: total file 25 bytes,
    # size=24, header consumes 6 → 19 remaining → short read.
    blob = bytes([0x80, 0x01, 24, 0, 0, 0]) + b"x" * 19
    assert len(blob) == 25
    assert len(blob) >= PfbParser.PFB_HEADER_LENGTH
    with pytest.raises(EOFError, match="EOF while reading PFB font"):
        PfbParser(blob)
