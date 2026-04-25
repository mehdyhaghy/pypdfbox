"""Hand-written tests for ``FlateDecode``."""

from __future__ import annotations

import io
import zlib

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FilterFactory, FlateDecode


def _round_trip(data: bytes, parameters: COSDictionary | None = None) -> bytes:
    """Encode then decode ``data`` and return the round-trip output."""
    flate = FlateDecode()
    encoded = io.BytesIO()
    flate.encode(io.BytesIO(data), encoded, parameters)
    decoded = io.BytesIO()
    flate.decode(io.BytesIO(encoded.getvalue()), decoded, parameters)
    return decoded.getvalue()


class TestRoundTrip:
    def test_empty_input(self) -> None:
        assert _round_trip(b"") == b""

    def test_single_byte(self) -> None:
        assert _round_trip(b"\x42") == b"\x42"

    def test_short_text(self) -> None:
        original = "Hello, PDF world!".encode(encoding="utf-8")
        assert _round_trip(original) == original

    def test_repetitive_input_compresses(self) -> None:
        original = b"abc" * 4000
        flate = FlateDecode()
        encoded = io.BytesIO()
        flate.encode(io.BytesIO(original), encoded, None)
        # Highly repetitive data should compress much smaller.
        assert len(encoded.getvalue()) < len(original) // 4
        decoded = io.BytesIO()
        flate.decode(io.BytesIO(encoded.getvalue()), decoded, None)
        assert decoded.getvalue() == original

    def test_random_bytes(self) -> None:
        # Round-trip on a fixed, known sequence of all 256 byte values.
        original = bytes(range(256)) * 5
        assert _round_trip(original) == original


class TestDecodeResult:
    def test_bytes_written_matches_output(self) -> None:
        flate = FlateDecode()
        original = b"abcdefghijklmnopqrstuvwxyz"
        encoded = zlib.compress(original)
        out = io.BytesIO()
        result = flate.decode(io.BytesIO(encoded), out, None)
        assert result.bytes_written == len(original)
        assert out.getvalue() == original

    def test_parameters_returned_unchanged(self) -> None:
        flate = FlateDecode()
        params = COSDictionary()
        params.set_int("Predictor", 1)
        encoded = zlib.compress(b"hello")
        out = io.BytesIO()
        result = flate.decode(io.BytesIO(encoded), out, params)
        # Pass-through (no DCT-style mutation).
        assert result.parameters is params


