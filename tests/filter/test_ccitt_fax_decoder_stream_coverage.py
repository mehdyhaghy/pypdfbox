"""Coverage-boost tests for :mod:`pypdfbox.filter.ccitt_fax_decoder_stream`.

Targets the wrapper's read/skip/readinto plumbing, the G3 (T.4) branch,
the ``EncodedByteAlign`` option, and the parity stubs that mirror the
upstream Java private state-machine methods.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecoderStream, CCITTFaxEncoderStream
from pypdfbox.filter.ccitt_fax_decode import CCITTFaxDecode
from pypdfbox.filter.tiff_extension import TIFFExtension


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_g4(raw: bytes, columns: int, rows: int) -> bytes:
    """Encode ``raw`` (1-bit packed) into CCITT G4 via the encoder stream."""
    out = io.BytesIO()
    enc = CCITTFaxEncoderStream(
        out,
        columns=columns,
        rows=rows,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    enc.write(raw)
    enc.flush()
    return out.getvalue()


def _encode_g3_1d(raw: bytes, columns: int, rows: int) -> bytes:
    """Encode ``raw`` into CCITT G3 1D via :class:`CCITTFaxDecode`.

    The encoder stream class only emits G4, so we go through the lower-level
    filter (``K=0``) to obtain G3-encoded bytes for the decoder stream's G3
    branch.
    """
    params = COSDictionary()
    sub = COSDictionary()
    sub.set_int("K", 0)
    sub.set_int("Columns", columns)
    sub.set_int("Rows", rows)
    params.set_item("DecodeParms", sub)
    enc_out = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_out, sub)
    return enc_out.getvalue()


# ---------------------------------------------------------------------------
# G3 / EncodedByteAlign branches
# ---------------------------------------------------------------------------


def test_decoder_g3_1d_branch_round_trips() -> None:
    """``type_`` != T6 selects ``K=0`` and runs the G3 1D libtiff path."""
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4  # 16 wide x 8 tall
    encoded = _encode_g3_1d(raw, columns=16, rows=8)

    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=8,
        type_=TIFFExtension.COMPRESSION_CCITT_T4,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    decoded = dec.read()
    assert decoded == raw


def test_decoder_encoded_byte_align_option_branch() -> None:
    """``options & 0x4`` toggles ``EncodedByteAlign=True`` on DecodeParms.

    The bit is not honored by libtiff for a stream that was *not* encoded
    byte-aligned, so we only assert the constructor + decode path runs to
    completion without raising — which is enough to cover line 82.
    """
    raw = b"\x00\x00" * 8 + b"\xff\xff" * 8
    encoded = _encode_g4(raw, columns=16, rows=16)

    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=16,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        options=TIFFExtension.GROUP3OPT_FILLBITS,  # 0x4
    )
    # We don't insist on exact equality here — the option toggle changes
    # libtiff's framing expectations and the round-trip may differ. Just
    # exercise the decode path.
    out = dec.read()
    assert isinstance(out, bytes)


# ---------------------------------------------------------------------------
# RawIOBase plumbing
# ---------------------------------------------------------------------------


def test_decoder_readable_returns_true() -> None:
    dec = CCITTFaxDecoderStream(
        io.BytesIO(b""),
        columns=8,
        rows=1,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    assert dec.readable() is True


def test_decoder_readinto_fills_buffer() -> None:
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4  # 16 bytes
    encoded = _encode_g4(raw, columns=16, rows=8)
    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=8,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )

    buf = bytearray(8)
    n = dec.readinto(buf)
    assert n == 8
    assert bytes(buf) == raw[:8]

    # Second call drains the remaining bytes.
    buf2 = bytearray(8)
    n2 = dec.readinto(buf2)
    assert n2 == 8
    assert bytes(buf2) == raw[8:]

    # Third call: stream empty.
    buf3 = bytearray(4)
    n3 = dec.readinto(buf3)
    assert n3 == 0


def test_decoder_readinto_short_target_returns_partial() -> None:
    """``readinto`` honors the destination buffer length."""
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4
    encoded = _encode_g4(raw, columns=16, rows=8)
    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=8,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    target = bytearray(3)
    n = dec.readinto(target)
    assert n == 3
    assert bytes(target) == raw[:3]


# ---------------------------------------------------------------------------
# skip()
# ---------------------------------------------------------------------------


def test_decoder_skip_zero_or_negative_returns_zero() -> None:
    dec = CCITTFaxDecoderStream(
        io.BytesIO(b""),
        columns=8,
        rows=1,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    assert dec.skip(0) == 0
    assert dec.skip(-5) == 0


def test_decoder_skip_advances_position() -> None:
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4
    encoded = _encode_g4(raw, columns=16, rows=8)
    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=8,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    stepped = dec.skip(4)
    assert stepped == 4
    rest = dec.read()
    assert rest == raw[4:]


def test_decoder_skip_clamps_to_available() -> None:
    """Asking for more bytes than remain returns the bytes actually skipped."""
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4  # 16 bytes
    encoded = _encode_g4(raw, columns=16, rows=8)
    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=8,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    stepped = dec.skip(10_000)
    assert stepped == 16
    assert dec.read() == b""


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


def test_decoder_close_closes_underlying_stream() -> None:
    inner = io.BytesIO(b"")
    dec = CCITTFaxDecoderStream(
        inner,
        columns=8,
        rows=1,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    dec.close()
    assert inner.closed
    assert dec.closed


def test_decoder_close_suppresses_inner_close_failure() -> None:
    class _BadCloser(io.BytesIO):
        _raised = False

        def close(self) -> None:  # noqa: D401 — test stub
            # Only raise on the first close call (the wrapper's). Subsequent
            # finalizer-driven closes must succeed to avoid an unraisable
            # warning at GC time.
            if not self._raised:
                self._raised = True
                raise OSError("boom")
            super().close()

    inner = _BadCloser(b"")
    dec = CCITTFaxDecoderStream(
        inner,
        columns=8,
        rows=1,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    # Should not raise — the close() wrapper suppresses inner failures.
    dec.close()
    assert dec.closed


# ---------------------------------------------------------------------------
# Parity stubs — these mirror upstream private G3/G4 state-machine methods.
# Decoding is delegated to libtiff, so the stubs only ensure decode is
# triggered (where applicable) and return safe defaults.
# ---------------------------------------------------------------------------


def _fresh_dec(raw: bytes = b"") -> CCITTFaxDecoderStream:
    if not raw:
        # An empty stream with no rows -> libtiff trivially produces nothing.
        return CCITTFaxDecoderStream(
            io.BytesIO(b""),
            columns=8,
            rows=0,
            type_=TIFFExtension.COMPRESSION_CCITT_T6,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
    encoded = _encode_g4(raw, columns=16, rows=len(raw) // 2)
    return CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=len(raw) // 2,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )


def test_parity_stubs_fetch_and_decode_helpers_do_not_raise() -> None:
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4
    dec = _fresh_dec(raw)
    # Each of these triggers _ensure_decoded or returns a safe default.
    assert dec.fetch() is None
    assert dec.decode1_d() is None
    assert dec.decode2_d() is None
    assert dec.decode_row() is None
    assert dec.decode_row_type2() is None
    assert dec.decode_row_type4() is None
    assert dec.decode_row_type6() is None


def test_parity_stub_decode_run_returns_zero() -> None:
    dec = _fresh_dec()
    assert dec.decode_run(tree=None) == 0


def test_parity_stub_get_next_changing_element_returns_zero() -> None:
    dec = _fresh_dec()
    assert dec.get_next_changing_element(a0=0, white=True) == 0
    assert dec.get_next_changing_element(a0=5, white=False) == 0


def test_parity_stub_read_bit_returns_false() -> None:
    dec = _fresh_dec()
    assert dec.read_bit() is False


def test_parity_stub_reset_buffer_returns_none() -> None:
    dec = _fresh_dec()
    assert dec.reset_buffer() is None


# ---------------------------------------------------------------------------
# read(None) full-drain branch
# ---------------------------------------------------------------------------


def test_decoder_read_none_drains_entire_buffer() -> None:
    raw = b"\x00\x00" * 4 + b"\xff\xff" * 4
    encoded = _encode_g4(raw, columns=16, rows=8)
    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=8,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    out = dec.read(None)
    assert out == raw
    # Second drain returns empty.
    assert dec.read(None) == b""


# ---------------------------------------------------------------------------
# reset() not supported
# ---------------------------------------------------------------------------


def test_decoder_reset_raises_oserror() -> None:
    dec = CCITTFaxDecoderStream(
        io.BytesIO(b""),
        columns=8,
        rows=1,
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    with pytest.raises(OSError):
        dec.reset()
