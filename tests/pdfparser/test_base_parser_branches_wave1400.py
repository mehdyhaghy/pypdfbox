"""Branch coverage for :class:`BaseParser` — wave 1400.

Closes residual partial branches in ``pypdfbox/pdfparser/base_parser.py``:

* ``unread_byte`` at file position 0 (no rewind possible).
* ``skip_eol`` invoked when the next byte is neither CR nor LF.
* ``_read_until_end_of_cos_dictionary`` recovery: ``end`` matched but
  followed by neither ``stream`` nor ``obj``.
* ``parse_cos_array`` corruption recovery: trailing ``COSInteger`` is
  not followed by another ``COSInteger`` (malformed indirect reference).
"""

from __future__ import annotations

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser


def _parser(payload: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(payload))


# ----------------------------------------------------------------------
# unread_byte at offset 0
# ----------------------------------------------------------------------


def test_unread_byte_at_position_zero_is_a_noop() -> None:
    """At file position 0 there is nowhere to rewind to. ``unread_byte``
    must check ``get_position() > 0`` and silently return.

    Closes branch (161 → 160) in base_parser."""
    p = _parser(b"abc")
    assert p.position == 0
    # No exception — should silently return.
    p.unread_byte()
    assert p.position == 0
    # Consuming a byte then unread *does* rewind.
    p.read_byte()
    assert p.position == 1
    p.unread_byte()
    assert p.position == 0


# ----------------------------------------------------------------------
# skip_eol with non-EOL next byte
# ----------------------------------------------------------------------


def test_skip_eol_no_op_when_next_byte_is_not_eol() -> None:
    """``skip_eol`` is intended to consume an optional EOL marker. When
    the next byte is neither CR nor LF the method must not move the
    cursor.

    Closes branch (311 → 304) in base_parser."""
    p = _parser(b"X\nrest")
    assert p.position == 0
    # 'X' is not an EOL — cursor should remain at 0.
    p.skip_eol()
    assert p.position == 0
    # Advance past the 'X'; next byte is LF → skip_eol consumes it.
    p.read_byte()
    assert p.position == 1
    p.skip_eol()
    assert p.position == 2


# ----------------------------------------------------------------------
# Dictionary recovery: 'end' followed by neither 'stream' nor 'obj'
# ----------------------------------------------------------------------


def test_read_until_end_of_cos_dictionary_end_keyword_false_match() -> None:
    """The recovery helper byte-walks looking for ``endstream`` or
    ``endobj`` markers. An ``end`` keyword followed by something else
    (e.g. ``endless``) must NOT exit the loop — the parser keeps
    scanning for the real terminator.

    Closes branches (1123 → 1141) and (1139 → 1141) in base_parser."""
    # Build a payload where 'end' appears mid-stream with a non-matching
    # suffix, and the real '>>' terminator follows.
    payload = b"endless garbage >>"
    p = _parser(payload)
    result = p.read_until_end_of_cos_dictionary()
    assert result is False
    # Cursor should be positioned just before the closing '>'.
    # The helper rewinds one byte after the terminating '>'.
    remaining = p._src.read()  # noqa: SLF001
    assert remaining == 0x3E  # '>'


def test_read_until_end_of_cos_dictionary_endobj_terminates() -> None:
    """An actual ``endobj`` keyword should terminate the scan with
    ``True``. Confirms the positive path through the same branches we
    exercise in the false-match case above."""
    payload = b"trailing junk endobj"
    p = _parser(payload)
    result = p.read_until_end_of_cos_dictionary()
    assert result is True


def test_read_until_end_of_cos_dictionary_endstream_terminates() -> None:
    """``endstream`` is the other accepted terminator — exercise the
    twin branch in the same helper."""
    payload = b"oops endstream"
    p = _parser(payload)
    result = p.read_until_end_of_cos_dictionary()
    assert result is True


def test_read_until_end_of_cos_dictionary_eof_returns_true() -> None:
    """EOF without finding ``/`` or ``>`` returns ``True`` so the caller
    stops parsing."""
    p = _parser(b"only-words")
    result = p.read_until_end_of_cos_dictionary()
    assert result is True


def test_read_until_end_of_cos_dictionary_en_not_d_continues_scan() -> None:
    """When the helper sees 'e' 'n' but the next byte is NOT 'd' (e.g.
    'enable'), it must NOT terminate — keep scanning for the real
    ``>>`` / ``endobj`` / ``endstream``.

    Closes branch (1123 → 1141) in base_parser."""
    # 'enable' — 'en' followed by 'a', not 'd'. Should continue scanning.
    p = _parser(b"enable stuff >>")
    result = p.read_until_end_of_cos_dictionary()
    assert result is False  # '>' terminator was found before EOF


# ----------------------------------------------------------------------
# parse_cos_array with a malformed `<int> R` reference (gen but no num)
# ----------------------------------------------------------------------


def test_parse_cos_array_corruption_with_only_one_trailing_int_before_R() -> None:
    """An array like ``[5 R]`` has only one int preceding the ``R`` —
    BaseParser treats this as corruption: after removing the trailing
    int the second ``len(po) > 0`` check is False and ``pbo`` stays
    None, triggering the corruption-recovery log.

    Closes branch (966 → 979) in base_parser. We exercise BaseParser
    directly (NOT COSParser, which raises on bare ``R``)."""
    # Use a synthetic input where the 'R' returns COSObject (BaseParser
    # path) and only one preceding integer exists.
    p = _parser(b"[5 R]")
    result = p.parse_cos_array()
    # The element became None / corrupt, but parse_cos_array still
    # returns the partially-populated array without raising.
    assert result is not None


def test_parse_cos_array_corruption_with_endobj_after_R() -> None:
    """When the corruption recovery reads an end-of-object marker
    (``endobj``) it returns the array so far. Also covers the [5 R]
    corruption path."""
    p = _parser(b"[5 R endobj")
    result = p.parse_cos_array()
    assert result is not None
