from __future__ import annotations

import io

import pytest

from pypdfbox.contentstream import Operator, OperatorName
from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdfwriter import ContentStreamWriter
from pypdfbox.pdfwriter.content_stream_writer import EOL, SPACE

# ---------- helpers ---------------------------------------------------------


def _emit(*tokens: object) -> bytes:
    sink = io.BytesIO()
    ContentStreamWriter(sink).write_tokens(*tokens)
    return sink.getvalue()


def _emit_list(tokens: list[object]) -> bytes:
    sink = io.BytesIO()
    ContentStreamWriter(sink).write_tokens(tokens)
    return sink.getvalue()


def _emit_token(token: object) -> bytes:
    sink = io.BytesIO()
    ContentStreamWriter(sink).write_token(token)
    return sink.getvalue()


# ---------- upstream constants ---------------------------------------------


def test_upstream_class_constants_are_exposed() -> None:
    assert ContentStreamWriter.SPACE == SPACE == b" "
    assert ContentStreamWriter.EOL == EOL == b"\n"


# ---------- COS leaf types --------------------------------------------------


def test_integer_token_emits_ascii_digits_then_space() -> None:
    assert _emit_token(COSInteger.get(42)) == b"42 "


def test_negative_integer_token() -> None:
    assert _emit_token(COSInteger.get(-7)) == b"-7 "


def test_float_token_emits_decimal_then_space() -> None:
    out = _emit_token(COSFloat(0.5))
    assert out.endswith(b" ")
    assert b"0.5" in out


def test_boolean_true_emits_true_then_space() -> None:
    assert _emit_token(COSBoolean.TRUE) == b"true "


def test_boolean_false_emits_false_then_space() -> None:
    assert _emit_token(COSBoolean.FALSE) == b"false "


def test_null_emits_null_then_space() -> None:
    assert _emit_token(COSNull.NULL) == b"null "


def test_name_emits_slash_prefixed() -> None:
    assert _emit_token(COSName.get_pdf_name("Helvetica")) == b"/Helvetica "


def test_name_with_special_byte_is_hash_escaped() -> None:
    # Space is not in the printable allowlist → must be #20-encoded.
    out = _emit_token(COSName.get_pdf_name("foo bar"))
    assert out == b"/foo#20bar "


def test_ascii_string_emits_literal() -> None:
    assert _emit_token(COSString(b"Hello")) == b"(Hello) "


def test_string_with_paren_is_escaped() -> None:
    assert _emit_token(COSString(b"a(b)c")) == b"(a\\(b\\)c) "


def test_non_ascii_string_emits_hex_form() -> None:
    out = _emit_token(COSString(bytes([0xFE, 0xFF, 0x00, 0x41])))
    assert out == b"<FEFF0041> "


# ---------- containers ------------------------------------------------------


def test_empty_array_emits_brackets_then_space() -> None:
    assert _emit_token(COSArray()) == b"[] "


def test_array_of_numbers() -> None:
    arr = COSArray([COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)])
    # Each element is itself emitted with a trailing space (matches upstream).
    assert _emit_token(arr) == b"[1 2 3 ] "


def test_array_with_mixed_types() -> None:
    arr = COSArray([COSInteger.get(1), COSString(b"x"), COSName.get_pdf_name("A")])
    assert _emit_token(arr) == b"[1 (x) /A ] "


def test_nested_array() -> None:
    inner = COSArray([COSInteger.get(1), COSInteger.get(2)])
    outer = COSArray([inner, COSInteger.get(3)])
    assert _emit_token(outer) == b"[[1 2 ] 3 ] "


def test_empty_dictionary_emits_open_close() -> None:
    assert _emit_token(COSDictionary()) == b"<<>> "


def test_dictionary_with_entries() -> None:
    d = COSDictionary()
    d.set_int("Width", 100)
    d.set_int("Height", 200)
    out = _emit_token(d)
    # Each name + value emits its own trailing space.
    assert out == b"<</Width 100 /Height 200 >> "


def test_nested_dictionary_in_array() -> None:
    d = COSDictionary()
    d.set_int("K", 1)
    arr = COSArray([d, COSInteger.get(2)])
    assert _emit_token(arr) == b"[<</K 1 >> 2 ] "


# ---------- operators -------------------------------------------------------


def test_operator_no_operands_emits_name_then_lf() -> None:
    out = _emit_token(Operator.get_operator(OperatorName.BEGIN_TEXT))
    assert out == b"BT\n"


def test_operator_then_operands_via_write_tokens_varargs() -> None:
    # cm operator: 1 0 0 1 100 200 cm
    op = Operator.get_operator(OperatorName.CONCAT)
    out = _emit(
        COSInteger.get(1),
        COSInteger.get(0),
        COSInteger.get(0),
        COSInteger.get(1),
        COSInteger.get(100),
        COSInteger.get(200),
        op,
    )
    # Trailing newline from varargs writeTokens, plus the operator's own newline.
    assert out == b"1 0 0 1 100 200 cm\n\n"


def test_tj_with_array_operand() -> None:
    arr = COSArray(
        [COSString(b"Hello"), COSInteger.get(-100), COSString(b"World")]
    )
    op = Operator.get_operator(OperatorName.SHOW_TEXT_ADJUSTED)
    out = _emit_list([arr, op])
    # writeTokens(list) form does NOT append a trailing newline.
    assert out == b"[(Hello) -100 (World) ] TJ\n"


def test_apostrophe_text_show_operator() -> None:
    out = _emit_token(Operator.get_operator(OperatorName.SHOW_TEXT_LINE))
    assert out == b"'\n"


