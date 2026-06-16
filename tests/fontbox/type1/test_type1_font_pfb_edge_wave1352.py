"""Wave 1352 — Type1Font.create_with_pfb error-path edge cases and the
trailing ``cleartomark`` ASCII-record exclusion branch.

Targets the under-covered framing branches in
``pypdfbox/fontbox/type1/type1_font.py``:

* line 209 — record header truncated immediately after the type byte (no
  length / payload follows, so the parser breaks out cleanly without
  raising);
* lines 218-219 — length field truncated before the 4-byte little-endian
  size can be read;
* lines 223-224 — record length is negative;
* lines 226-227 — record length exceeds the entire input;
* lines 229-230 — record length plausible vs the total stream but the
  payload itself is truncated;
* lines 248-249 — trailing ASCII record carries ``cleartomark`` and is
  excluded from segment 1 (matches upstream ``PfbParser.getSegment1()``
  / ``PfbParser.java`` L295-L310).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.type1.type1_font import Type1Font


def _wrap_pfb_record(record_type: int, payload: bytes) -> bytes:
    return bytes((0x80, record_type)) + struct.pack("<I", len(payload)) + payload


def _make_minimal_pfb(seg1: bytes, seg2: bytes, *, trailing: bytes = b"") -> bytes:
    return (
        _wrap_pfb_record(0x01, seg1)
        + _wrap_pfb_record(0x02, seg2)
        + trailing
        + b"\x80\x03"
    )


# ---------- header truncation paths ----------


def test_create_with_pfb_breaks_when_marker_is_last_byte() -> None:
    """Loop sees ``pos >= len(raw)`` immediately after consuming the
    start marker (the marker is the very last byte of the input) —
    breaks out cleanly without raising. Exercises line 209.
    """
    seg1 = b"%!PS-AdobeFont-1.0: T\n/FontName /T def\n/Encoding StandardEncoding def\n"
    seg2 = b"\x00\x00\x00\x00"
    truncated = (
        _wrap_pfb_record(0x01, seg1)
        + _wrap_pfb_record(0x02, seg2)
        + b"\x80"  # bare start marker as final byte — no type, no length
    )
    # No exception: loop consumes the trailing marker, advances pos to
    # len(raw), the ``pos >= len(raw)`` guard fires and breaks cleanly.
    font = Type1Font.create_with_pfb(truncated)
    assert font.get_binary_segment() == seg2


def test_create_with_pfb_rejects_truncated_length_field() -> None:
    """The 4-byte little-endian size field is truncated. Exercises 217-219.

    A complete first record gets us past the header-length guard; then
    a partial ``\\x80\\x01\\x00\\x00`` trailer (marker + type + 2 of 4
    length bytes) trips the ``pos + 4 > len(raw)`` check.
    """
    seg1 = b"%!PS-AdobeFont-1.0: T\n/FontName /T def\n/Encoding StandardEncoding def\n"
    bad = _wrap_pfb_record(0x01, seg1) + bytes((0x80, 0x01)) + b"\x00\x00"
    with pytest.raises(OSError, match="EOF while reading PFB font"):
        Type1Font.create_with_pfb(bad)


def test_create_with_pfb_rejects_negative_record_size() -> None:
    """Signed-decoded record length is < 0. Exercises 222-224."""
    bad = bytes((0x80, 0x01)) + struct.pack("<i", -1) + b"\x00" * 32
    with pytest.raises(OSError, match="record size -1 is negative"):
        Type1Font.create_with_pfb(bad)


def test_create_with_pfb_rejects_oversized_record() -> None:
    """Length field claims more bytes than the entire input. Exercises 225-227."""
    bad = bytes((0x80, 0x01)) + struct.pack("<I", 99999) + b"\x00" * 32
    with pytest.raises(OSError, match="would be larger than the input"):
        Type1Font.create_with_pfb(bad)


def test_create_with_pfb_rejects_truncated_payload() -> None:
    """Length passes the global-size check but the payload itself is short.

    Exercises 228-230. We claim a payload of exactly ``len(raw) - 6``
    (the largest the global-size guard permits) but the in-buffer
    payload only has half that many bytes — because the buffer is split
    by an earlier record.

    Construction: one complete prefix record + a second record whose
    declared size is equal to the total input length minus its header
    (6 bytes for marker+type+length), so ``size <= len(raw)`` passes but
    ``pos + size > len(raw)`` trips.
    """
    prefix = _wrap_pfb_record(0x01, b"AAAA")  # 6 + 4 = 10 bytes
    # After the prefix, pos = 10. Total buffer length will be
    # 10 + 6 + payload_provided. Declare size such that pos+size > len
    # but size <= len. Provide 4 payload bytes; declare size = 100 (>4).
    # len(raw) = 10 + 6 + 4 = 20. size=100 > 20 — fails the global check.
    # Instead provide a huge payload so the global check passes:
    payload_provided = b"X" * 50  # len(raw) = 10 + 6 + 50 = 66
    declared_size = 60  # 60 <= 66 OK, but pos(16) + 60 = 76 > 66 trips next.
    bad = prefix + bytes((0x80, 0x01)) + struct.pack("<I", declared_size) + payload_provided
    # Upstream ``PfbParser`` raises ``EOFException`` for a payload that runs
    # past the input; ``create_with_pfb`` now mirrors that with ``EOFError``
    # (wave 1561 parity fix — was a plain ``OSError`` before).
    with pytest.raises(EOFError, match="EOF while reading PFB font"):
        Type1Font.create_with_pfb(bad)


# ---------- trailing ``cleartomark`` exclusion ----------


def test_create_with_pfb_excludes_trailing_cleartomark_record() -> None:
    """The trailing ASCII record carrying ``cleartomark`` is dropped from
    segment 1 (matches upstream ``PfbParser.getSegment1()``).

    Exercises lines 242-249. We emit:

      record 1 (ASCII)  — main cleartext header
      record 2 (binary) — eexec body
      record 3 (ASCII)  — short ``cleartomark`` trailer

    The trailer must be < 600 bytes and contain ``b"cleartomark"`` for
    the exclusion to fire.
    """
    seg1 = (
        b"%!PS-AdobeFont-1.0: WaveCleartomark\n"
        b"/FontName /WaveCleartomark def\n"
        b"/Encoding StandardEncoding def\n"
    )
    seg2 = b"\x00\x00\x00\x00"
    trailer_ascii = b"0000000000\ncleartomark\n"  # < 600 bytes, contains marker
    pfb = (
        _wrap_pfb_record(0x01, seg1)
        + _wrap_pfb_record(0x02, seg2)
        + _wrap_pfb_record(0x01, trailer_ascii)
        + b"\x80\x03"
    )
    font = Type1Font.create_with_pfb(pfb)
    # Segment 1 contains the main header but NOT the trailing cleartomark
    # ASCII record.
    assert font.get_ascii_segment().startswith(b"%!PS-AdobeFont-1.0: WaveCleartomark")
    assert b"cleartomark" not in font.get_ascii_segment()


def test_create_with_pfb_keeps_long_trailing_ascii_record() -> None:
    """An ASCII trailer >= 600 bytes is *kept* in segment 1 even if it
    happens to contain ``cleartomark``. Guard branch — the cleartomark
    exclusion only fires for the conventional short trailer.
    """
    seg1 = (
        b"%!PS-AdobeFont-1.0: WaveLongTrailer\n"
        b"/FontName /WaveLongTrailer def\n"
        b"/Encoding StandardEncoding def\n"
    )
    seg2 = b"\x00\x00\x00\x00"
    long_trailer = b"X" * 600 + b"\ncleartomark\n"  # >= 600 bytes
    pfb = (
        _wrap_pfb_record(0x01, seg1)
        + _wrap_pfb_record(0x02, seg2)
        + _wrap_pfb_record(0x01, long_trailer)
        + b"\x80\x03"
    )
    font = Type1Font.create_with_pfb(pfb)
    # The long trailer is folded back into segment 1.
    assert b"cleartomark" in font.get_ascii_segment()
