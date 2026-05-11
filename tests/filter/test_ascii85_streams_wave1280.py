"""Tests for :class:`ASCII85InputStream` and :class:`ASCII85OutputStream`."""

from __future__ import annotations

import io

import pytest

from pypdfbox.filter import ASCII85InputStream, ASCII85OutputStream


def _roundtrip(raw: bytes) -> bytes:
    sink = io.BytesIO()
    enc = ASCII85OutputStream(sink)
    enc.write(raw)
    enc.flush()
    return sink.getvalue()


def _decode(payload: bytes) -> bytes:
    dec = ASCII85InputStream(io.BytesIO(payload))
    return dec.read()


class TestASCII85OutputStream:
    def test_writes_terminator(self) -> None:
        enc = _roundtrip(b"x")
        assert enc.endswith(b"~>\n")

    def test_empty_input_writes_only_terminator(self) -> None:
        sink = io.BytesIO()
        enc = ASCII85OutputStream(sink)
        enc.flush()
        assert sink.getvalue() == b""  # no payload, no flushed bytes
        del enc  # keep reference until after we read

    def test_terminator_setter(self) -> None:
        sink = io.BytesIO()
        enc = ASCII85OutputStream(sink)
        enc.set_terminator("|")
        assert enc.get_terminator() == "|"
        enc.write(b"x")
        enc.flush()
        assert b"|>" in sink.getvalue()

    def test_terminator_rejects_z(self) -> None:
        enc = ASCII85OutputStream(io.BytesIO())
        with pytest.raises(ValueError):
            enc.set_terminator("z")

    def test_terminator_rejects_out_of_range(self) -> None:
        enc = ASCII85OutputStream(io.BytesIO())
        with pytest.raises(ValueError):
            enc.set_terminator(64)

    def test_line_length_getter_setter(self) -> None:
        enc = ASCII85OutputStream(io.BytesIO())
        assert enc.get_line_length() == 72
        enc.set_line_length(10)
        assert enc.get_line_length() == 10

    def test_line_break_inserted(self) -> None:
        sink = io.BytesIO()
        enc = ASCII85OutputStream(sink)
        enc.set_line_length(5)
        enc.write(b"abcdefghijklmnop")
        enc.flush()
        # Body should contain at least one newline.
        body = sink.getvalue().rstrip(b"~>\n")
        assert b"\n" in body


class TestASCII85InputStream:
    def test_decode_with_terminator(self) -> None:
        raw = b"Man is distinguished, not only by his reason, but by this"
        enc = _roundtrip(raw)
        assert _decode(enc) == raw

    def test_decode_without_terminator(self) -> None:
        # Missing ~>; we tolerate it.
        raw = b"hello"
        enc = _roundtrip(raw).rstrip(b"\n").rstrip(b">").rstrip(b"~")
        assert _decode(enc) == raw

    def test_decode_z_shorthand(self) -> None:
        # 4 zero bytes encode as 'z'.
        payload = b"z~>"
        assert _decode(payload) == b"\x00\x00\x00\x00"

    def test_decode_handles_whitespace(self) -> None:
        # Newlines / spaces inside the body are skipped.
        raw = b"Hello, world!"
        enc = _roundtrip(raw)
        # Sprinkle whitespace
        munged = enc[:5] + b"\n" + enc[5:8] + b" " + enc[8:]
        assert _decode(munged) == raw

    def test_invalid_bytes_raise(self) -> None:
        # Garbage outside the printable range triggers ValueError → OSError.
        with pytest.raises(OSError):
            _decode(b"!!\xff\xff\xff~>")

    def test_mark_supported_false(self) -> None:
        s = ASCII85InputStream(io.BytesIO(b"~>"))
        assert s.mark_supported() is False

    def test_reset_raises(self) -> None:
        s = ASCII85InputStream(io.BytesIO(b"~>"))
        with pytest.raises(OSError):
            s.reset()

    def test_skip_returns_zero(self) -> None:
        s = ASCII85InputStream(io.BytesIO(b"~>"))
        assert s.skip(10) == 0

    def test_available_returns_zero(self) -> None:
        s = ASCII85InputStream(io.BytesIO(b"~>"))
        assert s.available() == 0


class TestRoundTrip:
    @pytest.mark.parametrize(
        "raw",
        [
            b"",
            b"a",
            b"ab",
            b"abc",
            b"abcd",
            b"abcde",
            b"\x00\x00\x00\x00" * 3,
            bytes(range(256)),
        ],
    )
    def test_roundtrip(self, raw: bytes) -> None:
        if not raw:
            # Empty: no encoded bytes, decoder yields b"".
            assert _decode(b"~>") == b""
            return
        assert _decode(_roundtrip(raw)) == raw
