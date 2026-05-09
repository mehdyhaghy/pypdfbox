from __future__ import annotations

from tests.filter.test_filter_remaining_wave738 import _decode_ascii85


def test_decode_ascii85_helper_returns_decoded_bytes() -> None:
    assert _decode_ascii85(b"z~>") == b"\x00\x00\x00\x00"
