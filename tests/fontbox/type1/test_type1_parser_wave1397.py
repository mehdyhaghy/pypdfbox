"""Wave 1397 — residual branch coverage for ``Type1Parser`` / ``Type1Lexer``.

Each test names the specific partial branch it closes (line number in
``pypdfbox/fontbox/type1/type1_parser.py``). The fixtures are hand-built
PostScript snippets — small enough to keep the test surface readable
while exercising the EOF / malformed-input branches the real-world
parser corpus would otherwise need fuzzing to hit.
"""

from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_CHARSTRING,
    TOKEN_END_PROC,
    Type1Lexer,
    Type1Parser,
)

_HEADER = (
    b"%!PS-AdobeFont-1.0: Wave1397 001.000\n"
    b"12 dict begin\n"
    b"/FontName /Wave1397 def\n"
    b"/FontType 1 def\n"
)


def _rd(prefix: bytes, plain: bytes, suffix: bytes = b" ND\n") -> bytes:
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=0)
    return prefix + str(len(cipher)).encode("ascii") + b" RD " + cipher + suffix


# ---------------------------------------------------------------------------
# Lexer EOF / malformed-input branches
# ---------------------------------------------------------------------------


def test_read_token_eof_returns_none_and_skips_prev_state_update() -> None:
    """Branch 209->211: ``read_token`` skips the ``_prev_token`` update at EOF."""
    lex = Type1Lexer("")
    assert lex.read_token() is None
    # A second call still returns None — the EOF state is sticky.
    assert lex.read_token() is None


def test_read_regular_stops_on_delimiter_without_eof() -> None:
    """Branch 258->263: ``read_regular`` breaks on a delimiter mid-buffer."""
    lex = Type1Lexer("/SomeName)")
    # Consume the leading "/" so read_regular starts on the bareword.
    lex.next_token()
    # Reset position to the bareword: just call _read_literal_name path
    # via the public next_token + check remaining hits ")" delimiter.
    lex2 = Type1Lexer("abc) tail")
    assert lex2.read_regular() == "abc"
    # Position should be at the ")" delimiter, not at EOF.
    assert lex2.remaining().startswith(")")


def test_read_regular_eof_returns_none_when_starts_on_delimiter() -> None:
    """Branch 264 (already at delimiter) — guard against the start==pos path."""
    lex = Type1Lexer(")foo")
    assert lex.read_regular() is None


def test_read_regular_consumes_to_end_of_buffer() -> None:
    """Branch 258->263: ``read_regular`` reaches EOF without hitting a
    delimiter — while-condition exits the loop instead of ``break``.
    """
    lex = Type1Lexer("abc")
    assert lex.read_regular() == "abc"
    assert lex.remaining() == ""


def test_read_hex_string_at_eof_without_closing_bracket() -> None:
    """Branch 469->472: ``_read_hex_string`` reaches buffer end without ``>``."""
    lex = Type1Lexer("<ab cd")
    tok = lex.next_token()
    assert tok is not None
    assert tok[0] == "string"
    # Odd nibble count got padded with a trailing 0.
    assert tok[1] == bytes.fromhex("abcd")


def test_bareword_rd_with_non_integer_prev_is_plain_name() -> None:
    """Branch 503->518: ``RD`` bareword whose ``_prev_token`` is set but
    not INTEGER (e.g. a literal name) -- the charstring capture is
    skipped and ``RD`` is emitted as a TOKEN_NAME.
    """
    # ``/foo RD`` -- prev is (literal, "foo"), so the INT-kind check fails.
    lex = Type1Lexer("/foo RD")
    assert lex.next_token() == ("literal", "foo")
    assert lex.next_token() == ("name", "RD")


def test_bareword_rd_at_eof_skips_delimiter_consumption() -> None:
    """Branch 506->508: ``RD`` immediately after an INT at EOF — the
    delimiter-byte skip is bypassed (``self._pos == len(buf)``).
    """
    # "5 RD" with no delimiter or payload — RD lands at EOF.
    lex = Type1Lexer("5 RD")
    int_tok = lex.next_token()
    assert int_tok == ("integer", 5)
    rd_tok = lex.next_token()
    # Lexer captures an empty-tail charstring because there are no
    # payload bytes left after RD.
    assert rd_tok is not None and rd_tok[0] == TOKEN_CHARSTRING
    assert rd_tok[1] == b""


# ---------------------------------------------------------------------------
# ASCII top-level parse branches
# ---------------------------------------------------------------------------


