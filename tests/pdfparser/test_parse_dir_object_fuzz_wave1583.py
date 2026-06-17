"""Fuzz / differential coverage for the BaseParser direct-object dispatcher.

Targets ``BaseParser.parse_dir_object`` (the COS direct-object dispatcher)
together with ``parse_cos_dictionary`` / ``parse_cos_array`` /
``parse_cos_number`` / ``parse_cos_dictionary_value``. Each case asserts the
behaviour of upstream PDFBox 3.0.7 ``BaseParser.parseDirObject`` /
``parseCOSDictionary`` / ``parseCOSArray`` (the lenient tokenizer dispatch):

* ``<<`` -> dictionary, lone ``<`` -> hex string (the
  ``parseDirObject`` ``'<'`` disambiguation, Java line ~983);
* ``[`` -> array, ``(`` -> literal string, ``/`` -> name;
* digit / sign / ``.`` -> number;
* ``true`` / ``false`` / ``null`` keyword primitives;
* the ``num gen R`` indirect-reference detection — handled post-hoc in
  ``parseCOSArray`` (PDFBOX-385) and inline in ``parseCOSDictionaryValue``;
* lenient recovery on unclosed / malformed containers.

These are hand-written pypdfbox tests (not a 1:1 JUnit port), so no
PROVENANCE row is required.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError


def parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


@pytest.fixture
def doc_parser() -> Iterator:
    """Factory yielding a ``BaseParser`` bound to a fresh ``COSDocument`` so
    ``num gen R`` references can be resolved through the object pool.

    Without a bound document upstream ``getObjectFromPool`` raises
    ``IOException`` for a content-stream reference; pypdfbox mirrors that with
    ``PDFParseError`` (covered separately). Closes each created document on
    teardown to silence the unclosed-document warning."""
    from pypdfbox.cos import COSDocument

    created: list[COSDocument] = []

    def make(data: bytes) -> BaseParser:
        p = parser(data)
        document = COSDocument()
        created.append(document)
        p._document = document
        return p

    yield make
    for document in created:
        document.close()


# --------------------------------------------------------------------------
# dictionary dispatch
# --------------------------------------------------------------------------


def test_simple_dictionary_with_array_value() -> None:
    from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

    obj = parser(b"<< /A 1 /B [2 3] >>").parse_dir_object()
    assert isinstance(obj, COSDictionary)
    assert obj.get_int(COSName.get_pdf_name("A")) == 1
    b = obj.get_item(COSName.get_pdf_name("B"))
    assert isinstance(b, COSArray)
    assert [x.value for x in b if isinstance(x, COSInteger)] == [2, 3]


def test_nested_dictionary_and_array() -> None:
    from pypdfbox.cos import COSArray, COSDictionary, COSName

    obj = parser(b"<< /A << /B [1 [2 3]] >> >>").parse_dir_object()
    assert isinstance(obj, COSDictionary)
    inner = obj.get_item(COSName.get_pdf_name("A"))
    assert isinstance(inner, COSDictionary)
    deep = inner.get_item(COSName.get_pdf_name("B"))
    assert isinstance(deep, COSArray)
    assert isinstance(deep.get(1), COSArray)


def test_empty_dictionary() -> None:
    from pypdfbox.cos import COSDictionary

    obj = parser(b"<<>>").parse_dir_object()
    assert isinstance(obj, COSDictionary)
    assert len(obj) == 0


def test_dictionary_marks_itself_direct() -> None:
    # parseDirObject -> parseCOSDictionary(true): inline dictionaries are
    # direct objects.
    from pypdfbox.cos import COSDictionary

    obj = parser(b"<< /A 1 >>").parse_dir_object()
    assert isinstance(obj, COSDictionary)
    assert obj.is_direct()


def test_dictionary_value_marked_direct() -> None:
    from pypdfbox.cos import COSInteger, COSName

    obj = parser(b"<< /A 1 >>").parse_dir_object()
    val = obj.get_item(COSName.get_pdf_name("A"))
    assert isinstance(val, COSInteger)
    assert val.is_direct()


# --------------------------------------------------------------------------
# '<<' vs '<' disambiguation
# --------------------------------------------------------------------------


def test_hex_string_not_dictionary() -> None:
    from pypdfbox.cos import COSString

    obj = parser(b"<48656C6C6F>").parse_dir_object()
    assert isinstance(obj, COSString)
    assert obj.get_bytes() == b"Hello"


def test_empty_hex_string() -> None:
    from pypdfbox.cos import COSString

    obj = parser(b"<>").parse_dir_object()
    assert isinstance(obj, COSString)
    assert obj.get_bytes() == b""


def test_double_lt_is_dictionary_not_hex() -> None:
    from pypdfbox.cos import COSDictionary

    obj = parser(b"<</X 1>>").parse_dir_object()
    assert isinstance(obj, COSDictionary)


def test_lone_lt_at_eof_raises() -> None:
    # '<' not followed by a second '<' -> hex string parse, which hits EOF
    # before the closing '>'.
    with pytest.raises(PDFParseError):
        parser(b"<").parse_dir_object()


def test_hex_string_dispatch_does_not_consume_extra() -> None:
    p = parser(b"<41>/Next")
    obj = p.parse_dir_object()
    from pypdfbox.cos import COSString

    assert isinstance(obj, COSString)
    # position is right after '>' so the next token is the name.
    nxt = p.parse_dir_object()
    from pypdfbox.cos import COSName

    assert isinstance(nxt, COSName)
    assert nxt.get_name() == "Next"


# --------------------------------------------------------------------------
# literal string / name dispatch
# --------------------------------------------------------------------------


def test_literal_string_dispatch() -> None:
    from pypdfbox.cos import COSString

    obj = parser(b"(hello world)").parse_dir_object()
    assert isinstance(obj, COSString)
    assert obj.get_bytes() == b"hello world"


def test_name_dispatch() -> None:
    from pypdfbox.cos import COSName

    obj = parser(b"/Type").parse_dir_object()
    assert isinstance(obj, COSName)
    assert obj.get_name() == "Type"


def test_name_with_hex_escape() -> None:
    from pypdfbox.cos import COSName

    obj = parser(b"/A#42C").parse_dir_object()
    assert isinstance(obj, COSName)
    assert obj.get_name() == "ABC"


# --------------------------------------------------------------------------
# keyword primitives
# --------------------------------------------------------------------------


def test_true_false_null() -> None:
    from pypdfbox.cos import COSBoolean, COSNull

    assert parser(b"true ").parse_dir_object() is COSBoolean.TRUE
    assert parser(b"false ").parse_dir_object() is COSBoolean.FALSE
    assert parser(b"null ").parse_dir_object() is COSNull.NULL


def test_true_at_eof() -> None:
    from pypdfbox.cos import COSBoolean

    assert parser(b"true").parse_dir_object() is COSBoolean.TRUE


def test_keyword_prefix_mismatch_raises() -> None:
    # 'n' must be followed by 'ull' (readExpectedString) -> any mismatch is a
    # hard parse error in upstream.
    with pytest.raises(PDFParseError):
        parser(b"nope").parse_dir_object()


# --------------------------------------------------------------------------
# number dispatch (int / real / sign)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"0", 0),
        (b"42", 42),
        (b"+7", 7),
        (b"-13", -13),
        (b"00123", 123),
    ],
    ids=["zero", "int", "plus", "minus", "leading_zeros"],
)
def test_integer_values(data: bytes, expected: int) -> None:
    from pypdfbox.cos import COSInteger

    obj = parser(data).parse_dir_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"3.14", 3.14),
        (b"-3.14", -3.14),
        (b".5", 0.5),
        (b"5.", 5.0),
        (b"-.5", -0.5),
    ],
    ids=["pi", "neg_pi", "leading_dot", "trailing_dot", "neg_leading_dot"],
)
def test_real_values(data: bytes, expected: float) -> None:
    from pypdfbox.cos import COSFloat

    obj = parser(data).parse_dir_object()
    assert isinstance(obj, COSFloat)
    assert obj.value == pytest.approx(expected)


def test_number_not_followed_by_g_r_is_plain_integer() -> None:
    # A bare number must dispatch to parseCOSNumber, not the indirect-ref path
    # (which is only assembled by the array/dict value parsers).
    from pypdfbox.cos import COSInteger

    obj = parser(b"42 ").parse_dir_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == 42


def test_number_then_endobj_keyword_recovery() -> None:
    # PDFBOX-5025 style: '74191endobj' -> integer 74191 with the 'endobj'
    # token preserved for the caller (a trailing 'e' is rewound).
    from pypdfbox.cos import COSInteger

    p = parser(b"74191endobj")
    obj = p.parse_dir_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == 74191
    assert p.read_keyword() == b"endobj"


# --------------------------------------------------------------------------
# arrays — mixed types, nesting, indirect refs
# --------------------------------------------------------------------------


def test_array_mixed_types() -> None:
    from pypdfbox.cos import (
        COSArray,
        COSBoolean,
        COSFloat,
        COSInteger,
        COSName,
        COSNull,
        COSString,
    )

    obj = parser(b"[1 2.5 /Nm (s) true null]").parse_dir_object()
    assert isinstance(obj, COSArray)
    assert [type(x) for x in obj] == [
        COSInteger,
        COSFloat,
        COSName,
        COSString,
        COSBoolean,
        COSNull,
    ]


def test_empty_array() -> None:
    from pypdfbox.cos import COSArray

    obj = parser(b"[]").parse_dir_object()
    assert isinstance(obj, COSArray)
    assert len(obj) == 0


def test_array_of_three_integers_is_not_a_reference(doc_parser) -> None:
    # '1 2 3' inside an array stays three integers (no trailing R).
    from pypdfbox.cos import COSInteger

    obj = doc_parser(b"[1 2 3]").parse_dir_object()
    assert [x.value for x in obj if isinstance(x, COSInteger)] == [1, 2, 3]


def test_array_indirect_reference(doc_parser) -> None:
    from pypdfbox.cos import COSArray, COSInteger, COSObject

    obj = doc_parser(b"[1 0 R 5]").parse_dir_object()
    assert isinstance(obj, COSArray)
    assert len(obj) == 2
    ref = obj.get(0)
    assert isinstance(ref, COSObject)
    assert ref.object_number == 1
    assert ref.generation_number == 0
    assert isinstance(obj.get(1), COSInteger)


def test_array_two_indirect_references(doc_parser) -> None:
    from pypdfbox.cos import COSName, COSObject

    obj = doc_parser(b"[1 0 R 2 0 R /N]").parse_dir_object()
    assert len(obj) == 3
    assert isinstance(obj.get(0), COSObject)
    assert isinstance(obj.get(1), COSObject)
    assert isinstance(obj.get(2), COSName)


def test_array_bare_r_with_one_preceding_int_recovers(doc_parser) -> None:
    # A bare 'R' (no second integer) -> parseDirObject returns a placeholder
    # COSObject; parseCOSArray finds only one preceding integer so it nulls
    # the element (PDFBOX-385) and the recovery branch fires.
    from pypdfbox.cos import COSArray, COSInteger

    obj = doc_parser(b"[5 R]").parse_dir_object()
    assert isinstance(obj, COSArray)
    assert len(obj) == 1
    assert isinstance(obj.get(0), COSInteger)
    assert obj.get(0).value == 5


def test_array_bare_r_at_start_recovers(doc_parser) -> None:
    from pypdfbox.cos import COSInteger

    obj = doc_parser(b"[R 1 2]").parse_dir_object()
    assert [x.value for x in obj if isinstance(x, COSInteger)] == [1, 2]


def test_array_indirect_reference_without_document_raises() -> None:
    # No bound document -> getObjectFromPool cannot resolve the content-stream
    # reference (upstream IOException -> PDFParseError).
    with pytest.raises(PDFParseError):
        parser(b"[1 0 R]").parse_dir_object()


def test_nested_array() -> None:
    from pypdfbox.cos import COSArray

    obj = parser(b"[[1 2] [3 [4]]]").parse_dir_object()
    assert isinstance(obj, COSArray)
    assert len(obj) == 2
    assert all(isinstance(x, COSArray) for x in obj)


# --------------------------------------------------------------------------
# dictionary values — indirect refs and the 'num gen R' lookahead
# --------------------------------------------------------------------------


def test_dictionary_with_indirect_reference_value(doc_parser) -> None:
    from pypdfbox.cos import COSName, COSObject

    obj = doc_parser(b"<</K 3 0 R /N 9>>").parse_dir_object()
    ref = obj.get_item(COSName.get_pdf_name("K"))
    assert isinstance(ref, COSObject)
    assert ref.object_number == 3
    assert obj.get_int(COSName.get_pdf_name("N")) == 9


def test_dictionary_num_then_int_without_r_raises(doc_parser) -> None:
    # '3 0' as a value: parseCOSDictionaryValue sees a number followed by a
    # digit, parses the generation, then readExpectedChar('R') fails on '>'.
    with pytest.raises(PDFParseError):
        doc_parser(b"<</K 3 0>>").parse_dir_object()


def test_dictionary_non_integer_generation_is_null(doc_parser) -> None:
    # '3 0.5 R': the generation token is a float, not a COSInteger -> the
    # value collapses to COSNull (upstream logs + returns COSNull.NULL).
    from pypdfbox.cos import COSName, COSNull

    obj = doc_parser(b"<</K 3 0.5 R /N 1>>").parse_dir_object()
    assert obj.get_item(COSName.get_pdf_name("K")) is COSNull.NULL
    assert obj.get_int(COSName.get_pdf_name("N")) == 1


def test_dictionary_negative_second_number_is_not_a_reference() -> None:
    # isDigit() gates the 'num gen' lookahead; a leading '-' is not a digit so
    # '1' is taken as a plain value and the stray '-2' triggers the malformed
    # recovery path (no crash).
    from pypdfbox.cos import COSDictionary, COSInteger, COSName

    obj = parser(b"<< /A 1 -2 >>").parse_dir_object()
    assert isinstance(obj, COSDictionary)
    a = obj.get_item(COSName.get_pdf_name("A"))
    assert isinstance(a, COSInteger)
    assert a.value == 1


# --------------------------------------------------------------------------
# stream keyword after a dictionary
# --------------------------------------------------------------------------


def test_dictionary_stops_at_stream_keyword() -> None:
    # parseCOSDictionary stops at '>>'; the 'stream' keyword is left for the
    # caller (PDFParser handles the stream body).
    from pypdfbox.cos import COSDictionary, COSName

    p = parser(b"<< /Length 5 >>stream")
    obj = p.parse_dir_object()
    assert isinstance(obj, COSDictionary)
    assert obj.get_int(COSName.get_pdf_name("Length")) == 5
    assert p.read_keyword() == b"stream"


# --------------------------------------------------------------------------
# lenient recovery on malformed / unclosed containers
# --------------------------------------------------------------------------


def test_unclosed_dictionary_is_lenient() -> None:
    # EOF before '>>' -> upstream returns the partial dictionary (logs a
    # warning) rather than raising.
    from pypdfbox.cos import COSDictionary, COSInteger, COSName

    obj = parser(b"<< /A 1").parse_dir_object()
    assert isinstance(obj, COSDictionary)
    a = obj.get_item(COSName.get_pdf_name("A"))
    assert isinstance(a, COSInteger)
    assert a.value == 1


def test_unclosed_array_is_lenient() -> None:
    # EOF before ']' -> the partial array is returned.
    from pypdfbox.cos import COSArray

    obj = parser(b"[1 2 3").parse_dir_object()
    assert isinstance(obj, COSArray)
    assert [x.value for x in obj] == [1, 2, 3]


def test_dictionary_non_slash_entry_triggers_recovery() -> None:
    # A non-'/' byte where a key is expected fires
    # readUntilEndOfCOSDictionary; the recovery still produces a dictionary.
    from pypdfbox.cos import COSDictionary

    obj = parser(b"<< /A 1 bad >>").parse_dir_object()
    assert isinstance(obj, COSDictionary)


def test_eof_returns_none() -> None:
    # Empty input -> parseDirObject returns None at EOF.
    assert parser(b"").parse_dir_object() is None


def test_whitespace_only_returns_none() -> None:
    assert parser(b"   \n\t ").parse_dir_object() is None


def test_endobj_keyword_returns_none_and_rewinds() -> None:
    # An unexpected 'endobj' token at dir-object position is rewound and None
    # is returned so the outer caller sees the terminator.
    p = parser(b"endobj")
    assert p.parse_dir_object() is None
    assert p.read_keyword() == b"endobj"