def test_quote_text_show_operator() -> None:
    out = _emit_token(Operator.get_operator(OperatorName.SHOW_TEXT_LINE_AND_SPACE))
    assert out == b'"\n'


def test_unknown_token_type_raises() -> None:
    with pytest.raises(OSError, match="Unknown type"):
        _emit_token(object())  # type: ignore[arg-type]


# ---------- inline image ----------------------------------------------------


def test_inline_image_block() -> None:
    bi = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    params = COSDictionary()
    params.set_int("W", 1)
    params.set_int("H", 1)
    params.set_name("CS", "G")
    params.set_int("BPC", 8)
    bi.set_image_parameters(params)
    bi.set_image_data(b"\x00")
    out = _emit_token(bi)
    expected = (
        b"BI\n"
        b"/W 1 \n"
        b"/H 1 \n"
        b"/CS /G \n"
        b"/BPC 8 \n"
        b"ID\n"
        b"\x00\n"
        b"EI\n"
    )
    assert out == expected


def test_inline_image_with_no_image_data() -> None:
    bi = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    params = COSDictionary()
    params.set_int("W", 0)
    bi.set_image_parameters(params)
    # ``image_data`` deliberately left None — must not crash.
    out = _emit_token(bi)
    assert b"BI\n" in out
    assert b"ID\n" in out
    assert out.endswith(b"EI\n")


# ---------- write_token vs write_tokens semantics ---------------------------


def test_write_token_single_operand_no_trailing_newline() -> None:
    out = _emit_token(COSInteger.get(5))
    # write_token doesn't add the trailing newline; only the operand's own
    # ``SPACE`` separator follows.
    assert out == b"5 "


def test_write_tokens_list_form_no_trailing_newline() -> None:
    out = _emit_list([COSInteger.get(1), COSInteger.get(2)])
    assert out == b"1 2 "


def test_write_tokens_varargs_appends_newline() -> None:
    out = _emit(COSInteger.get(1), COSInteger.get(2))
    assert out == b"1 2 \n"


# ---------- round trip via PDFStreamParser ----------------------------------


def _is_operator(o: object) -> bool:
    """True for either ``Operator`` flavour (parser vs contentstream).

    The parser ships its own ``Operator`` value type
    (``pypdfbox.pdfparser.pdf_stream_parser.Operator``); the
    contentstream module ports the canonical
    ``pypdfbox.contentstream.operator.Operator``. Both expose a
    no-arg ``get_name``."""
    return o.__class__.__name__ == "Operator"


def _tokens_equal(a: object, b: object) -> bool:
    """Loose equality: parser ``Operator`` and contentstream ``Operator``
    differ in identity, but a successful round trip just needs the names
    + operand sequence to match."""
    if _is_operator(a) and _is_operator(b):
        return a.get_name() == b.get_name()  # type: ignore[attr-defined]
    # COSInteger / COSFloat — compare numeric value.
    if isinstance(a, (COSInteger, COSFloat)) and isinstance(b, (COSInteger, COSFloat)):
        return a.value == b.value
    if isinstance(a, COSName) and isinstance(b, COSName):
        return a.get_name() == b.get_name()
    if isinstance(a, COSString) and isinstance(b, COSString):
        return a.get_bytes() == b.get_bytes()
    if isinstance(a, COSArray) and isinstance(b, COSArray):
        if a.size() != b.size():
            return False
        return all(_tokens_equal(a.get(i), b.get(i)) for i in range(a.size()))
    if isinstance(a, COSBoolean) and isinstance(b, COSBoolean):
        return a.get_value() == b.get_value()
    return isinstance(a, COSNull) and isinstance(b, COSNull)


def test_round_trip_simple_text_block() -> None:
    src = b"BT\n/F1 12 Tf\n100 200 Td\n(Hello World) Tj\nET\n"
    tokens = PDFStreamParser(RandomAccessReadBuffer(src)).parse()

    sink = io.BytesIO()
    ContentStreamWriter(sink).write_tokens(tokens)
    rewritten = sink.getvalue()

    reparsed = PDFStreamParser(RandomAccessReadBuffer(rewritten)).parse()
    assert len(reparsed) == len(tokens)
    for a, b in zip(tokens, reparsed, strict=True):
        assert _tokens_equal(a, b), f"{a!r} != {b!r}"


def test_round_trip_with_cm_and_path_ops() -> None:
    src = b"q\n1 0 0 1 100 200 cm\n0 0 50 50 re\nf\nQ\n"
    tokens = PDFStreamParser(RandomAccessReadBuffer(src)).parse()

    sink = io.BytesIO()
    ContentStreamWriter(sink).write_tokens(tokens)
    rewritten = sink.getvalue()

    reparsed = PDFStreamParser(RandomAccessReadBuffer(rewritten)).parse()
    assert len(reparsed) == len(tokens)
    for a, b in zip(tokens, reparsed, strict=True):
        assert _tokens_equal(a, b), f"{a!r} != {b!r}"


def test_round_trip_with_array_operand_tj() -> None:
    src = b"BT\n[(Hello) -100 (World)] TJ\nET\n"
    tokens = PDFStreamParser(RandomAccessReadBuffer(src)).parse()

    sink = io.BytesIO()
    ContentStreamWriter(sink).write_tokens(tokens)
    rewritten = sink.getvalue()

    reparsed = PDFStreamParser(RandomAccessReadBuffer(rewritten)).parse()
    assert len(reparsed) == len(tokens)
    for a, b in zip(tokens, reparsed, strict=True):
        assert _tokens_equal(a, b), f"{a!r} != {b!r}"
