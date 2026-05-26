from __future__ import annotations

import io

import pytest

from pypdfbox.filter import ASCII85Decode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_ascii85_wave327_skips_lf_cr_space_whitespace() -> None:
    # PDFBox's ASCII85InputStream treats ONLY LF, CR and SPACE as ignorable
    # whitespace (verified against the live oracle, wave 1412). "9jqo" is
    # the ASCII85 encoding of b"Man"; sprinkling those three flavours is a
    # no-op.
    assert _decode(b"9 j\nq\ro~>") == b"Man"


@pytest.mark.parametrize(
    "ws",
    [b"\t", b"\x00", b"\x0c", b"\x0b"],
    ids=["tab", "nul", "ff", "vtab"],
)
def test_ascii85_wave327_rejects_non_pdfbox_whitespace(ws: bytes) -> None:
    # TAB, NUL, FF and VT are NOT ASCII85 whitespace in PDFBox — they fall
    # below b'!' and trip the "Invalid data in Ascii85 stream" range check.
    with pytest.raises(OSError, match="Invalid data"):
        _decode(b"9j" + ws + b"qo~>")