def test_font_info_with_unrecognised_literal_value_clears_pending_key() -> None:
    """Branch 696->698: literal value belongs to a key NOT in
    ``_FONT_INFO_KEYS`` — the value-coercion branch is skipped and
    ``pending_key`` is reset directly.
    """
    src = (
        b"%!PS-AdobeFont-1.0\n"
        b"12 dict begin\n"
        b"/FontInfo 4 dict dup begin\n"
        b"  /CustomKey /SomeLiteralValue def\n"
        b"  /FullName (Wave1397FI) def\n"
        b"end\n"
        b"/FontName /Wave1397 def\n"
    )
    parser = Type1Parser()
    parser.parse(src, Type1FontUtil.eexec_encrypt(b""))
    # FullName landed; CustomKey was filtered out.
    assert parser.font_dict["FontInfo"].get("FullName") == "Wave1397FI"
    assert "CustomKey" not in parser.font_dict["FontInfo"]


def test_font_info_name_value_neither_true_false_nor_def() -> None:
    """Branches 736->740 / 740->742: a ``_FONT_INFO_KEYS`` key whose value
    is a bareword (e.g. ``readonly``) that is not true/false and not def.
    """
    src = (
        b"%!PS-AdobeFont-1.0\n"
        b"12 dict begin\n"
        b"/FontInfo 4 dict dup begin\n"
        b"  /isFixedPitch readonly noaccess def\n"
        b"end\n"
        b"/FontName /Wave1397 def\n"
    )
    parser = Type1Parser()
    parser.parse(src, Type1FontUtil.eexec_encrypt(b""))
    # The key was seen but no boolean value pinned -- key stays absent
    # because pending_key is reset on the trailing "def".
    assert "isFixedPitch" not in parser.font_dict.get("FontInfo", {})


def test_top_level_def_without_value_resets_pending_key() -> None:
    """Branch 774->666: a top-level key followed directly by ``def`` (no
    value) -- pending_key resets and the loop continues without storing.
    """
    src = (
        b"%!PS-AdobeFont-1.0\n"
        b"12 dict begin\n"
        b"/UniqueID def\n"
        b"/FontName /Wave1397 def\n"
    )
    parser = Type1Parser()
    parser.parse(src, Type1FontUtil.eexec_encrypt(b""))
    assert parser.font_dict["FontName"] == "Wave1397"
    assert "UniqueID" not in parser.font_dict


# ---------------------------------------------------------------------------
# Array / proc reader branches
# ---------------------------------------------------------------------------


def test_read_proc_ignores_charstring_token() -> None:
    """Branch 795->785: ``_read_proc`` sees a CHARSTRING token mid-proc
    and skips it rather than appending.
    """
    parser = Type1Parser()
    # Build a proc body that contains a synthetic CHARSTRING via RD.
    src = b"{ 1 2 RD ab }"
    lex = Type1Lexer(src)
    open_tok = lex.next_token()
    assert open_tok is not None and open_tok[0] == "startproc"
    out = parser._read_proc(lex)
    # CHARSTRING isn't in the kept-kinds tuple, so it's silently dropped.
    # Both INTs were captured; the synthetic CHARSTRING between them
    # (driven by ``2 RD ab``) fell through the kind-dispatch chain.
    assert out == [1, 2]


def test_read_array_kind_dispatch_for_each_token_type() -> None:
    """``_read_array`` walks INT / REAL / STRING / LITERAL / NAME kinds,
    plus skips nested arrays via the inner ``_read_array``.
    """
    parser = Type1Parser()
    src = b"[ 1 2.5 (hello) /Name barename [ 3 ] ]"
    lex = Type1Lexer(src)
    open_tok = lex.next_token()
    assert open_tok is not None and open_tok[0] == "startarray"
    out = parser._read_array(lex)
    assert out == [1, 2.5, "hello", "Name", "barename", [3]]


def test_read_array_ignores_charstring_token() -> None:
    """Branch 816->801: ``_read_array`` sees a CHARSTRING token inside the
    body and skips it (the kind isn't in the kept-kinds dispatch).
    """
    parser = Type1Parser()
    src = b"[ 1 2 RD ab ]"
    lex = Type1Lexer(src)
    open_tok = lex.next_token()
    assert open_tok is not None and open_tok[0] == "startarray"
    out = parser._read_array(lex)
    # 1 + integer 2 (RD consumes the bytes after); the CHARSTRING token
    # itself isn't appended.
    assert out == [1, 2]


# ---------------------------------------------------------------------------
# Private / binary parse branches
# ---------------------------------------------------------------------------


