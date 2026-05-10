"""Parity tests for the upstream-shaped Type1Parser helpers.

Upstream (``Type1Parser.java``) does not ship a dedicated
``Type1ParserTest`` — the bulk of its coverage lives in
``Type1FontTest`` via end-to-end parsing of the embedded sample PFB.
These tests target the helper methods on ``Type1Parser`` directly
(``read``, ``read_maybe``, ``read_value``, ``read_proc``, ...) so we
can verify each one against a hand-built token sequence.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_END_PROC,
    TOKEN_INTEGER,
    TOKEN_LITERAL,
    TOKEN_NAME,
    TOKEN_REAL,
    TOKEN_START_ARRAY,
    TOKEN_START_PROC,
    Type1Lexer,
    Type1Parser,
)


def _parser_from(src: str | bytes) -> Type1Parser:
    parser = Type1Parser()
    parser._lexer = Type1Lexer(src)
    return parser


# ---------- decrypt / hex helpers ----------


def test_decrypt_no_encryption_returns_input() -> None:
    # n == -1 short-circuit (PDFBox-undocumented tolerance).
    assert Type1Parser.decrypt(b"\x01\x02\x03", Type1Parser.EEXEC_KEY, -1) == b"\x01\x02\x03"


def test_decrypt_short_input_returns_empty() -> None:
    assert Type1Parser.decrypt(b"\x01\x02", Type1Parser.EEXEC_KEY, 4) == b""
    assert Type1Parser.decrypt(b"", Type1Parser.EEXEC_KEY, 4) == b""


def test_decrypt_eexec_round_trip_against_font_util() -> None:
    from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil

    plain = b"hello private dict body"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    assert Type1Parser.decrypt(cipher, Type1Parser.EEXEC_KEY, 4) == plain


def test_decrypt_charstring_round_trip_against_font_util() -> None:
    from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil

    plain = b"\x10\x11\x12\x13"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    assert Type1Parser.decrypt(cipher, Type1Parser.CHARSTRING_KEY, 4) == plain


def test_is_binary_pure_hex_returns_false() -> None:
    assert Type1Parser.is_binary(b"abcd") is False
    assert Type1Parser.is_binary(b"   1") is False


def test_is_binary_with_high_byte_returns_true() -> None:
    assert Type1Parser.is_binary(b"\x80\x81\x82\x83") is True


def test_is_binary_short_input_returns_true() -> None:
    assert Type1Parser.is_binary(b"ab") is True


def test_hex_to_binary_basic() -> None:
    assert Type1Parser.hex_to_binary(b"48656C6C6F") == b"Hello"


def test_hex_to_binary_strips_whitespace_and_unmatched_nibble() -> None:
    assert Type1Parser.hex_to_binary(b"48 65 6c 6c 6") == b"Hell"


# ---------- read / read_maybe ----------


def test_read_returns_token_when_kind_matches() -> None:
    parser = _parser_from("/Foo")
    assert parser.read(TOKEN_LITERAL) == (TOKEN_LITERAL, "Foo")


def test_read_with_name_matches_value() -> None:
    parser = _parser_from("def")
    assert parser.read(TOKEN_NAME, "def") == (TOKEN_NAME, "def")


def test_read_raises_on_kind_mismatch() -> None:
    parser = _parser_from("/Foo")
    with pytest.raises(OSError):
        parser.read(TOKEN_INTEGER)


def test_read_raises_on_eof() -> None:
    parser = _parser_from("")
    with pytest.raises(OSError):
        parser.read(TOKEN_NAME)


def test_read_raises_on_name_mismatch() -> None:
    parser = _parser_from("def")
    with pytest.raises(OSError):
        parser.read(TOKEN_NAME, "begin")


def test_read_maybe_consumes_when_match() -> None:
    parser = _parser_from("dup 1")
    assert parser.read_maybe(TOKEN_NAME, "dup") == (TOKEN_NAME, "dup")
    # The next token should still be available.
    assert parser.read(TOKEN_INTEGER) == (TOKEN_INTEGER, 1)


def test_read_maybe_leaves_position_when_mismatch() -> None:
    parser = _parser_from("def")
    assert parser.read_maybe(TOKEN_NAME, "begin") is None
    # Token still available afterwards.
    assert parser.read(TOKEN_NAME, "def") == (TOKEN_NAME, "def")


def test_read_maybe_at_eof_returns_none() -> None:
    parser = _parser_from("")
    assert parser.read_maybe(TOKEN_NAME, "anything") is None


# ---------- read_value / read_dict_value ----------


def test_read_value_reads_array() -> None:
    parser = _parser_from("[ 1 2 3 ] def")
    value = parser.read_value()
    assert value[0][0] == TOKEN_START_ARRAY
    assert value[-1][0] == "endarray"
    # Inner integers preserved.
    inner = [v for k, v in value if k == TOKEN_INTEGER]
    assert inner == [1, 2, 3]


def test_read_value_reads_proc() -> None:
    parser = _parser_from("{ 1 2 add } readonly def")
    value = parser.read_value()
    assert value[0][0] == TOKEN_START_PROC
    # readProc consumes through the matching END_PROC.
    assert value[-1][0] == TOKEN_END_PROC


def test_read_dict_value_consumes_trailing_def() -> None:
    parser = _parser_from("[ 0 1 2 ] readonly def /next")
    value = parser.read_dict_value()
    inner = [v for k, v in value if k == TOKEN_INTEGER]
    assert inner == [0, 1, 2]
    # After the def we should be looking at /next.
    assert parser.read(TOKEN_LITERAL) == (TOKEN_LITERAL, "next")


def test_read_proc_handles_nested() -> None:
    parser = _parser_from("{ 1 { 2 { 3 } } } def")
    parser.read(TOKEN_START_PROC)
    body = parser.read_proc()
    # Make sure nesting was tracked (3 END_PROC tokens consumed inside).
    end_count = sum(1 for t in body if t[0] == TOKEN_END_PROC)
    assert end_count == 3


def test_read_proc_void_consumes_balanced_proc() -> None:
    parser = _parser_from("{ 1 { 2 } 3 } executeonly /next")
    parser.read(TOKEN_START_PROC)
    parser.read_proc_void()
    # Cursor should be at /next.
    assert parser.read(TOKEN_LITERAL) == (TOKEN_LITERAL, "next")


def test_read_proc_void_raises_on_unterminated() -> None:
    parser = _parser_from("{ 1 ")
    parser.read(TOKEN_START_PROC)
    with pytest.raises(OSError):
        parser.read_proc_void()


# ---------- read_def / read_put ----------


def test_read_def_accepts_def() -> None:
    parser = _parser_from("def")
    parser.read_def()  # should not raise


def test_read_def_accepts_nd_synonym() -> None:
    parser = _parser_from("ND")
    parser.read_def()


def test_read_def_accepts_pipe_minus() -> None:
    parser = _parser_from("|-")
    parser.read_def()


def test_read_def_accepts_readonly_noaccess_def() -> None:
    parser = _parser_from("readonly noaccess def")
    parser.read_def()


def test_read_def_raises_on_unrelated_name() -> None:
    parser = _parser_from("foo")
    with pytest.raises(OSError):
        parser.read_def()


def test_read_put_accepts_np() -> None:
    parser = _parser_from("NP")
    parser.read_put()


def test_read_put_accepts_pipe() -> None:
    parser = _parser_from("|")
    parser.read_put()


def test_read_put_accepts_readonly_put() -> None:
    parser = _parser_from("readonly put")
    parser.read_put()


def test_read_put_raises_on_unrelated_name() -> None:
    parser = _parser_from("foo")
    with pytest.raises(OSError):
        parser.read_put()


# ---------- array_to_numbers ----------


def test_array_to_numbers_drops_brackets_and_coerces_types() -> None:
    tokens = [
        (TOKEN_START_ARRAY, "["),
        (TOKEN_INTEGER, 1),
        (TOKEN_REAL, 0.5),
        (TOKEN_INTEGER, -2),
        ("endarray", "]"),
    ]
    assert Type1Parser.array_to_numbers(tokens) == [1, 0.5, -2]


def test_array_to_numbers_raises_on_non_numeric() -> None:
    tokens = [
        (TOKEN_START_ARRAY, "["),
        (TOKEN_INTEGER, 1),
        (TOKEN_NAME, "bogus"),
        ("endarray", "]"),
    ]
    with pytest.raises(OSError):
        Type1Parser.array_to_numbers(tokens)


# ---------- read_simple_value / read_font_info ----------


def test_read_simple_value_assigns_int_keys() -> None:
    parser = _parser_from("1 def")
    parser.read_simple_value("PaintType")
    assert parser.font_dict["PaintType"] == 1


def test_read_simple_value_assigns_font_matrix_array() -> None:
    parser = _parser_from("[ 0.001 0 0 0.001 0 0 ] readonly def")
    parser.read_simple_value("FontMatrix")
    assert parser.font_dict["FontMatrix"] == [0.001, 0, 0, 0.001, 0, 0]


def test_read_simple_value_assigns_font_name_literal() -> None:
    parser = _parser_from("/Helvetica def")
    parser.read_simple_value("FontName")
    assert parser.font_dict["FontName"] == "Helvetica"


def test_read_simple_value_unknown_key_is_dropped() -> None:
    parser = _parser_from("123 def")
    parser.read_simple_value("UnknownKey")
    assert "UnknownKey" not in parser.font_dict


def test_read_font_info_lifts_recognised_keys() -> None:
    parser = Type1Parser()
    font_info = {
        "version": [(TOKEN_LITERAL, "001.000")],
        "FullName": [(TOKEN_LITERAL, "Test Regular")],
        "ItalicAngle": [(TOKEN_INTEGER, -12)],
        "isFixedPitch": [(TOKEN_NAME, "true")],
        "UnknownNoise": [(TOKEN_INTEGER, 42)],
    }
    parser.read_font_info(font_info)
    info = parser.font_dict["FontInfo"]
    assert info["version"] == "001.000"
    assert info["FullName"] == "Test Regular"
    assert info["ItalicAngle"] == -12.0
    assert info["isFixedPitch"] is True
    assert "UnknownNoise" not in info


# ---------- read_simple_dict ----------


def test_read_simple_dict_extracts_key_value_tokens() -> None:
    src = "2 dict dup begin /A 1 def /B 2 def end readonly def"
    parser = _parser_from(src)
    out = parser.read_simple_dict()
    assert "A" in out
    assert "B" in out
    a_ints = [v for k, v in out["A"] if k == TOKEN_INTEGER]
    assert a_ints == [1]


def test_read_simple_dict_handles_pdfbox_5942_empty_def_short_circuit() -> None:
    # The "<N> dict dup def" early-exit form (no begin/end body).
    parser = _parser_from("0 dict dup def")
    assert parser.read_simple_dict() == {}


# ---------- read_encoding ----------


def test_read_encoding_standard_encoding_predef() -> None:
    parser = _parser_from("StandardEncoding readonly def")
    parser.read_encoding()
    assert parser.font_dict["Encoding"] == "StandardEncoding"


def test_read_encoding_unknown_predef_raises() -> None:
    parser = _parser_from("MysteryEncoding def")
    with pytest.raises(OSError):
        parser.read_encoding()


def test_read_encoding_dup_table() -> None:
    src = "256 array dup 65 /A put dup 66 /B put readonly def"
    parser = _parser_from(src)
    parser.read_encoding()
    enc = parser.font_dict["Encoding"]
    assert isinstance(enc, dict)
    assert enc[65] == "A"
    assert enc[66] == "B"


def test_read_encoding_skips_for_loop_preamble_pdfbox_2134() -> None:
    # Real fonts often emit ``0 1 255 { ... } for`` between the array
    # opener and the first ``dup``. The drain loop should swallow
    # everything up to ``dup`` / ``readonly`` / ``def``.
    src = (
        "256 array 0 1 255 dup 65 /A put readonly def"
    )
    parser = _parser_from(src)
    parser.read_encoding()
    assert parser.font_dict["Encoding"][65] == "A"


# ---------- read_private ----------


def test_read_private_blue_values_array() -> None:
    parser = Type1Parser()
    parser.read_private(
        "BlueValues",
        [
            (TOKEN_START_ARRAY, "["),
            (TOKEN_INTEGER, -20),
            (TOKEN_INTEGER, 0),
            (TOKEN_INTEGER, 800),
            (TOKEN_INTEGER, 820),
            ("endarray", "]"),
        ],
    )
    assert parser.font_dict["Private"]["BlueValues"] == [-20, 0, 800, 820]


def test_read_private_force_bold_boolean() -> None:
    parser = Type1Parser()
    parser.read_private("ForceBold", [(TOKEN_NAME, "true")])
    assert parser.font_dict["Private"]["ForceBold"] is True


def test_read_private_blue_scale_real() -> None:
    parser = Type1Parser()
    parser.read_private("BlueScale", [(TOKEN_REAL, 0.039625)])
    assert parser.font_dict["Private"]["BlueScale"] == pytest.approx(0.039625)


def test_read_private_unknown_key_dropped() -> None:
    parser = Type1Parser()
    parser.read_private("Mystery", [(TOKEN_INTEGER, 42)])
    # Private dict gets created (setdefault) but Mystery is not stored.
    assert parser.font_dict.get("Private", {}).get("Mystery") is None


# ---------- read_post_script_wrapper ----------


def test_read_post_script_wrapper_unwraps_value() -> None:
    src = (
        "systemdict /internaldict known "
        "{ pop } "
        "{ pop } "
        "ifelse "
        "{ pop /Inner } if /next"
    )
    parser = _parser_from(src)
    value: list[tuple[str, object]] = []
    parser.read_post_script_wrapper(value)
    # Wrapper rewrote value to /Inner.
    assert value == [(TOKEN_LITERAL, "Inner")]
    # And cursor is at /next.
    assert parser.read(TOKEN_LITERAL) == (TOKEN_LITERAL, "next")


def test_read_post_script_wrapper_no_wrapper_leaves_value_intact() -> None:
    # When the next token is not "systemdict", upstream simply returns.
    parser = _parser_from("/notthewrapper")
    value: list[tuple[str, object]] = [(TOKEN_INTEGER, 1)]
    parser.read_post_script_wrapper(value)
    assert value == [(TOKEN_INTEGER, 1)]


# ---------- read_other_subrs ----------


def test_read_other_subrs_array_form() -> None:
    parser = _parser_from("[ 1 2 3 ] def")
    parser.read_other_subrs()  # just confirm it returns; we don't store


def test_read_other_subrs_dup_form() -> None:
    parser = _parser_from(
        "2 array "
        "dup 0 { 1 } NP "
        "dup 1 { 2 } NP "
        "def"
    )
    parser.read_other_subrs()
