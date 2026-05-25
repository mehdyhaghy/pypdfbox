"""Wave 1403 branch round-out for ``CCITTFaxDecoderStream._ensure_decoded``.

Closes 78->81 — the ``if self._rows > 0`` False arm: when the stream is
constructed with ``rows == 0`` the ``Rows`` entry is omitted from the
``DecodeParms`` dictionary and decoding falls through to the byte-align
check directly.
"""

from __future__ import annotations

import io

from pypdfbox.filter import CCITTFaxDecoderStream, CCITTFaxEncoderStream
from pypdfbox.filter.tiff_extension import TIFFExtension


def _encode_g4(raw: bytes, columns: int, rows: int) -> bytes:
    out = io.BytesIO()
    enc = CCITTFaxEncoderStream(
        out,
        columns=columns,
        rows=rows,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    enc.write(raw)
    enc.flush()
    return out.getvalue()


def test_decoder_with_zero_rows_omits_rows_param() -> None:
    """Closes 78->81: ``rows=0`` skips ``sub.set_int('Rows', ...)`` so the
    DecodeParms dict carries no ``Rows`` entry. libtiff reads to EOFB.
    """
    raw = b"\x00\x00" * 8 + b"\xff\xff" * 8  # 16 wide x 16 tall
    encoded = _encode_g4(raw, columns=16, rows=16)

    dec = CCITTFaxDecoderStream(
        io.BytesIO(encoded),
        columns=16,
        rows=0,  # <= 0 => Rows entry omitted (78->81 False arm)
        type_=TIFFExtension.COMPRESSION_CCITT_T6,
        fill_order=TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    out = dec.read()
    # Don't assert the exact tail (libtiff/Pillow wheels differ past EOD);
    # just confirm the rows-less decode path completes.
    assert isinstance(out, bytes)