def test_lenIV_with_non_integer_value_does_not_pin_len_iv() -> None:
    """Branch 977->979: ``lenIV`` keyed to a non-int (real) value -- the
    int branch is bypassed but the raw value is still stored.
    """
    binary = (
        b"dup /Private 5 dict dup begin\n"
        b"/lenIV 3.5 def\n"
        b"/CharStrings 0 dict dup begin end\n"
        b"end\nend\n"
    )
    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))
    assert parser.font_dict["Private"]["lenIV"] == 3.5


def test_scalar_key_with_no_meaningful_value_skips_assignment() -> None:
    """Branch 988->990: ``_read_scalar_value`` returns None for a key
    whose body is empty array -- the ``if val is not None`` branch is
    skipped so the key never lands in ``private``.
    """
    binary = (
        b"dup /Private 5 dict dup begin\n"
        b"/BlueScale [ 1 ] def\n"  # array body, scalar reader returns None
        b"/CharStrings 0 dict dup begin end\n"
        b"end\nend\n"
    )
    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))
    assert "BlueScale" not in parser.font_dict.get("Private", {})


def test_read_scalar_value_end_array_at_zero_depth_is_tolerated() -> None:
    """Branch 1026->1028: ``END_ARRAY`` token at depth=0 leaves depth
    unchanged (defensive guard against malformed input).
    """
    # Construct a stream that starts with a stray ``]`` then a real value.
    val = Type1Parser._read_scalar_value(Type1Lexer("] 7 def"))
    assert val == 7


def test_read_numeric_array_value_skips_non_array_non_def_prefix() -> None:
    """Branch 1059->1052: opener-search loop continues past name tokens
    that aren't ``def`` and aren't array openers.
    """
    val = Type1Parser._read_numeric_array_value(
        Type1Lexer("readonly noaccess [ 1 2 3 ] def")
    )
    assert val == [1, 2, 3]


def test_read_numeric_array_trailing_non_numeric_token_is_skipped() -> None:
    """Branch 1069->1062: array body contains a non-numeric token between
    numbers -- the ``if kind in (INT, REAL)`` branch is skipped.
    """
    val = Type1Parser._read_numeric_array_value(
        Type1Lexer("[ 1 (skipped) 2 ] def")
    )
    assert val == [1, 2]


def test_read_numeric_array_trailing_drain_passes_through_non_def() -> None:
    """Branch 1076->1072: trailing-drain loop continues past tokens that
    aren't ``def`` / ``ND`` / ``|-``.
    """
    val = Type1Parser._read_numeric_array_value(
        Type1Lexer("[ 1 2 ] readonly noaccess def")
    )
    assert val == [1, 2]


def test_drain_value_tolerates_stray_end_array_at_zero_depth() -> None:
    """Branch 1097->1099: ``_drain_value`` encounters END_ARRAY at depth=0
    (mirrors the scalar reader guard).
    """
    # Should drain through without raising — terminator is the trailing def.
    Type1Parser._drain_value(Type1Lexer("] readonly def"))


def test_read_subrs_trailing_token_loop_continues_on_unknown_name() -> None:
    """Branch 1157->1150: subrs entry's trailing-drain loop sees a NAME
    that isn't NP / | / put -- it consumes and continues looking.
    """
    parser = Type1Parser()
    out: list[bytes] = []
    # Insert a stray ``readonly`` between the charstring and the put.
    src = _rd(b"1 array dup 0 ", b"glyph", b" readonly put\n")
    parser._read_subrs(Type1Lexer(src), out, len_iv=0)
    assert out == [b"glyph"]


def test_read_charstrings_preamble_breaks_on_unknown_token() -> None:
    """Branch 1171->1180: the preamble drain (``dict``/``dup``/``begin``)
    stops early when a non-preamble token appears.
    """
    parser = Type1Parser()
    out: dict[str, bytes] = {}
    # Preamble has only ``dict``; next is the body marker directly.
    src = _rd(b"1 dict /A ", b"glyph", b"")
    parser._read_charstrings(Type1Lexer(src), out, len_iv=0)
    # The literal ``A`` was harvested as a charstring.
    assert out == {"A": b"glyph"}


def test_read_charstrings_eof_after_literal_name_drops_entry() -> None:
    """Adjacent guard: ``length_tok`` is None after a literal -- entry is
    skipped without raising.
    """
    parser = Type1Parser()
    out: dict[str, bytes] = {}
    # Provide a buffer that ends right after consuming the /A literal.
    # peek_token returns ("literal", "A"), next_token consumes it, then
    # the next next_token() for length returns None and we ``continue``.
    parser._read_charstrings(
        Type1Lexer("1 dict dup begin /A"), out, len_iv=0
    )
    assert out == {}


