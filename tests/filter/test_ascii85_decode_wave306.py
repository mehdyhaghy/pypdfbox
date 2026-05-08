from __future__ import annotations

import io

import pytest

from pypdfbox.filter import ASCII85Decode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_ascii85_rejects_single_digit_final_group_before_eod() -> None:
    with pytest.raises(OSError, match="final partial group"):
        _decode(b"!~>")


def test_ascii85_rejects_single_digit_final_group_without_eod() -> None:
    with pytest.raises(OSError, match="final partial group"):
        _decode(b"z!")


def test_ascii85_accepts_two_digit_final_group() -> None:
    assert _decode(b"!!~>") == b"\x00"