class TestPredictor:
    def test_png_up_predictor_columns_4(self) -> None:
        # Two-row image, columns=4, colors=1, bits=8 → row_bytes=4.
        # Original raw bytes:
        #   row0 = [10, 20, 30, 40]
        #   row1 = [11, 22, 33, 44]
        # With PNG /Up filter (type=2) the encoder emits, for each row,
        # a tag byte followed by (row - prev_row) mod 256.
        # The factory uses /Predictor 12 to mean PNG-Up across all rows.
        encoded_rows = bytearray()
        # Row 0: prev_row is implicitly zero.
        encoded_rows.append(2)  # /Up filter tag
        encoded_rows.extend(bytes([10, 20, 30, 40]))
        # Row 1: difference from row 0.
        encoded_rows.append(2)
        encoded_rows.extend(bytes([(11 - 10) & 0xFF, (22 - 20) & 0xFF,
                                   (33 - 30) & 0xFF, (44 - 40) & 0xFF]))
        compressed = zlib.compress(bytes(encoded_rows))

        params = COSDictionary()
        params.set_int("Predictor", 12)
        params.set_int("Columns", 4)
        params.set_int("Colors", 1)
        params.set_int("BitsPerComponent", 8)

        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == bytes([10, 20, 30, 40, 11, 22, 33, 44])

    def test_png_none_predictor(self) -> None:
        # /Predictor 10 = "predict using PNG None for every row" — each
        # row is preceded by tag 0 and the bytes are unchanged.
        rows = bytearray()
        rows.append(0)
        rows.extend(b"\x01\x02\x03\x04")
        rows.append(0)
        rows.extend(b"\x05\x06\x07\x08")
        compressed = zlib.compress(bytes(rows))

        params = COSDictionary()
        params.set_int("Predictor", 10)
        params.set_int("Columns", 4)

        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == b"\x01\x02\x03\x04\x05\x06\x07\x08"

    def test_png_sub_predictor(self) -> None:
        # /Sub: encoded byte = original - left-neighbor.
        # For a single row [5, 10, 20, 35] with bytes_per_pixel=1:
        #   tag=1, then [5, 5, 10, 15].
        encoded = bytearray([1, 5, 5, 10, 15])
        compressed = zlib.compress(bytes(encoded))
        params = COSDictionary()
        params.set_int("Predictor", 11)  # /Sub
        params.set_int("Columns", 4)
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == bytes([5, 10, 20, 35])

    def test_png_optimum_predictor_mixed_rows(self) -> None:
        # /Predictor 15 = Optimum: each row's actual filter tag is honoured.
        # Row 0: None (tag=0), bytes [1,2,3,4]
        # Row 1: Up   (tag=2), bytes [10, 10, 10, 10] → original [11,12,13,14]
        rows = bytearray()
        rows.append(0)
        rows.extend(b"\x01\x02\x03\x04")
        rows.append(2)
        rows.extend(bytes([10, 10, 10, 10]))
        compressed = zlib.compress(bytes(rows))
        params = COSDictionary()
        params.set_int("Predictor", 15)
        params.set_int("Columns", 4)
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == bytes([1, 2, 3, 4, 11, 12, 13, 14])

    def test_tiff_predictor_2(self) -> None:
        # TIFF Predictor 2 with colors=1, bits=8, columns=4.
        # Encoded row [5, 5, 10, 15] decodes to [5, 10, 20, 35].
        compressed = zlib.compress(bytes([5, 5, 10, 15]))
        params = COSDictionary()
        params.set_int("Predictor", 2)
        params.set_int("Columns", 4)
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == bytes([5, 10, 20, 35])

    def test_predictor_1_is_no_op(self) -> None:
        # /Predictor 1 = no prediction → same as no parameters.
        compressed = zlib.compress(b"plain bytes")
        params = COSDictionary()
        params.set_int("Predictor", 1)
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == b"plain bytes"

    def test_predictor_encode_raises(self) -> None:
        flate = FlateDecode()
        params = COSDictionary()
        params.set_int("Predictor", 12)
        with pytest.raises(NotImplementedError):
            flate.encode(io.BytesIO(b"x"), io.BytesIO(), params)


class TestErrors:
    def test_truncated_stream_raises_oserror(self) -> None:
        # Compress something then chop off the trailing bytes.
        encoded = zlib.compress(b"some data" * 100)
        truncated = encoded[: len(encoded) // 2]
        flate = FlateDecode()
        with pytest.raises(OSError):
            flate.decode(io.BytesIO(truncated), io.BytesIO(), None)

    def test_garbage_input_raises_oserror(self) -> None:
        flate = FlateDecode()
        with pytest.raises(OSError):
            flate.decode(io.BytesIO(b"not zlib at all"), io.BytesIO(), None)

    def test_unsupported_predictor_raises(self) -> None:
        # Predictor numbers other than 1, 2, and 10..15 are not defined.
        compressed = zlib.compress(b"abcd")
        params = COSDictionary()
        params.set_int("Predictor", 7)
        flate = FlateDecode()
        with pytest.raises(OSError):
            flate.decode(io.BytesIO(compressed), io.BytesIO(), params)


class TestFilterFactoryIntegration:
    def test_long_name_registered(self) -> None:
        assert FilterFactory.is_registered("FlateDecode")

    def test_short_name_resolves(self) -> None:
        assert FilterFactory.is_registered("Fl")
        assert FilterFactory.get("Fl") is FilterFactory.get("FlateDecode")

    def test_factory_returns_flate_decode_instance(self) -> None:
        assert isinstance(FilterFactory.get("FlateDecode"), FlateDecode)
