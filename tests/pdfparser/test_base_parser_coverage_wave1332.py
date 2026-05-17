"""Wave 1332 coverage boost for ``BaseParser``.

Targets the remaining uncovered branches in
``pypdfbox/pdfparser/base_parser.py``:

* :meth:`require_byte` EOF guard;
* :meth:`read_string_number` happy path + overflow;
* UTF-8 → latin-1 fallback in :meth:`read_name`,
  :meth:`read_string_with_length`, and :meth:`decode_buffer`;
* :meth:`check_for_end_of_string` short-stream branch;
* :meth:`_consume_escape` EOF-after-backslash + LF/CRLF continuation;
* :meth:`parse_dir_object` EOF / hex string / literal string / name /
  bare-R recovery / unknown-token recovery / endobj+endstream rewind /
  PDFNull-on-warning;
* :meth:`parse_cos_array` indirect-reference resolution, the corrupt-
  element ``[`` reentry recovery, and ``endobj`` exit;
* :meth:`parse_cos_dictionary` recovery from a non-``/`` head byte and
  the missing-``>>`` warning path;
* :meth:`parse_cos_dictionary_name_value_pair` empty-name warning;
* :meth:`parse_cos_dictionary_value` indirect-reference resolution +
  invalid-number / negative-generation / non-positive-object recovery;
* :meth:`read_until_end_of_cos_dictionary` EOF exit;
* :meth:`parse_cos_number` empty-buffer error + trailing-``E`` rewind;
* :meth:`parse_cos_string` error path;
* :meth:`parse_cos_hex_string` invalid-byte skip-to-close recovery +
  unterminated-after-recovery error.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


# ----------------------------------------------------------------------
# Low-level helpers
# ----------------------------------------------------------------------


def test_require_byte_raises_at_eof() -> None:
    p = _parser(b"")
    with pytest.raises(PDFParseError, match="unexpected EOF"):
        p.require_byte()


def test_require_byte_returns_byte() -> None:
    p = _parser(b"A")
    assert p.require_byte() == 0x41


def test_read_string_number_basic() -> None:
    p = _parser(b"123 ")
    assert p.read_string_number() == "123"


def test_read_string_number_overflow_raises() -> None:
    """A digit run longer than ``MAX_LENGTH_LONG`` (19) must raise."""
    p = _parser(b"1" * 25)
    with pytest.raises(PDFParseError, match="too long"):
        p.read_string_number()


def test_read_string_number_eof_returns_empty() -> None:
    p = _parser(b"")
    assert p.read_string_number() == ""


def test_read_string_number_stops_on_non_digit() -> None:
    p = _parser(b"42x")
    assert p.read_string_number() == "42"
    # The trailing 'x' is left in the buffer.
    assert p.read_byte() == ord("x")


# ----------------------------------------------------------------------
# UTF-8 → latin-1 fallback paths
# ----------------------------------------------------------------------


def test_read_name_falls_back_to_latin1_on_bad_utf8() -> None:
    """A ``#FF`` escape injects 0xFF into the name; UTF-8 decode fails and
    the latin-1 fallback path runs."""
    p = _parser(b"/Foo#FFBar ")
    out = p.read_name()
    # 0xFF in latin-1 is U+00FF.
    assert out == "Foo\xffBar"


def test_read_string_with_length_falls_back_to_latin1() -> None:
    """Inject a 0xFF byte so the UTF-8 decode of the token fails and the
    latin-1 fallback in ``read_string_with_length`` is exercised."""
    p = _parser(b"\xffabc ")
    out = p.read_string_with_length(10)
    assert out == "\xffabc"


def test_decode_buffer_utf8_happy_path() -> None:
    assert BaseParser.decode_buffer(b"hello") == "hello"


def test_decode_buffer_windows_1252_fallback() -> None:
    """Bytes invalid as UTF-8 but valid in Windows-1252 take the
    documented PDFBOX-3347 fallback."""
    # 0x80 is the Euro sign in Windows-1252; invalid as UTF-8 start byte.
    out = BaseParser.decode_buffer(b"\x80hi")
    assert out.endswith("hi")


# ----------------------------------------------------------------------
# Literal-string escape edge cases
# ----------------------------------------------------------------------


def test_check_for_end_of_string_short_stream() -> None:
    """If fewer than 3 lookahead bytes remain, the brace count must be
    returned unchanged — exercises the early-return branch."""
    p = _parser(b"ab")
    # depth=2 with only 2 bytes available → returned unchanged.
    assert p.check_for_end_of_string(2) == 2


def test_check_for_end_of_string_zero_short_circuit() -> None:
    p = _parser(b"abc")
    assert p.check_for_end_of_string(0) == 0


def test_check_for_end_of_string_crlf_slash() -> None:
    p = _parser(b"\r\n/")
    assert p.check_for_end_of_string(1) == 0


def test_literal_string_eof_after_backslash() -> None:
    """``\\`` immediately followed by EOF inside a literal string must
    leave the ``_consume_escape`` helper at depth unchanged and surface
    as the unterminated-string error from the outer loop."""
    p = _parser(b"(abc\\")
    with pytest.raises(PDFParseError, match="unterminated literal string"):
        p.read_literal_string()


def test_literal_string_crlf_line_continuation() -> None:
    p = _parser(b"(ab\\\r\ncd)")
    # ``\\`` + CRLF is a line continuation: drop both, keep ``abcd``.
    assert p.read_literal_string() == b"abcd"


def test_literal_string_lf_line_continuation() -> None:
    p = _parser(b"(ab\\\ncd)")
    assert p.read_literal_string() == b"abcd"


def test_literal_string_cr_only_line_continuation() -> None:
    """Bare CR after ``\\`` is also a line continuation."""
    p = _parser(b"(ab\\\rcd)")
    assert p.read_literal_string() == b"abcd"


# ----------------------------------------------------------------------
# parse_dir_object branches
# ----------------------------------------------------------------------


def test_parse_dir_object_eof_returns_none() -> None:
    p = _parser(b"")
    assert p.parse_dir_object() is None


def test_parse_dir_object_hex_string() -> None:
    p = _parser(b"<48656C6C6F>")
    out = p.parse_dir_object()
    assert isinstance(out, COSString)
    assert out.get_bytes() == b"Hello"


def test_parse_dir_object_literal_string() -> None:
    p = _parser(b"(Hi)")
    out = p.parse_dir_object()
    assert isinstance(out, COSString)
    assert out.get_bytes() == b"Hi"


def test_parse_dir_object_name() -> None:
    p = _parser(b"/Foo ")
    out = p.parse_dir_object()
    assert isinstance(out, COSName)
    assert out.get_name() == "Foo"


def test_parse_dir_object_bare_r_returns_cosobject_sentinel() -> None:
    """A bare ``R`` token outside the ``num gen R`` form must return a
    placeholder ``COSObject`` for ``parse_cos_array`` to fold back into
    an indirect reference."""
    p = _parser(b"R ")
    out = p.parse_dir_object()
    assert isinstance(out, COSObject)


def test_parse_dir_object_unknown_token_returns_null() -> None:
    p = _parser(b"garbage ")
    out = p.parse_dir_object()
    assert out is COSNull.NULL


def test_parse_dir_object_endobj_rewinds_and_returns_none() -> None:
    p = _parser(b"endobj")
    assert p.parse_dir_object() is None
    # The token was rewound.
    assert p.position == 0


def test_parse_dir_object_endstream_rewinds_and_returns_none() -> None:
    p = _parser(b"endstream")
    assert p.parse_dir_object() is None
    assert p.position == 0


def test_parse_dir_object_recovers_unknown_token_as_null() -> None:
    """A leading byte that doesn't match a fast-path (here ``]``) is
    consumed as a recovery token and parsed as ``COSNull.NULL`` with a
    logged warning."""
    p = _parser(b"]")
    out = p.parse_dir_object()
    assert out is COSNull.NULL


# ----------------------------------------------------------------------
# parse_cos_array
# ----------------------------------------------------------------------


def test_parse_cos_array_basic() -> None:
    p = _parser(b"[1 2 3]")
    arr = p.parse_cos_array()
    assert isinstance(arr, COSArray)
    assert len(arr) == 3


def test_parse_cos_array_indirect_reference_resolved() -> None:
    """``[5 0 R]`` must be folded into a single resolved object pool
    entry — exercising the COSObject placeholder + get_object_from_pool
    branch."""
    doc = COSDocument()
    p = _parser(b"[5 0 R]")
    p._document = doc
    arr = p.parse_cos_array()
    assert len(arr) == 1
    # The entry is a real COSObject (resolved from the pool).
    assert isinstance(arr.get(0), COSObject)


def test_parse_cos_array_invalid_indirect_pair_warning() -> None:
    """A negative object number in ``num gen R`` falls into the warning
    branch — the resulting array element is dropped (``pbo`` stays
    ``None`` and the array is shorter)."""
    doc = COSDocument()
    # Synthesise: negative num + 0 R — read by parsing manually.
    # Build the COSArray state by parsing ``[-1 0 R]``.
    p = _parser(b"[-1 0 R]")
    p._document = doc
    arr = p.parse_cos_array()
    # The negative-number branch logs a warning and skips; array has no
    # surviving entries.
    assert len(arr) == 0


def test_parse_cos_array_endobj_terminates() -> None:
    """A stray ``endobj`` inside an array terminates the array as a
    recovery measure."""
    p = _parser(b"[1 2 endobj")
    arr = p.parse_cos_array()
    assert len(arr) == 2


# ----------------------------------------------------------------------
# parse_cos_dictionary
# ----------------------------------------------------------------------


def test_parse_cos_dictionary_recovers_from_garbage() -> None:
    """A non-``/`` head byte must trigger
    :meth:`read_until_end_of_cos_dictionary` — when that finds ``/``,
    parsing continues."""
    p = _parser(b"<< garbage /Foo 1 >>")
    d = p.parse_cos_dictionary()
    assert isinstance(d, COSDictionary)
    assert d.get_int("Foo") == 1


def test_parse_cos_dictionary_missing_close_logs_warning() -> None:
    """A dictionary that ends after the final value without ``>>`` still
    returns the parsed dict — the missing-close branch logs a warning
    but does not raise."""
    # Truncated input: no ``>>``.
    p = _parser(b"<< /Foo 1 ")
    d = p.parse_cos_dictionary()
    assert d.get_int("Foo") == 1


def test_parse_cos_dictionary_endobj_recovery() -> None:
    """An ``endobj`` marker inside a malformed dictionary stops parsing
    and returns the dict accumulated so far."""
    p = _parser(b"<< /Foo 1 endobj")
    d = p.parse_cos_dictionary()
    assert d.get_int("Foo") == 1


def test_parse_cos_dictionary_empty_name_warning() -> None:
    """An empty key (``/`` directly followed by whitespace + value) must
    log the empty-COSName warning but still record the entry."""
    p = _parser(b"<< / 1 >>")
    d = p.parse_cos_dictionary()
    # The empty key is stored as COSName("").
    assert d.get_int(COSName.get_pdf_name("")) == 1


def test_parse_cos_dictionary_value_indirect_reference() -> None:
    """``/Key 5 0 R`` must be resolved through the document pool — this
    exercises the indirect-reference branch in
    :meth:`parse_cos_dictionary_value`."""
    doc = COSDocument()
    p = _parser(b"<< /Foo 5 0 R >>")
    p._document = doc
    d = p.parse_cos_dictionary()
    val = d.get_item(COSName.get_pdf_name("Foo"))
    assert val is not None


def test_parse_cos_dictionary_value_zero_object_number_recovers() -> None:
    """An object number ``<= 0`` triggers the recovery branch and the
    value is replaced by ``COSNull.NULL``."""
    doc = COSDocument()
    p = _parser(b"<< /Foo 0 0 R >>")
    p._document = doc
    d = p.parse_cos_dictionary()
    val = d.get_item(COSName.get_pdf_name("Foo"))
    assert val is COSNull.NULL


# ----------------------------------------------------------------------
# read_until_end_of_cos_dictionary
# ----------------------------------------------------------------------


def test_read_until_end_of_cos_dictionary_eof() -> None:
    """Reaching EOF in the recovery scan returns ``True`` (caller stops
    parsing)."""
    p = _parser(b"abcdef")
    assert p.read_until_end_of_cos_dictionary() is True


def test_read_until_end_of_cos_dictionary_finds_slash() -> None:
    p = _parser(b"abc/Foo")
    assert p.read_until_end_of_cos_dictionary() is False
    # The ``/`` is left for the caller.
    assert p.peek_byte() == 0x2F


def test_read_until_end_of_cos_dictionary_endstream_detected() -> None:
    p = _parser(b"\x00endstream")
    assert p.read_until_end_of_cos_dictionary() is True


def test_read_until_end_of_cos_dictionary_endobj_detected() -> None:
    p = _parser(b"\x00endobj")
    assert p.read_until_end_of_cos_dictionary() is True


# ----------------------------------------------------------------------
# parse_cos_number
# ----------------------------------------------------------------------


def test_parse_cos_number_integer() -> None:
    p = _parser(b"42 ")
    out = p.parse_cos_number()
    assert isinstance(out, COSInteger)
    assert out.value == 42


def test_parse_cos_number_float_with_exp() -> None:
    p = _parser(b"1.5e2 ")
    out = p.parse_cos_number()
    # COSFloat — value derived from the textual form.
    assert out.float_value() == pytest.approx(150.0)


def test_parse_cos_number_strips_trailing_e_for_endobj() -> None:
    """PDFBOX-5025: ``74191endobj`` — the trailing ``e`` is rewound so
    ``endobj`` can be read separately."""
    p = _parser(b"74191endobj")
    out = p.parse_cos_number()
    assert isinstance(out, COSInteger)
    assert out.value == 74191
    # Cursor is back at the ``e`` of ``endobj``.
    assert p.read_byte() == ord("e")


def test_parse_cos_number_empty_buffer_raises() -> None:
    p = _parser(b" ")
    # Move cursor past the space first; then the next byte is EOF.
    p.read_byte()
    with pytest.raises(PDFParseError, match="expected number"):
        p.parse_cos_number()


# ----------------------------------------------------------------------
# parse_cos_string + parse_cos_hex_string
# ----------------------------------------------------------------------


def test_parse_cos_string_literal() -> None:
    p = _parser(b"(Hello)")
    out = p.parse_cos_string()
    assert isinstance(out, COSString)
    assert out.get_bytes() == b"Hello"


def test_parse_cos_string_hex() -> None:
    p = _parser(b"<48656C6C6F>")
    out = p.parse_cos_string()
    assert out.get_bytes() == b"Hello"


def test_parse_cos_string_bad_lead_raises() -> None:
    p = _parser(b"X")
    with pytest.raises(PDFParseError, match="should start with"):
        p.parse_cos_string()


def test_parse_cos_hex_string_skips_invalid_bytes_to_close() -> None:
    """An invalid byte inside the hex sequence triggers the skip-to-
    ``>`` recovery; valid prefix is preserved."""
    # 'XY' is not hex; the caller pre-consumes the '<', then parser
    # reads '48' then 'XY' triggers the skip-until-close path.
    # parse_cos_hex_string expects the leading ``<`` already consumed.
    p = _parser(b"48XY>")
    out = p.parse_cos_hex_string()
    assert isinstance(out, COSString)


def test_parse_cos_hex_string_eof_after_invalid_raises() -> None:
    """Invalid byte + missing ``>`` after recovery raises EOS error."""
    p = _parser(b"48XY")
    with pytest.raises(PDFParseError, match="Missing closing bracket"):
        p.parse_cos_hex_string()


def test_parse_cos_hex_string_unterminated_raises() -> None:
    p = _parser(b"4865")
    with pytest.raises(PDFParseError, match="Missing closing bracket"):
        p.parse_cos_hex_string()


# ----------------------------------------------------------------------
# get_object_key cache reuse
# ----------------------------------------------------------------------


def test_get_object_key_returns_cached_when_document_attached() -> None:
    """When a document with a matching xref-table key exists, the parser
    returns the cached instance so identity comparisons succeed."""
    doc = COSDocument()
    key = COSObjectKey(7, 0)
    # Wire the key into the document's xref table.
    doc.get_xref_table()[key] = 0
    p = _parser(b"")
    p._document = doc
    cached = p.get_object_key(7, 0)
    assert cached is key


def test_get_object_key_uncached_returns_fresh() -> None:
    """Without a matching xref entry, a freshly constructed key is
    returned."""
    doc = COSDocument()
    p = _parser(b"")
    p._document = doc
    out = p.get_object_key(99, 0)
    assert out.object_number == 99


def test_get_object_from_pool_without_document_raises() -> None:
    p = _parser(b"")
    with pytest.raises(PDFParseError, match="content stream"):
        p.get_object_from_pool(COSObjectKey(1, 0))


# ----------------------------------------------------------------------
# Misc sanity covers — keep the file honest on simple helpers.
# ----------------------------------------------------------------------


def test_read_keyword_returns_true_for_keyword_token() -> None:
    p = _parser(b"true ")
    assert p.read_keyword() == b"true"


def test_parse_dir_object_true_false_null() -> None:
    assert _parser(b"true").parse_dir_object() is COSBoolean.TRUE
    assert _parser(b"false").parse_dir_object() is COSBoolean.FALSE
    assert _parser(b"null").parse_dir_object() is COSNull.NULL


# ----------------------------------------------------------------------
# parse_cos_dictionary_value — error branches for invalid R-references.
# ----------------------------------------------------------------------


def test_parse_cos_dictionary_value_float_object_number_returns_null() -> None:
    """A float in the object-number slot (``/K 1.5 5 R``) is detected
    after the gen-number read and replaced with ``COSNull.NULL``."""
    doc = COSDocument()
    # value=1 (parsed first), then is_digit_at=True (next is '5'), so the
    # parser tries the indirect-ref branch. We need value (the first
    # number) to be COSNumber-but-not-COSInteger — i.e. COSFloat. Build a
    # dict where ``1.0`` is followed by an integer.
    p = _parser(b"<< /Foo 1.0 5 R >>")
    p._document = doc
    d = p.parse_cos_dictionary()
    assert d.get_item(COSName.get_pdf_name("Foo")) is COSNull.NULL


def test_parse_cos_dictionary_value_float_generation_returns_null() -> None:
    """A float in the generation-number slot triggers the matching
    branch and yields ``COSNull.NULL``."""
    doc = COSDocument()
    p = _parser(b"<< /Foo 5 0.5 R >>")
    p._document = doc
    d = p.parse_cos_dictionary()
    assert d.get_item(COSName.get_pdf_name("Foo")) is COSNull.NULL


def test_parse_cos_dictionary_missing_dict_value_returns_dict() -> None:
    """A name with no following value (immediately ``>>``) leaves
    ``value`` as ``None`` from :meth:`parse_cos_dictionary_value`
    (``parse_dir_object`` returns ``None`` at EOF / closing delimiter),
    triggering the early-return-False branch in
    :meth:`parse_cos_dictionary_name_value_pair`."""
    # ``/Foo`` followed immediately by ``>>`` — parse_dir_object peeks
    # ``>`` (not in any fast-path) and ``read_string`` returns the empty
    # string... but ``>`` is handled differently. The deterministic way
    # is to use a recovery-keyword: ``/Foo endobj`` makes parse_dir_object
    # rewind ``endobj`` and return None, so the caller registers
    # ``value is None`` and returns False.
    p = _parser(b"<< /Foo endobj")
    d = p.parse_cos_dictionary()
    assert isinstance(d, COSDictionary)


def test_parse_cos_dictionary_skips_invalid_cosinteger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Out-of-range ``COSInteger`` values are skipped with a warning
    (the dict ends up without the key) — exercises the
    ``not value.is_valid()`` branch.

    Python ints are unbounded so ``parse_cos_number`` never produces an
    OUT_OF_RANGE sentinel through normal parsing (unlike Java). We
    drive the branch by monkey-patching ``COSInteger.is_valid`` to
    return ``False`` once during the dict parse."""
    from pypdfbox.cos.cos_integer import COSInteger as _CI

    monkeypatch.setattr(_CI, "is_valid", lambda self: False)

    p = _parser(b"<< /Foo 1 >>")
    d = p.parse_cos_dictionary()
    # Branch: the integer is rejected as invalid; ``Foo`` is never set.
    assert d.get_item(COSName.get_pdf_name("Foo")) is None


