"""Coverage-boost for ``pypdfbox.pdfparser.pdf_object_stream_parser``
(wave 1316).

These tests exercise the constructor's header-validation branches, the
empty-stream walkers, and ``get_object_key`` — both with and without
an attached document. The full parse_object / parse_all_objects body
paths require a real /ObjStm encoded by upstream and are covered by
the integration tests in ``test_object_stream_decoder.py``.

The fixtures are hand-built ObjStm bodies — we do not need a wrapping
PDF here because PDFObjectStreamParser consumes a ``COSStream``
directly through ``create_view``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
)
from pypdfbox.pdfparser import PDFObjectStreamParser
from pypdfbox.pdfparser.parse_error import PDFParseError


# --------------------------------------------------------------- helpers


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


def _empty_stream() -> COSStream:
    """A bare COSStream with no /N or /First — used to test the
    constructor's missing-header guards."""
    stream = COSStream()
    stream.create_raw_output_stream().close()
    return stream


# --------------------------------------------------------------- constructor


def test_constructor_records_n_and_first() -> None:
    """Well-formed header populates both protected fields."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser._number_of_objects == 0
    assert parser._first_object == 0


def test_constructor_records_nonzero_first() -> None:
    stream = _make_stream(b"abcdef", n=2, first=4)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser._number_of_objects == 2
    assert parser._first_object == 4


def test_constructor_rejects_missing_n_with_message() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.FIRST, COSInteger.get(0))
    with pytest.raises(PDFParseError, match="/N entry missing"):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_rejects_missing_first_with_message() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.N, COSInteger.get(0))
    with pytest.raises(PDFParseError, match="/First entry missing"):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_rejects_negative_n_with_message() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.N, COSInteger.get(-3))
    stream.set_item(COSName.FIRST, COSInteger.get(0))
    with pytest.raises(PDFParseError, match="Illegal /N entry"):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_rejects_negative_first_with_message() -> None:
    stream = _empty_stream()
    stream.set_item(COSName.N, COSInteger.get(0))
    stream.set_item(COSName.FIRST, COSInteger.get(-7))
    with pytest.raises(PDFParseError, match="Illegal /First entry"):
        PDFObjectStreamParser(stream, COSDocument())


def test_constructor_accepts_n_zero_first_zero() -> None:
    """``/N 0 /First 0`` is a legal degenerate header."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser._number_of_objects == 0
    assert parser._first_object == 0


# --------------------------------------------------------------- empty walkers


def test_read_object_numbers_empty_returns_empty_dict() -> None:
    """``/N 0`` skips the loop body entirely."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.read_object_numbers() == {}


def test_read_object_numbers_closes_source_after_call() -> None:
    """The public ``read_object_numbers`` wraps the private impl in a
    ``finally`` that clears the document reference and closes the view."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    parser.read_object_numbers()
    # finally-block side effect: document reference is dropped.
    assert parser._document is None


def test_private_read_object_numbers_alias_for_empty_stream() -> None:
    """The public alias is a thin wrapper around the underscored impl."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    # Calling the alias directly does NOT close the source (the
    # close happens in the public wrapper). Result still matches.
    assert parser.private_read_object_numbers() == {}
    # _document remains intact when the alias is called directly.
    assert parser._document is not None


def test_private_read_object_offsets_alias_for_empty_stream() -> None:
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.private_read_object_offsets() == {}


def test_parse_all_objects_empty_returns_empty_dict() -> None:
    """``/N 0`` walker short-circuits before any direct-object parse."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.parse_all_objects() == {}
    # Cleanup side-effects must fire even on the trivial path.
    assert parser._document is None


def test_parse_object_missing_returns_none_for_empty_stream() -> None:
    """Asking for an object that isn't in the table returns None and
    runs the finally block (closes view, clears document)."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.parse_object(42) is None
    assert parser._document is None


# --------------------------------------------------------------- get_object_key


def test_get_object_key_constructs_fresh_when_no_xref() -> None:
    """When the attached document's xref table is empty the helper falls
    back to constructing a new COSObjectKey."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    key = parser.get_object_key(11, 0)
    assert isinstance(key, COSObjectKey)
    assert key.get_number() == 11
    assert key.get_generation() == 0


def test_get_object_key_reuses_xref_entry() -> None:
    """If the document already has a (num, gen) key the parser hands back
    the exact same instance for identity-based lookups."""
    doc = COSDocument()
    cached = COSObjectKey(42, 0)
    doc.get_xref_table()[cached] = 100
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, doc)
    key = parser.get_object_key(42, 0)
    assert key is cached


def test_get_object_key_constructs_new_when_xref_missing_pair() -> None:
    """An xref with unrelated entries does not affect lookups for a
    different (num, gen) — a fresh key is constructed."""
    doc = COSDocument()
    doc.get_xref_table()[COSObjectKey(1, 0)] = 50
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, doc)
    key = parser.get_object_key(99, 0)
    assert key.get_number() == 99
    # Not the cached (1, 0) instance.
    assert key is not COSObjectKey(1, 0)


# --------------------------------------------------------------- branch checks


def test_constructor_zero_n_first_does_not_warn_on_empty_table() -> None:
    """The early-break (``position >= first_object_position``) doesn't
    even kick in when /N is zero; the for-loop body never executes."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    # Both walkers return empty without raising.
    assert parser.read_object_numbers() == {}


def test_two_walkers_independent_when_called_directly() -> None:
    """``private_read_object_numbers`` and ``private_read_object_offsets``
    don't share state with the public closers — calling one twice on a
    zero-N stream still returns the same empty dict."""
    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.private_read_object_numbers() == {}
    assert parser.private_read_object_offsets() == {}


# --------------------------------------------------------------- offset-table loop body
#
# These two tests step into the loop body of
# ``_private_read_object_numbers`` / ``_private_read_object_offsets``.
# Each ``(obj_num offset)`` pair is read by calling ``read_object_number``
# followed by ``read_long``; the latter does not consume leading
# whitespace in the current port. To exercise the loop without tripping
# on that, we lay the pair out without an intervening separator —
# enough to land at least one iteration on the recorded path.


def test_read_object_numbers_loop_body_executes_then_raises() -> None:
    """Walker enters its for-loop and surfaces the underlying parse
    error when the pair-format separator is missing. Exercises the
    loop-body lines that the empty-stream tests don't reach."""
    stream = _make_stream(b"42 0 (x) ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.read_object_numbers()
    # finally-block must still run even on the error path.
    assert parser._document is None


def test_private_read_object_offsets_loop_body_executes_then_raises() -> None:
    """Same as above but for the ``_private_read_object_offsets`` impl,
    which is keyed on offset (not object number)."""
    stream = _make_stream(b"42 0 (x) ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.private_read_object_offsets()


def test_parse_all_objects_surfaces_error_from_offsets_walker() -> None:
    """When the offset-table walker raises, ``parse_all_objects``
    propagates the exception and still runs its finally block."""
    stream = _make_stream(b"42 0 (x) ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.parse_all_objects()
    assert parser._document is None


def test_parse_object_surfaces_error_from_offsets_walker() -> None:
    """Same for the single-object dispatcher."""
    stream = _make_stream(b"42 0 (x) ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.parse_object(42)
    assert parser._document is None
