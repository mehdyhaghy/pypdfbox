"""Wave 1275 round-out: ``COSStream.write`` bulk-output helper."""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSStream


def test_write_copies_raw_body_to_target() -> None:
    payload = b"hello world"
    with COSStream() as stream:
        stream.set_raw_data(payload)
        target = io.BytesIO()
        n = stream.write(target)
    assert n == len(payload)
    assert target.getvalue() == payload


def test_write_returns_zero_when_body_empty() -> None:
    with COSStream() as stream:
        target = io.BytesIO()
        n = stream.write(target)
    assert n == 0
    assert target.getvalue() == b""


def test_write_raises_while_a_writer_is_open() -> None:
    with COSStream() as stream, stream.create_raw_output_stream() as out:
        out.write(b"abc")
        target = io.BytesIO()
        with pytest.raises(RuntimeError):
            stream.write(target)
