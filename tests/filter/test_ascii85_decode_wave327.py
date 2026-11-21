import io

import pytest

from pypdfbox.filter import ASCII85Decode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_ascii85_wave327_skips_lf_cr_space_whitespace() -> None:
    # PDFBox's ASCII85InputStream treats the PDF white-space set (NUL, TAB,
    # LF, FF, CR, SPACE) as ignorable (PDFBOX-6330). "9jqo" is the ASCII85
    # encoding of b"Man"; sprinkling those flavours is a no-op.
    assert _decode(b"9 j\nq\ro~>") == b"Man"
    assert _decode(b"9\tj\x00q\x0co~>") == b"Man"


@pytest.mark.parametrize(
    "ws",
    [b"\x0b"],
    ids=["vtab"],
)
def test_ascii85_wave327_rejects_non_pdfbox_whitespace(ws: bytes) -> None:
    # VT is NOT PDF whitespace: it falls below b'!' and trips the
    # "Invalid data in Ascii85 stream" range check.
    with pytest.raises(OSError, match="Invalid data"):
        _decode(b"9j" + ws + b"qo~>")
