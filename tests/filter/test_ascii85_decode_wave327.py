from __future__ import annotations

import io

import pytest

from pypdfbox.filter import ASCII85Decode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_ascii85_wave327_accepts_pdf_whitespace_bytes() -> None:
    assert _decode(b"\x009\tj\nq\x0co\r~>") == b"Man"


def test_ascii85_wave327_rejects_vertical_tab_as_non_pdf_whitespace() -> None:
    with pytest.raises(OSError, match="out of range"):
        _decode(b"9j\x0bqo~>")
