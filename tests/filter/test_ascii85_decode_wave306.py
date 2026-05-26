from __future__ import annotations

import io

from pypdfbox.filter import ASCII85Decode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_ascii85_single_digit_final_group_is_dropped() -> None:
    # A trailing group with only one base-85 digit cannot form even one
    # output byte. PDFBox's ASCII85InputStream silently drops it (verified
    # against the live oracle, wave 1412) rather than raising.
    assert _decode(b"!~>") == b""


def test_ascii85_z_then_single_digit_drops_the_digit() -> None:
    # 'z' expands to four zero bytes at the group boundary; the trailing
    # lone '!' digit is dropped. (EOD-terminated so behaviour is defined.)
    assert _decode(b"z!~>") == b"\x00\x00\x00\x00"


def test_ascii85_accepts_two_digit_final_group() -> None:
    assert _decode(b"!!~>") == b"\x00"