def test_read_charstrings_preamble_drains_all_four_iterations() -> None:
    """Branch 1171->1180: the preamble for-loop completes all 4 iterations
    when ``dict``/``dup``/``begin`` tokens fill them all -- exits via the
    range generator instead of the early ``break``.
    """
    parser = Type1Parser()
    out: dict[str, bytes] = {}
    # 4 preamble tokens in a row -- consumes the entire ``range(4)``.
    parser._read_charstrings(
        Type1Lexer("1 dict dup begin dict /A end"), out, len_iv=0
    )
    assert out == {}


# ---------------------------------------------------------------------------
# Upstream-shaped parity helpers
# ---------------------------------------------------------------------------


def test_parse_ascii_currentdict_terminates_loop() -> None:
    """Branch 1767->1784: the inner for-loop breaks on ``currentdict``
    before the declared length is exhausted.
    """
    src = (
        b"%!PS-AdobeFont-1.0\n"
        b"12 dict begin\n"
        b"/FontName /Wave1397 def\n"
        b"currentdict end\n"
        b"currentfile eexec\n"
    )
    parser = Type1Parser()
    parser.parse_ascii(src)
    assert parser.font_dict["FontName"] == "Wave1397"


def test_read_subrs_streaming_index_out_of_range_silently_skipped() -> None:
    """The streaming ``_read_subrs`` ignores a Subrs entry whose index
    sits outside the declared array length.
    """
    # Build an inline binary segment with a /Subrs 2 array but a
    # ``dup 5`` (out-of-range) entry.
    binary = (
        b"dup /Private 5 dict dup begin\n"
        b"/Subrs 2 array\n"
    )
    binary += _rd(b"dup 5 ", b"out-of-range", b" put\n")
    binary += b"def\n"
    binary += b"/CharStrings 0 dict dup begin end\n"
    binary += b"end\nend\n"

    parser = Type1Parser()
    parser.parse(_HEADER, Type1FontUtil.eexec_encrypt(binary))
    private = parser.font_dict.get("Private", {})
    # All slots remain b"" — the out-of-range write was a no-op.
    assert private.get("Subrs") == [b"", b""]


def test_upstream_read_subrs_index_out_of_range_branch() -> None:
    """Branch 1909->1911: the upstream-parity ``read_subrs`` skips the
    ``subrs[index]=...`` assignment when ``index`` >= ``len(subrs)``.
    Falls through to ``read_put()`` and finishes the iteration cleanly.
    """
    parser = Type1Parser()
    # Declared length 1, but dup index 5 — out of range.
    src = b"1 array " + _rd(b"dup 5 ", b"oor", b" put\n") + b"def\n"
    parser._lexer = Type1Lexer(src)
    parser.read_subrs(len_iv=0)
    # The lone slot stayed empty -- the out-of-range write was a no-op.
    assert parser.font_dict["Private"]["Subrs"] == [b""]


def test_parse_ascii_loop_completes_via_length_exhaustion() -> None:
    """Branch 1767->1784: the inner for-loop runs all ``length`` iterations
    (no early ``break`` on ``currentdict``/``end``) and falls into the
    trailing ``currentdict``/``end``/``currentfile`` recogniser.
    """
    src = (
        b"%!PS-AdobeFont-1.0\n"
        b"1 dict begin\n"
        b"/FontName /Wave1397 def\n"
        b"end\n"
        b"currentfile eexec\n"
    )
    parser = Type1Parser()
    parser.parse_ascii(src)
    assert parser.font_dict["FontName"] == "Wave1397"


def test_read_proc_unmatched_open_proc_collects_inner_tokens() -> None:
    """Defensive smoke -- the read_proc() helper walks nested procs and
    captures the executeonly tail. Exercises ``open_proc += 1`` plus the
    trailing ``executeonly`` recogniser (line 1404-1406).
    """
    parser = Type1Parser()
    parser._lexer = Type1Lexer("{ 1 { 2 } 3 } executeonly")
    parser.read("startproc")
    body = parser.read_proc()
    # Body includes the inner proc + END_PROC + executeonly bareword.
    assert ("integer", 1) in body
    assert ("integer", 3) in body
    assert ("name", "executeonly") in body
    assert any(tok[0] == TOKEN_END_PROC for tok in body)
