from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCII85Decode, RunLengthDecode


def test_ascii85_decode_reports_bytes_written_and_preserves_parameters() -> None:
    params = COSDictionary()
    out = io.BytesIO()

    result = ASCII85Decode().decode(io.BytesIO(b"9jqo~>"), out, params)

    assert out.getvalue() == b"Man"
    assert result.bytes_written == 3
    assert result.parameters is params


def test_run_length_decode_reports_literal_and_repeat_bytes_written() -> None:
    params = COSDictionary()
    out = io.BytesIO()

    result = RunLengthDecode().decode(io.BytesIO(b"\x01ab\xfdX\x80"), out, params)

    assert out.getvalue() == b"abXXXX"
    assert result.bytes_written == 6
    assert result.parameters is params


def test_run_length_decode_reports_zero_bytes_for_immediate_eod() -> None:
    out = io.BytesIO()

    result = RunLengthDecode().decode(io.BytesIO(b"\x80"), out)

    assert out.getvalue() == b""
    assert result.bytes_written == 0
