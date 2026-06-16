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


def _raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    return compressor.compress(data) + compressor.flush()


class _FlushTrackingBytesIO(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


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

    def test_raw_deflate_without_zlib_wrapper_decodes(self) -> None:
        original = b"raw deflate stream without zlib header" * 30
        flate = FlateDecode()
        out = io.BytesIO()
        result = flate.decode(io.BytesIO(_raw_deflate(original)), out, None)
        assert out.getvalue() == original
        assert result.bytes_written == len(original)

    def test_decode_flushes_decoded_sink_after_write(self) -> None:
        original = b"flush me after inflate"
        out = _FlushTrackingBytesIO()

        result = FlateDecode().decode(io.BytesIO(zlib.compress(original)), out, None)

        assert out.getvalue() == original
        assert result.bytes_written == len(original)
        assert out.flush_count == 1

    def test_encode_flushes_encoded_sink_after_deflate(self) -> None:
        out = _FlushTrackingBytesIO()

        FlateDecode().encode(io.BytesIO(b"flush me after deflate"), out, None)

        assert zlib.decompress(out.getvalue()) == b"flush me after deflate"
        assert out.flush_count == 1


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

    def test_predictor_encode_round_trip_png_up(self) -> None:
        # Encode and decode through FlateDecode with /Predictor 12.
        flate = FlateDecode()
        params = COSDictionary()
        params.set_int("Predictor", 12)
        params.set_int("Columns", 4)
        params.set_int("Colors", 1)
        params.set_int("BitsPerComponent", 8)
        original = bytes([10, 20, 30, 40, 11, 22, 33, 44])
        encoded = io.BytesIO()
        flate.encode(io.BytesIO(original), encoded, params)
        decoded = io.BytesIO()
        flate.decode(io.BytesIO(encoded.getvalue()), decoded, params)
        assert decoded.getvalue() == original

    def test_predictor_encode_unsupported_raises(self) -> None:
        flate = FlateDecode()
        params = COSDictionary()
        params.set_int("Predictor", 7)  # not 1, 2, or 10..15
        params.set_int("Columns", 4)
        with pytest.raises(OSError):
            flate.encode(io.BytesIO(b"abcd"), io.BytesIO(), params)


class TestErrors:
    def test_truncated_stream_yields_partial_data(self) -> None:
        # A truncated /FlateDecode body does NOT raise: upstream's
        # FlateFilterDecoderStream (PDFBOX-1232) catches the
        # DataFormatException, logs a warning, and yields whatever was
        # already inflated. Verified byte-for-byte against the live
        # PDFBox 3.0.7 oracle (see test_filter_decode_oracle.py): for this
        # exact input PDFBox emits 10 bytes — the leading decoded prefix.
        original = b"some data" * 100
        encoded = zlib.compress(original)
        truncated = encoded[: len(encoded) // 2]
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(truncated), out, None)
        decoded = out.getvalue()
        # Partial, not empty, and a genuine prefix of the original payload.
        assert 0 < len(decoded) < len(original)
        assert original.startswith(decoded)

    def test_truncated_zlib_stream_yields_partial_data(self) -> None:
        # Dropping the final 2 bytes (the Adler-32 tail) loses only the
        # checksum, not data: upstream's nowrap Inflater ignores the
        # checksum, so the full payload still decodes. PDFBox yields all
        # 900 bytes here (oracle-verified); the old strict zlib.decompress
        # raised an "incomplete/truncated" Error -5.
        original = b"some data" * 100
        encoded = zlib.compress(original)
        truncated = encoded[:-2]
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(truncated), out, None)
        assert out.getvalue() == original

    def test_garbage_input_yields_empty(self) -> None:
        # Non-deflate garbage: the decoder stream fails on the first block
        # and yields zero bytes (it does not raise). Matches PDFBox, which
        # logs a warning and emits an empty stream (oracle-verified).
        flate = FlateDecode()
        out = io.BytesIO()
        flate.decode(io.BytesIO(b"not zlib at all"), out, None)
        assert out.getvalue() == b""

    def test_undefined_predictor_passes_through(self) -> None:
        # Predictor numbers other than 1, 2, and 10..15 are undefined, but
        # PDFBox does NOT raise on them: ``Predictor.wrapPredictor`` builds a
        # ``PredictorOutputStream`` for any predictor > 1, and
        # ``decodePredictorRow``'s switch hits ``default: break`` for an
        # unhandled value — the row is written through unchanged. Verified
        # against Apache PDFBox 3.0.7 (wave 1543); the former one-shot
        # ``unpredict`` raised here, a divergence now fixed.
        compressed = zlib.compress(b"abcd")
        params = COSDictionary()
        params.set_int("Predictor", 7)
        out = io.BytesIO()
        FlateDecode().decode(io.BytesIO(compressed), out, params)
        assert out.getvalue() == b"abcd"


class TestFilterFactoryIntegration:
    def test_long_name_registered(self) -> None:
        assert FilterFactory.is_registered("FlateDecode")

    def test_short_name_resolves(self) -> None:
        assert FilterFactory.is_registered("Fl")
        assert FilterFactory.get("Fl") is FilterFactory.get("FlateDecode")

    def test_factory_returns_flate_decode_instance(self) -> None:
        assert isinstance(FilterFactory.get("FlateDecode"), FlateDecode)


class TestCompressionLevel:
    """Exercises ``Filter.get_compression_level`` + ``SYSPROP_DEFLATELEVEL``.

    Mirrors PDFBox's ``Filter#getCompressionLevel`` which reads the
    ``org.apache.pdfbox.filter.deflatelevel`` system property and clamps
    to ``-1..9``. The Python port reads it from ``os.environ``.
    """

    def test_sysprop_constant_value(self) -> None:
        from pypdfbox.filter import Filter
        assert Filter.SYSPROP_DEFLATELEVEL == "org.apache.pdfbox.filter.deflatelevel"

    def test_default_is_minus_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pypdfbox.filter import Filter
        monkeypatch.delenv(Filter.SYSPROP_DEFLATELEVEL, raising=False)
        assert Filter.get_compression_level() == -1

    def test_explicit_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pypdfbox.filter import Filter
        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "9")
        assert Filter.get_compression_level() == 9

    def test_explicit_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pypdfbox.filter import Filter
        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "0")
        assert Filter.get_compression_level() == 0

    def test_clamps_above_nine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pypdfbox.filter import Filter
        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "42")
        assert Filter.get_compression_level() == 9

    def test_clamps_below_minus_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pypdfbox.filter import Filter
        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "-50")
        assert Filter.get_compression_level() == -1

    def test_unparseable_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pypdfbox.filter import Filter
        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "not-an-int")
        assert Filter.get_compression_level() == -1

    def test_flate_encode_honors_max_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Highly repetitive input — level 9 should produce output no larger
        # than level 0 (which is store-only) and round-trip identically.
        from pypdfbox.filter import Filter
        payload = b"abc" * 4000
        flate = FlateDecode()

        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "0")
        enc_zero = io.BytesIO()
        flate.encode(io.BytesIO(payload), enc_zero, None)

        monkeypatch.setenv(Filter.SYSPROP_DEFLATELEVEL, "9")
        enc_nine = io.BytesIO()
        flate.encode(io.BytesIO(payload), enc_nine, None)

        assert len(enc_nine.getvalue()) <= len(enc_zero.getvalue())

        # Round-trip through both produces the original bytes regardless.
        for enc in (enc_zero, enc_nine):
            dec = io.BytesIO()
            flate.decode(io.BytesIO(enc.getvalue()), dec, None)
            assert dec.getvalue() == payload
