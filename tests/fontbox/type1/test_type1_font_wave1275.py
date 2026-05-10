"""Wave 1275 — Type1Font: create_with_pfb / get_font_b_box / get_parser /
to_string parity."""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.type1.type1_font import Type1Font


def _wrap_pfb_record(record_type: int, payload: bytes) -> bytes:
    return bytes((0x80, record_type)) + struct.pack("<I", len(payload)) + payload


def _make_minimal_pfb(seg1: bytes, seg2: bytes) -> bytes:
    return (
        _wrap_pfb_record(0x01, seg1)
        + _wrap_pfb_record(0x02, seg2)
        + b"\x80\x03"
    )


def test_create_with_pfb_rejects_short_input() -> None:
    with pytest.raises(OSError, match="PFB header missing"):
        Type1Font.create_with_pfb(b"")


def test_create_with_pfb_rejects_bad_start_marker() -> None:
    with pytest.raises(OSError, match="Start marker missing"):
        Type1Font.create_with_pfb(b"\x00" * 32)


def test_create_with_pfb_rejects_bad_record_type() -> None:
    # Pad past the 18-byte header guard so we exercise the per-record
    # type-validation branch and not the early header-too-short check.
    bad = bytes((0x80, 0x05)) + struct.pack("<I", 0) + b"\x00" * 32
    with pytest.raises(OSError, match="Incorrect record type"):
        Type1Font.create_with_pfb(bad)


def test_create_with_pfb_splits_into_segments() -> None:
    # Segment 1 carries a recognisable Type 1 cleartext header so the
    # downstream Type1Parser accepts it; segment 2 is empty (an
    # end-of-eexec marker is enough for this framing-only smoke test).
    seg1 = (
        b"%!PS-AdobeFont-1.0: WaveFont\n"
        b"/FontName /WaveFont def\n"
        b"/Encoding StandardEncoding def\n"
    )
    # 4 random-prefix bytes are enough warm-up for the eexec decrypt;
    # the decrypted body is empty (which is fine — we never decode it).
    seg2 = b"\x00\x00\x00\x00"
    pfb = _make_minimal_pfb(seg1, seg2)
    font = Type1Font.create_with_pfb(pfb)
    assert font.get_ascii_segment().startswith(b"%!PS-AdobeFont-1.0: WaveFont")
    assert font.get_binary_segment() == seg2


def test_get_font_b_box_delegates_to_get_font_bbox() -> None:
    font = Type1Font()
    # Empty font: bbox accessor returns None when /FontBBox is missing.
    assert font.get_font_b_box() == font.get_font_bbox()


def test_get_parser_caches_instance() -> None:
    font = Type1Font()
    p1 = font.get_parser()
    p2 = font.get_parser()
    assert p1 is p2


def test_to_string_matches_dunder_str() -> None:
    font = Type1Font()
    assert font.to_string() == str(font)
