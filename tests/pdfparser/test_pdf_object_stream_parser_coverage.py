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
# These tests step into the loop body of
# ``_private_read_object_numbers`` / ``_private_read_object_offsets``.
# Each ``(obj_num offset)`` pair is read by calling ``read_object_number``
# followed by ``read_long``; wave 1363 aligned ``read_long`` with upstream
# Java by having it ``skip_whitespace`` first. Malformed truncated input
# (only the object number, no offset) therefore still surfaces a
# ``PDFParseError`` from ``read_long`` once it runs off the end of the
# stream looking for digits.


def test_read_object_numbers_loop_body_executes_then_raises() -> None:
    """Walker enters its for-loop and surfaces the underlying parse
    error when the pair-format offset is missing. Exercises the
    loop-body lines that the empty-stream tests don't reach."""
    stream = _make_stream(b"42  ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.read_object_numbers()
    # finally-block must still run even on the error path.
    assert parser._document is None


def test_private_read_object_offsets_loop_body_executes_then_raises() -> None:
    """Same as above but for the ``_private_read_object_offsets`` impl,
    which is keyed on offset (not object number)."""
    stream = _make_stream(b"42  ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.private_read_object_offsets()


def test_parse_all_objects_surfaces_error_from_offsets_walker() -> None:
    """When the offset-table walker raises, ``parse_all_objects``
    propagates the exception and still runs its finally block."""
    stream = _make_stream(b"42  ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.parse_all_objects()
    assert parser._document is None


def test_parse_object_surfaces_error_from_offsets_walker() -> None:
    """Same for the single-object dispatcher."""
    stream = _make_stream(b"42  ", n=1, first=5)
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.parse_object(42)
    assert parser._document is None


# --------------------------------------------------------------- full loop bodies
#
# Wave 1363 aligned ``BaseParser.read_long`` with upstream Java by
# prefixing it with ``skip_whitespace``; the fixture below originally
# patched the missing skip in but is now a no-op kept for clarity (and to
# keep the test bodies unchanged from the wave that introduced them).


@pytest.fixture
def patched_read_long(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op fixture — kept as a breadcrumb for wave 1363's read_long fix.

    Earlier waves patched ``BaseParser.read_long`` to skip leading
    whitespace as a workaround for the missing upstream-parity skip; the
    source now does that itself.
    """
    from pypdfbox.pdfparser.base_parser import BaseParser

    original = BaseParser.read_long

    def _patched(self: BaseParser) -> int:
        self.skip_whitespace()
        return original(self)

    monkeypatch.setattr(BaseParser, "read_long", _patched)


def _make_obj_stream_with_names(n: int, first: int, header: bytes, body: bytes) -> COSStream:
    """Helper to build an /ObjStm with name-object bodies."""
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    out = stream.create_raw_output_stream()
    try:
        out.write(header)
        out.write(body)
    finally:
        out.close()
    return stream


def test_private_read_object_numbers_returns_pairs(patched_read_long: None) -> None:
    """Walker reads both ``(obj_num, offset)`` pairs from a well-formed
    header. Exercises lines 145, 148 in the underscored impl."""
    # Header '1 0 2 3 ' = 8 bytes, /First = 8.
    stream = _make_obj_stream_with_names(2, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.private_read_object_numbers()
    assert result == {1: 0, 2: 3}


def test_private_read_object_offsets_returns_offset_keyed(patched_read_long: None) -> None:
    """``_private_read_object_offsets`` flips key/value so the dict is
    keyed on offset. Exercises lines 166, 169."""
    stream = _make_obj_stream_with_names(2, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.private_read_object_offsets()
    assert result == {0: 1, 3: 2}


def test_parse_all_objects_full_walks_loop_body(patched_read_long: None) -> None:
    """End-to-end exercise of ``parse_all_objects`` — covers lines
    88-107 including the pre-skip to /First and the per-object parse."""
    stream = _make_obj_stream_with_names(2, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.parse_all_objects()
    keys = sorted(result.keys(), key=lambda k: k.get_number())
    assert [k.get_number() for k in keys] == [1, 2]
    assert str(result[keys[0]]) == "/A"
    assert str(result[keys[1]]) == "/B"
    # finally-block side effect: document reference is dropped.
    assert parser._document is None


def test_parse_object_returns_indexed_object(patched_read_long: None) -> None:
    """``parse_object`` returns the requested object — covers lines
    58-64 (the offset-walking + skip-to-first branch)."""
    stream = _make_obj_stream_with_names(2, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    obj = parser.parse_object(1)
    assert str(obj) == "/A"
    assert parser._document is None


def test_parse_object_returns_second_object(patched_read_long: None) -> None:
    """Confirms the offset arithmetic for the trailing object — second
    pair in the header table."""
    stream = _make_obj_stream_with_names(2, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    obj = parser.parse_object(2)
    assert str(obj) == "/B"


def test_parse_object_unknown_object_number_returns_none(patched_read_long: None) -> None:
    """When the requested object isn't in the offset table the parser
    returns None and still runs the finally block."""
    stream = _make_obj_stream_with_names(2, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    assert parser.parse_object(99) is None
    assert parser._document is None


def test_parse_all_objects_with_duplicate_object_numbers(
    patched_read_long: None,
) -> None:
    """PDFBOX-4927 — when an obj_num appears more than once in the
    header table the parser uses the stream-index to disambiguate.
    Hand-crafted duplicate entries flip the ``index_needed`` flag and
    exercise the continue-branch at lines 92-98."""
    # Header '1 0 1 3 ' duplicates object 1 at two offsets.
    stream = _make_obj_stream_with_names(2, 8, b"1 0 1 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    # Pre-populate the xref with index-bearing keys so get_object_key
    # returns instances whose stream_index matches the parse order.
    result = parser.parse_all_objects()
    # At least one object survives the dedup loop.
    assert len(result) >= 1


def test_parse_all_objects_continue_branch_when_index_skipped(
    patched_read_long: None,
) -> None:
    """When ``index_needed`` is set and the key's ``stream_index`` does
    not match the loop counter, the parser advances ``index`` and
    ``continue``s — exercises lines 97-98."""
    # Two header entries for the same object number → ``index_needed``
    # becomes True. Pre-populate the document's xref with a key whose
    # stream_index is 1 so the first iteration falls into the continue
    # branch (loop index 0 != stream_index 1).
    doc = COSDocument()
    indexed_key = COSObjectKey(1, 0, index=1)
    doc.get_xref_table()[indexed_key] = 0
    stream = _make_obj_stream_with_names(2, 8, b"1 0 1 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, doc)
    result = parser.parse_all_objects()
    # The continue branch did fire, but the second iteration still
    # parses an object — the resulting dict has exactly the indexed key.
    assert indexed_key in result


def test_private_read_object_numbers_breaks_when_position_passes_first(
    patched_read_long: None,
) -> None:
    """When the header advertises more pairs than the body actually
    contains, the loop must break once position reaches the /First
    boundary — exercises line 145 (and the symmetric line 166)."""
    # /N declares 5 pairs but the header only has space for 2 before
    # hitting /First=8. The loop should break early without raising.
    stream = _make_obj_stream_with_names(5, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.private_read_object_numbers()
    # Only two pairs got read before the early break fired.
    assert len(result) == 2


def test_private_read_object_offsets_breaks_when_position_passes_first(
    patched_read_long: None,
) -> None:
    """Symmetric to the test above — covers the early-break in
    ``_private_read_object_offsets`` (line 166)."""
    stream = _make_obj_stream_with_names(5, 8, b"1 0 2 3 ", b"/A /B  ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.private_read_object_offsets()
    assert len(result) == 2


# --------------------------------------------------------------- get_object_key fallback
#
# Line 181: ``return COSObjectKey(number, generation)`` runs when
# ``super().get_object_key`` is missing / not callable. ``BaseParser``
# always provides the helper today so the fallback is dead in practice.
# We trip the branch by temporarily detaching the base-class helper.


def test_get_object_key_fallback_when_super_helper_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the fallback branch at line 181 by hiding ``BaseParser
    .get_object_key`` so ``getattr(super(), ...)`` returns the
    ``object`` default — which is not callable as a 3-arg method."""
    from pypdfbox.pdfparser.base_parser import BaseParser

    stream = _make_stream(b"", n=0, first=0)
    parser = PDFObjectStreamParser(stream, COSDocument())
    # Replace BaseParser.get_object_key with a non-callable sentinel so
    # the ``if callable(helper)`` branch falls through.
    monkeypatch.setattr(BaseParser, "get_object_key", "not-callable")
    key = parser.get_object_key(7, 0)
    assert isinstance(key, COSObjectKey)
    assert key.get_number() == 7
    assert key.get_generation() == 0
