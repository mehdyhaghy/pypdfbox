"""Tests for :class:`CCITTFaxDecoderStream` / :class:`CCITTFaxEncoderStream`.

The streams delegate to libtiff via :class:`CCITTFaxDecode`; these tests
exercise the stream-shaped front end (construction, buffering, round-trip
via the encoder/decoder pair).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.filter import CCITTFaxDecoderStream, CCITTFaxEncoderStream
from pypdfbox.filter.tiff_extension import TIFFExtension


class TestCCITTFaxStreamsRoundtrip:
    @pytest.fixture(scope="class")
    def raw_image(self) -> bytes:
        # 16-pixel-wide × 8-row alternating bands of black/white.
        # 16 pixels = 2 bytes per row; 8 rows = 16 bytes.
        rows = []
        for r in range(8):
            rows.append(b"\x00\x00" if r % 2 == 0 else b"\xff\xff")
        return b"".join(rows)

    def test_g4_encode_then_decode(self, raw_image: bytes) -> None:
        # Encode
        out = io.BytesIO()
        enc = CCITTFaxEncoderStream(
            out,
            columns=16,
            rows=8,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
        enc.write(raw_image)
        enc.flush()
        encoded = out.getvalue()
        assert encoded  # libtiff produced something

        # Decode
        dec = CCITTFaxDecoderStream(
            io.BytesIO(encoded),
            columns=16,
            rows=8,
            type_=TIFFExtension.COMPRESSION_CCITT_T6,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
        decoded = dec.read()
        assert decoded == raw_image
        # Keep enc alive
        del enc

    def test_decoder_stream_read_sized(self) -> None:
        # Encode a small image first
        raw = b"\x00\x00" * 8 + b"\xff\xff" * 8  # 16 wide × 16 tall
        out = io.BytesIO()
        enc = CCITTFaxEncoderStream(
            out,
            columns=16,
            rows=16,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
        enc.write(raw)
        enc.flush()
        encoded = out.getvalue()
        del enc

        dec = CCITTFaxDecoderStream(
            io.BytesIO(encoded),
            columns=16,
            rows=16,
            type_=TIFFExtension.COMPRESSION_CCITT_T6,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
        chunks = []
        while True:
            chunk = dec.read(4)
            if not chunk:
                break
            chunks.append(chunk)
        assert b"".join(chunks) == raw

    def test_decoder_mark_supported_false(self) -> None:
        dec = CCITTFaxDecoderStream(
            io.BytesIO(b""),
            columns=8,
            rows=1,
            type_=TIFFExtension.COMPRESSION_CCITT_T6,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
        assert dec.mark_supported() is False

    def test_decoder_reset_raises(self) -> None:
        dec = CCITTFaxDecoderStream(
            io.BytesIO(b""),
            columns=8,
            rows=1,
            type_=TIFFExtension.COMPRESSION_CCITT_T6,
            fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
        )
        with pytest.raises(OSError):
            dec.reset()