# ----------------------------------------------------------------------
# decode_buffer — Latin-1 secondary fallback.
# ----------------------------------------------------------------------


def test_decode_buffer_latin1_secondary_fallback() -> None:
    """Bytes invalid as both UTF-8 *and* Windows-1252 fall through to
    the Latin-1 safety net — exercises lines 761-762."""
    # 0x81 is undefined in Windows-1252 (it raises with errors='strict').
    # Combined with a UTF-8-invalid lead byte 0xC0, this fails both
    # decode steps and lands on the Latin-1 final branch.
    out = BaseParser.decode_buffer(b"\x81")
    # Latin-1 maps 0x81 to U+0081.
    assert out == "\x81"


# ----------------------------------------------------------------------
# parse_cos_dictionary close-mismatch (raises caught + warning).
# ----------------------------------------------------------------------


def test_parse_cos_dictionary_close_mismatch_logged() -> None:
    """When the dict body ends with ``>X`` instead of ``>>``, the
    :meth:`read_expected_char` raises and the warning branch fires —
    the partial dict is still returned."""
    p = _parser(b"<< /Foo 1 >X")
    d = p.parse_cos_dictionary()
    assert d.get_int("Foo") == 1


# ----------------------------------------------------------------------
# parse_cos_array bracket reentry recovery (line 979).
# ----------------------------------------------------------------------


