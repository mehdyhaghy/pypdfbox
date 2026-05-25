"""Wave 1403 branch round-out for ``PDFObjectStreamParser.parse_object``.

Closes 59->61 — the ``if self._first_object > 0 and current_position <
self._first_object`` False arm: after the offset table is read, the source
cursor has already advanced to (or past) ``/First``, so the realign-skip is
not needed and execution falls straight to ``self._src.skip(offset)``.

Reaching the False arm needs ``current_position >= first_object`` *after* the
header table is read while still finding the requested object number in the
table. ``_private_read_object_numbers`` stops once the cursor reaches
``first_object - 1``, so the cursor ends up a byte or two past a small
``/First``. With ``/First == 2`` the single header pair ``"5 0 "`` leaves the
cursor at position 3 (>= 2), making the guard False. (Wave 1402/1403 earlier
attempts used ``/First == 4``; the cursor then sat at 3 < 4 and took the
*True* realign arm instead, leaving 59->61 open — which the full-suite
coverage run surfaced.)
"""

from __future__ import annotations

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSStream
from pypdfbox.pdfparser import PDFObjectStreamParser


def _object_stream(*, n: int, first: int, payload: bytes) -> COSStream:
    s = COSStream()
    s.set_item(COSName.N, COSInteger.get(n))
    s.set_item(COSName.FIRST, COSInteger.get(first))
    out = s.create_raw_output_stream()
    try:
        out.write(payload)
    finally:
        out.close()
    return s


def test_parse_object_cursor_past_first_skips_realign() -> None:
    """Closes 59->61: with ``/First == 2`` the header pair ``"5 0 "`` advances
    the cursor to position 3 (>= first_object 2), so the realign-skip guard is
    False and parsing proceeds straight to ``skip(offset)`` and
    ``parse_dir_object`` — which reads the trailing ``/A`` name.
    """
    payload = b"5 0 /A"
    stream = _object_stream(n=2, first=2, payload=payload)
    parser = PDFObjectStreamParser(stream, COSDocument())
    obj = parser.parse_object(5)
    # The False arm executed (no early exception) and parsing continued past
    # line 61, yielding the COSName /A at the resolved offset.
    assert isinstance(obj, COSName)
    assert obj.get_name() == "A"
