from __future__ import annotations

from tests.filter.test_lzw_decode import _png_up_encode


def test_png_up_encode_pads_partial_final_row() -> None:
    encoded = _png_up_encode(b"ABCDE", columns=4)

    assert encoded == b"\x02ABCD\x02\x04\xbe\xbd\xbc"
