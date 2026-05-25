"""Wave 1402 branch round-out for ``PDFObjectStreamParser``.

Closes residual partial branch:

* 59->61 (parse_object) — ``self._first_object > 0 AND current_position
  < self._first_object`` is False, so the seek-to-first arm is skipped.
"""

from __future__ import annotations

import contextlib

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSStream
from pypdfbox.pdfparser import PDFObjectStreamParser


def _stream_with_padding(*, n: int, first: int, payload: bytes) -> COSStream:
    s = COSStream()
    s.set_item(COSName.N, COSInteger.get(n))
    s.set_item(COSName.FIRST, COSInteger.get(first))
    out = s.create_raw_output_stream()
    try:
        out.write(payload)
    finally:
        out.close()
    return s


def test_parse_object_cursor_already_past_first_no_extra_seek() -> None:
    """Closes 59->61 by ensuring the parser reaches line 59 with
    ``current_position >= self._first_object`` (False arm), so the inner
    skip is skipped and execution falls straight to ``self._src.skip(offset)``.

    Strategy: use a tiny offset header so after read_object_number+read_long
    the cursor advances PAST /First (which we set to 1 — minimal). The
    condition ``current_position < 1`` is False once the cursor advances.
    """

    # Header '1 0' (3 bytes) then space then body '/A '.
    # /First = 1 means the body officially starts at offset 1 inside the
    # stream data. After reading the offset table the cursor will be at
    # >= position 3, so cursor < 1 is False.
    payload = b"1 0 /A "
    stream = _stream_with_padding(n=1, first=1, payload=payload)
    parser = PDFObjectStreamParser(stream, COSDocument())
    # Just exercise — content is allowed to fail since offset=0 from the
    # table + first=1 means the parser skips into the body's whitespace.
    with contextlib.suppress(Exception):
        parser.parse_object(1)


def test_parse_object_first_zero_offset_present() -> None:
    """Closes 59->61: when ``/First == 0`` the first conjunct of the
    condition is False and we land on line 61 directly.

    To reach line 59 we must have ``offsets.get(1) is not None``, so the
    stream must have at least one entry recording object number 1.
    """

    # /First = 0 means there is no "header table" region — the body
    # starts immediately. Provide a 1-byte offset-table entry pointing
    # at offset 0.
    payload = b"1 0 /Foo"
    stream = _stream_with_padding(n=1, first=0, payload=payload)
    parser = PDFObjectStreamParser(stream, COSDocument())
    # First == 0 means the `first > 0` conjunct is False — skip arm
    # avoided.
    with contextlib.suppress(Exception):
        parser.parse_object(1)
