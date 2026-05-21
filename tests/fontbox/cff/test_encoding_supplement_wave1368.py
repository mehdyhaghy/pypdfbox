"""Wave 1368 — CFF encoding format 0 / 1 + supplemental encoding parity.

CFF spec §16 defines two on-disk encoding formats and a supplemental
encoding block:

* **Format 0**: ``nCodes`` (Card8) followed by ``nCodes`` Card8 codes.
* **Format 1**: ``nRanges`` (Card8) followed by ``(first, nLeft)`` pairs.
* **Supplement**: when the high bit of the format byte is set, an extra
  ``(nSups, [(code, sid) * nSups])`` block follows.

Exercises both formats with and without the supplement bit + boundary
cases (zero codes, zero ranges, single-byte ranges).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_built_in_encoding import Supplement
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.embedded_charset import EmbeddedCharset
from pypdfbox.fontbox.cff.format0_encoding import Format0Encoding
from pypdfbox.fontbox.cff.format1_encoding import Format1Encoding


def _trivial_charset() -> EmbeddedCharset:
    """Builds a small charset that yields well-defined SIDs for the
    GIDs the encoding readers will look up."""
    cs = EmbeddedCharset(is_cid_font=False)
    cs.add_sid(0, 0, ".notdef")
    cs.add_sid(1, 1, "space")
    cs.add_sid(2, 2, "exclam")
    cs.add_sid(3, 3, "quotedbl")
    return cs


def test_read_encoding_format0_without_supplement_high_bit_clear() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # Format byte 0x00 → Format 0, no supplement; nCodes=1, code=0x41
    inp = DataInputByteArray(b"\x00\x01\x41")
    enc = parser.read_encoding(inp, cs)
    assert isinstance(enc, Format0Encoding)
    assert enc.n_codes == 1
    assert enc.get_name(0x41) == "space"
    # No supplement entries when high bit was clear.
    assert list(enc.supplement) == []


def test_read_encoding_format0_with_supplement_high_bit_set() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # Format byte 0x80 → Format 0, with supplement; nCodes=1, code=0x42
    # then supplement: nSups=2, (code=0x90, sid=1), (code=0x91, sid=2)
    inp = DataInputByteArray(b"\x80\x01\x42" + b"\x02\x90\x00\x01\x91\x00\x02")
    enc = parser.read_encoding(inp, cs)
    assert isinstance(enc, Format0Encoding)
    sups = list(enc.supplement)
    assert len(sups) == 2
    assert sups[0].code == 0x90
    assert sups[0].sid == 1
    assert sups[0].name == "space"
    assert sups[1].code == 0x91
    assert sups[1].sid == 2
    assert sups[1].name == "exclam"


def test_read_encoding_format1_without_supplement() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # Format 1, no supplement: nRanges=1, first=0x41, nLeft=1 →
    # covers gid 1 → space @ 0x41 and gid 2 → exclam @ 0x42
    inp = DataInputByteArray(b"\x01\x01\x41\x01")
    enc = parser.read_encoding(inp, cs)
    assert isinstance(enc, Format1Encoding)
    assert enc.get_name(0x41) == "space"
    assert enc.get_name(0x42) == "exclam"
    assert list(enc.supplement) == []


def test_read_encoding_format1_with_supplement_attaches_extra_codes() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # Format byte 0x81 → Format 1, with supplement; nRanges=1
    # first=0x41, nLeft=0 (one glyph), then nSups=1, code=0xA0, sid=3
    inp = DataInputByteArray(b"\x81\x01\x41\x00" + b"\x01\xa0\x00\x03")
    enc = parser.read_encoding(inp, cs)
    assert isinstance(enc, Format1Encoding)
    sups = list(enc.supplement)
    assert len(sups) == 1
    assert sups[0].code == 0xA0
    assert sups[0].sid == 3
    assert sups[0].name == "quotedbl"


def test_read_encoding_format0_zero_codes_with_supplement() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # nCodes=0, then a 1-entry supplement.
    inp = DataInputByteArray(b"\x80\x00" + b"\x01\xb0\x00\x01")
    enc = parser.read_encoding(inp, cs)
    assert isinstance(enc, Format0Encoding)
    assert enc.n_codes == 0
    sups = list(enc.supplement)
    assert len(sups) == 1
    assert sups[0].code == 0xB0
    assert sups[0].name == "space"


def test_read_supplement_zero_entries_leaves_encoding_empty() -> None:
    parser = CFFParser()
    enc = Format0Encoding(0)
    # nSups=0 → no extra entries.
    parser.read_supplement(DataInputByteArray(b"\x00"), enc)
    assert list(enc.supplement) == []


def test_supplement_is_isinstance_of_supplement_class() -> None:
    parser = CFFParser()
    enc = Format0Encoding(0)
    parser.read_supplement(DataInputByteArray(b"\x01\x55\x00\x01"), enc)
    sup = list(enc.supplement)[0]
    assert isinstance(sup, Supplement)


def test_read_encoding_invalid_base_format_two_raises() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # Format byte 0x02 → base format 2 (invalid: only 0 and 1 exist).
    inp = DataInputByteArray(b"\x02")
    with pytest.raises(OSError, match="Invalid encoding base format 2"):
        parser.read_encoding(inp, cs)


def test_read_encoding_format1_zero_ranges() -> None:
    parser = CFFParser()
    cs = _trivial_charset()
    # Format byte 0x01, nRanges=0 → an empty Format 1 encoding.
    inp = DataInputByteArray(b"\x01\x00")
    enc = parser.read_encoding(inp, cs)
    assert isinstance(enc, Format1Encoding)