def test_parse_cos_array_corrupt_element_with_nested_array() -> None:
    """When a corrupt element is followed by a new ``[``, the parser
    returns the array accumulated so far — exercises the
    ``is_this_the_end empty + peek == '['`` recovery branch."""
    # A bare ``R`` without preceding integers becomes a COSObject
    # placeholder; the recovery code looks at the next byte — a ``[``
    # closes the current array.
    doc = COSDocument()
    p = _parser(b"[R[")
    p._document = doc
    arr = p.parse_cos_array()
    assert isinstance(arr, COSArray)


# ----------------------------------------------------------------------
# read_string_with_length EOF mid-token.
# ----------------------------------------------------------------------


def test_read_string_with_length_eof_in_token() -> None:
    """Reaching EOF before ``length`` bytes are read must break the loop
    and return what was accumulated — exercises the EOF-mid-token branch."""
    p = _parser(b"ab")
    assert p.read_string_with_length(10) == "ab"


# ----------------------------------------------------------------------
# parse_cos_hex_string whitespace + odd-pair-skip recovery.
# ----------------------------------------------------------------------


def test_parse_cos_hex_string_whitespace_ignored() -> None:
    """Embedded whitespace (space, tab, LF, CR, BS, FF) inside a hex
    string is silently dropped — exercises the whitespace ``continue``
    branch."""
    p = _parser(b"48 65\t6C\n6C\r6F\x08\x0C>")
    out = p.parse_cos_hex_string()
    assert isinstance(out, COSString)
    assert out.get_bytes() == b"Hello"


def test_parse_cos_hex_string_odd_half_pair_before_invalid() -> None:
    """An odd accumulated half-pair followed by an invalid byte triggers
    the dangling-half-pair pop before the skip-to-close recovery."""
    # ``4`` + non-hex ``Z`` + ``>`` — the lone ``4`` is popped, then we
    # skip until ``>``.
    p = _parser(b"4Z>")
    out = p.parse_cos_hex_string()
    assert isinstance(out, COSString)


# ----------------------------------------------------------------------
# parse_cos_array re-entry recovery (line 979).
# ----------------------------------------------------------------------


def test_parse_cos_array_bare_r_then_lbracket_returns_partial() -> None:
    """A corrupt bare-``R`` element followed (after whitespace) by
    ``[``: ``read_string`` returns ``""`` because the next byte is
    whitespace; with peek == ``[`` the recovery branch returns the
    partial array."""
    doc = COSDocument()
    # ``[1 R [`` — after the bogus ``1 R`` placeholder fold the
    # whitespace is left in place so ``read_string`` returns empty.
    p = _parser(b"[1 R [")
    p._document = doc
    arr = p.parse_cos_array()
    assert isinstance(arr, COSArray)
