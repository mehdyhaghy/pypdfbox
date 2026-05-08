from __future__ import annotations

import io

from pypdfbox.filter import ASCIIHexDecode


class _FlushTrackingBytesIO(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def test_decode_flushes_decoded_sink_after_write() -> None:
    out = _FlushTrackingBytesIO()

    result = ASCIIHexDecode().decode(io.BytesIO(b"414243>"), out)

    assert out.getvalue() == b"ABC"
    assert result.bytes_written == 3
    assert out.flush_count == 1


def test_encode_flushes_encoded_sink_after_eod_marker() -> None:
    out = _FlushTrackingBytesIO()

    ASCIIHexDecode().encode(io.BytesIO(b"ABC"), out)

    assert out.getvalue() == b"414243>"
    assert out.flush_count == 1
