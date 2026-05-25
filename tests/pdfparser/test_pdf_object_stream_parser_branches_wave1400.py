"""Branch coverage for :class:`PDFObjectStreamParser` — wave 1400.

Closes residual partial branches in
``pypdfbox/pdfparser/pdf_object_stream_parser.py``:

* ``parse_object`` skip-to-first branch when ``_first_object == 0``
  (59 → 61).
* ``parse_object`` ``set_direct`` only invoked on non-None resolved
  object (63 → 66).
* ``parse_all_objects`` same set_direct guard (104 → 106).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDocument,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdfparser import PDFObjectStreamParser
from pypdfbox.pdfparser.base_parser import BaseParser


@pytest.fixture
def patched_read_long(monkeypatch: pytest.MonkeyPatch) -> None:
    """Carry-forward from wave 1316 — no-op; read_long already skips
    whitespace upstream-faithfully."""
    original = BaseParser.read_long

    def _patched(self: BaseParser) -> int:
        self.skip_whitespace()
        return original(self)

    monkeypatch.setattr(BaseParser, "read_long", _patched)


def _make_stream(payload: bytes, *, n: int, first: int) -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    out = stream.create_raw_output_stream()
    try:
        out.write(payload)
    finally:
        out.close()
    return stream


# ----------------------------------------------------------------------
# parse_object with /First == 0 → skip the seek-to-first guard
# ----------------------------------------------------------------------


def test_parse_object_first_zero_skips_initial_seek(
    patched_read_long: None,  # noqa: ARG001
) -> None:
    """When ``/First == 0`` the skip branch
    ``if self._first_object > 0 and current_position < self._first_object``
    is False — exercises the (59 → 61) skipped path."""
    # Empty header (n=0), /First=0; parse_object returns None without
    # entering the seek-to-first arm.
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.parse_object(1)
    assert result is None


def test_parse_object_seeks_to_first_when_cursor_short_of_it(
    patched_read_long: None,  # noqa: ARG001
) -> None:
    """When ``/First > 0`` AND the cursor (after the offset-table read)
    sits before ``/First`` — i.e., header is short and padded — the
    parser must seek forward to ``/First`` before reading the body.

    Closes the *True* side of branch (59 → 60)."""
    # Header '1 0 ' (4 bytes) declares one object at offset 0; /First=20
    # places real body after 16 extra bytes of padding. The body itself
    # is a name '/A' at offset 20.
    payload = b"1 0 " + b" " * 16 + b"/A "
    stream = _make_stream(payload, n=1, first=20)
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.parse_object(1)
    # The seek-to-first happened; the body '/A' parsed correctly.
    assert str(result) == "/A"


def test_parse_object_no_pre_seek_when_cursor_already_at_first(
    patched_read_long: None,  # noqa: ARG001
) -> None:
    """When the cursor is already at /First after the offset-table read
    (header is exactly /First bytes long), the condition
    ``current_position < self._first_object`` is False and the parser
    does NOT seek again before parse_dir_object.

    Closes the *False* side of branch (59 → 61)."""
    # Header '1 0 ' (4 bytes) declares one object at offset 0; /First=4
    # means the body starts immediately after the header — cursor lands
    # at /First naturally.
    payload = b"1 0 /A "
    stream = _make_stream(payload, n=1, first=4)
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.parse_object(1)
    assert str(result) == "/A"


# ----------------------------------------------------------------------
# parse_object: set_direct skipped when parse_dir_object returns None
# ----------------------------------------------------------------------


def test_parse_object_skip_set_direct_when_parse_returns_none(
    patched_read_long: None,  # noqa: ARG001
) -> None:
    """When the body at the computed offset is *empty* — ``parse_dir_object``
    returns ``None`` and ``set_direct(False)`` is skipped.

    Closes branch (63 → 66)."""
    # Header has one entry pointing at offset 0 in the body; body is empty
    # so parse_dir_object returns None.
    # Header '1 0 ' is 4 bytes long; /First = 4, body = b"" (0 bytes).
    stream = _make_stream(b"1 0 ", n=1, first=4)
    parser = PDFObjectStreamParser(stream, COSDocument())
    # Must not raise — None set_direct skip is the closed branch.
    result = parser.parse_object(1)
    assert result is None


# ----------------------------------------------------------------------
# parse_all_objects: set_direct skipped when parse_dir_object returns None
# ----------------------------------------------------------------------


def test_parse_all_objects_skip_set_direct_when_parse_returns_none(
    patched_read_long: None,  # noqa: ARG001
) -> None:
    """When ``parse_dir_object`` returns ``None`` for an entry, the
    walker stores ``None`` in the result dict without calling
    ``set_direct(False)``.

    Closes branch (104 → 106)."""
    # Same shape as the single-object test but exercised through
    # parse_all_objects.
    stream = _make_stream(b"1 0 ", n=1, first=4)
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.parse_all_objects()
    # The walker still records the key, with value None.
    assert len(result) == 1
    assert next(iter(result.values())) is None
