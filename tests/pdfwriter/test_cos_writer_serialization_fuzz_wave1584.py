"""Wave 1584 — COSWriter per-object serialization fuzz.

Hammers the ``visit_from_*`` / ``write_string`` leaf-serialization paths of
``pypdfbox.pdfwriter.cos_writer.COSWriter`` and asserts the exact emitted bytes
against the contract of upstream ``org.apache.pdfbox.pdfwriter.COSWriter``
(PDFBox 3.0.7):

* COSString literal ``(...)`` form with ``( ) \\`` escaping; hex ``<...>`` form
  forced by bytes >= 0x80, CR/LF (PDFBOX-3107), or ``set_force_hex_form(True)``.
* COSName ``/Name`` with ``#xx`` escaping of bytes outside the PDFBox printable
  allowlist (A-Z a-z 0-9 + - _ @ * $ ; .).
* COSArray ``[a b c]`` — single space between elements, EOL after the 10th, NO
  trailing separator before ``]`` (upstream guards the separator with
  ``if (i.hasNext())``).
* COSDictionary ``<<\\n/Key value\\n>>\\n`` framing + key ordering.
* COSBoolean ``true``/``false``, COSNull ``null``.
* COSStream — dictionary, then ``stream\\r\\n`` + body + ``\\r\\nendstream\\n``,
  with ``/Length`` synced to the emitted body and hoisted to first entry.
* indirect reference ``N G R``.
* empty string / array / dict edge cases.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter


def _emit(callback) -> bytes:
    """Run ``callback(writer)`` and capture the raw written bytes."""
    sink = io.BytesIO()
    writer = COSWriter(sink)
    callback(writer)
    writer.close()
    return sink.getvalue()


def _emit_string(s: COSString) -> bytes:
    sink = io.BytesIO()
    out = sink  # write_string accepts any write(bytes) sink
    COSWriter.write_string(s, out)
    return sink.getvalue()


# ---------------------------------------------------------------------------
# COSString — literal vs hex form + escaping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"hi", b"(hi)"),
        (b"", b"()"),
        (b"a(b", b"(a\\(b)"),
        (b"a)b", b"(a\\)b)"),
        (b"a\\b", b"(a\\\\b)"),
        (b"()\\", b"(\\(\\)\\\\)"),
        # tab (0x09) is < 0x80 and not CR/LF -> stays literal, NOT escaped
        (b"a\tb", b"(a\tb)"),
        # form-feed (0x0C) and backspace (0x08) also stay literal unescaped
        (b"a\x0cb", b"(a\x0cb)"),
        (b"a\x08b", b"(a\x08b)"),
        # NUL byte is < 0x80 -> literal, written raw
        (b"a\x00b", b"(a\x00b)"),
    ],
    ids=[
        "ascii",
        "empty",
        "lparen",
        "rparen",
        "backslash",
        "all_three_specials",
        "tab_literal",
        "formfeed_literal",
        "backspace_literal",
        "nul_literal",
    ],
)
def test_string_literal_form(raw: bytes, expected: bytes) -> None:
    assert _emit_string(COSString(raw)) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # CR (0x0D) forces hex (PDFBOX-3107)
        (b"a\rb", b"<610D62>"),
        # LF (0x0A) forces hex
        (b"a\nb", b"<610A62>"),
        # high byte (>= 0x80) forces hex
        (b"\x80", b"<80>"),
        (b"\xff\x00", b"<FF00>"),
        (b"caf\xe9", b"<636166E9>"),
        # empty stays literal even in non-forced path
    ],
    ids=["cr", "lf", "high_0x80", "high_then_nul", "latin1_e9"],
)
def test_string_hex_form_auto(raw: bytes, expected: bytes) -> None:
    assert _emit_string(COSString(raw)) == expected


def test_string_force_hex_form_overrides_ascii() -> None:
    s = COSString(b"hi")
    s.set_force_hex_form(True)
    assert _emit_string(s) == b"<6869>"


def test_string_force_hex_empty() -> None:
    s = COSString(b"")
    s.set_force_hex_form(True)
    assert _emit_string(s) == b"<>"


def test_string_hex_is_uppercase() -> None:
    # 0xab,0xcd must render uppercase ABCD, not abcd.
    assert _emit_string(COSString(b"\xab\xcd")) == b"<ABCD>"


def test_string_via_visitor_matches_write_string() -> None:
    # visit_from_string (no encryption) routes through write_string.
    out = _emit(lambda w: COSString(b"a(b").accept(w))
    assert out == b"(a\\(b)"


def test_bytes_input_always_literal_unless_eol() -> None:
    # The byte[] overload: bytes-like input, force_hex defaults False.
    sink = io.BytesIO()
    COSWriter.write_string(b"plain", sink)
    assert sink.getvalue() == b"(plain)"


# ---------------------------------------------------------------------------
# COSName — #xx escaping on write
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Type", b"/Type"),
        ("Foo.Bar", b"/Foo.Bar"),  # '.' is in the allowlist
        ("A-b_c@d*e$f;g", b"/A-b_c@d*e$f;g"),  # all allowlisted punctuation
        ("AB+12", b"/AB+12"),  # '+' allowlisted, digits allowlisted
        ("with space", b"/with#20space"),  # space -> #20
        ("a#b", b"/a#23b"),  # '#' itself -> #23
        ("a/b", b"/a#2Fb"),  # '/' -> #2F
        ("a(b", b"/a#28b"),  # '(' -> #28
        ("a)b", b"/a#29b"),  # ')' -> #29
        ("a<b", b"/a#3Cb"),  # '<' -> #3C
        ("a%b", b"/a#25b"),  # '%' -> #25
        ("", b"/"),  # empty name -> just the slash
    ],
    ids=[
        "type",
        "dot",
        "allowlist_punct",
        "plus_digits",
        "space",
        "hash",
        "slash",
        "lparen",
        "rparen",
        "lt",
        "percent",
        "empty",
    ],
)
def test_name_escaping(name: str, expected: bytes) -> None:
    assert _emit(lambda w, n=name: COSName.get_pdf_name(n).accept(w)) == expected


def test_name_hex_escape_is_uppercase() -> None:
    # 0x7e '~' is outside the allowlist -> #7E (uppercase hex digits).
    assert _emit(lambda w: COSName.get_pdf_name("~").accept(w)) == b"/#7E"


# ---------------------------------------------------------------------------
# COSBoolean / COSNull
# ---------------------------------------------------------------------------


def test_boolean_true() -> None:
    assert _emit(lambda w: COSBoolean.TRUE.accept(w)) == b"true"


def test_boolean_false() -> None:
    assert _emit(lambda w: COSBoolean.FALSE.accept(w)) == b"false"


def test_null() -> None:
    assert _emit(lambda w: COSNull.NULL.accept(w)) == b"null"


# ---------------------------------------------------------------------------
# COSArray — spacing, every-10th EOL, no trailing separator
# ---------------------------------------------------------------------------


def test_array_empty() -> None:
    assert _emit(lambda w: w.visit_from_array(COSArray())) == b"[]\n"


def test_array_scalars_single_space_no_trailing() -> None:
    a = COSArray.of_cos_integers([1, 2, 3])
    assert _emit(lambda w: w.visit_from_array(a)) == b"[1 2 3]\n"


def test_array_one_element_no_separator() -> None:
    a = COSArray()
    a.add(COSInteger.get(42))
    assert _emit(lambda w: w.visit_from_array(a)) == b"[42]\n"


def test_array_tenth_element_gets_eol() -> None:
    a = COSArray.of_cos_integers(list(range(12)))
    assert (
        _emit(lambda w: w.visit_from_array(a))
        == b"[0 1 2 3 4 5 6 7 8 9\n10 11]\n"
    )


def test_array_exactly_ten_no_trailing_eol() -> None:
    # 10 elements: EOL would land after the 10th, but it's the last element
    # so the separator is suppressed -> no trailing EOL inside the brackets.
    a = COSArray.of_cos_integers(list(range(10)))
    assert (
        _emit(lambda w: w.visit_from_array(a)) == b"[0 1 2 3 4 5 6 7 8 9]\n"
    )


def test_array_mixed_types() -> None:
    a = COSArray()
    a.add(COSName.get_pdf_name("Foo"))
    a.add(COSInteger.get(7))
    a.add(COSBoolean.TRUE)
    a.add(COSNull.NULL)
    a.add(COSString(b"hi"))
    assert _emit(lambda w: w.visit_from_array(a)) == b"[/Foo 7 true null (hi)]\n"


def test_array_none_element_is_null() -> None:
    a = COSArray()
    a.add(COSInteger.get(1))
    a.add(None)
    a.add(COSInteger.get(3))
    assert _emit(lambda w: w.visit_from_array(a)) == b"[1 null 3]\n"


def test_array_nested_direct() -> None:
    inner = COSArray.of_cos_integers([1, 2])
    outer = COSArray()
    outer.add(inner)
    outer.add(COSInteger.get(3))
    # inner array emits its own trailing EOL before the outer SPACE.
    assert _emit(lambda w: w.visit_from_array(outer)) == b"[[1 2]\n 3]\n"


def test_array_float_element() -> None:
    a = COSArray()
    a.add(COSFloat(0.5))
    a.add(COSInteger.get(2))
    assert _emit(lambda w: w.visit_from_array(a)) == b"[0.5 2]\n"


# ---------------------------------------------------------------------------
# COSDictionary — framing, ordering, nesting
# ---------------------------------------------------------------------------


def test_dict_empty() -> None:
    assert _emit(lambda w: w.visit_from_dictionary(COSDictionary())) == b"<<\n>>\n"


def test_dict_single_entry() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))
    assert (
        _emit(lambda w: w.visit_from_dictionary(d)) == b"<<\n/Type /Catalog\n>>\n"
    )


def test_dict_preserves_insertion_order() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("B"), COSInteger.get(2))
    d.set_item(COSName.get_pdf_name("A"), COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("C"), COSInteger.get(3))
    assert (
        _emit(lambda w: w.visit_from_dictionary(d))
        == b"<<\n/B 2\n/A 1\n/C 3\n>>\n"
    )


def test_dict_skips_none_values() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("A"), COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("B"), None)
    d.set_item(COSName.get_pdf_name("C"), COSInteger.get(3))
    assert _emit(lambda w: w.visit_from_dictionary(d)) == b"<<\n/A 1\n/C 3\n>>\n"


def test_dict_with_direct_array_value() -> None:
    d = COSDictionary()
    box = COSArray.of_cos_integers([0, 0, 612, 792])
    d.set_item(COSName.get_pdf_name("MediaBox"), box)
    assert (
        _emit(lambda w: w.visit_from_dictionary(d))
        == b"<<\n/MediaBox [0 0 612 792]\n>>\n"
    )


def test_dict_with_string_value_escaped() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Title"), COSString(b"Hello (PDF)"))
    assert (
        _emit(lambda w: w.visit_from_dictionary(d))
        == b"<<\n/Title (Hello \\(PDF\\))\n>>\n"
    )


def test_dict_nested_direct_dict() -> None:
    inner = COSDictionary()
    inner.set_item(COSName.get_pdf_name("X"), COSInteger.get(1))
    inner.set_direct(True)
    outer = COSDictionary()
    outer.set_item(COSName.get_pdf_name("Inner"), inner)
    assert (
        _emit(lambda w: w.visit_from_dictionary(outer))
        == b"<<\n/Inner <<\n/X 1\n>>\n>>\n"
    )


# ---------------------------------------------------------------------------
# COSStream — dict + stream/endstream + /Length sync + EOL
# ---------------------------------------------------------------------------


def test_stream_length_synced_and_framing() -> None:
    stream = COSStream()
    with stream.create_output_stream() as os:
        os.write(b"hello world")
    out = _emit(lambda w: w.visit_from_stream(stream))
    # /Length is hoisted to the first dict entry and equals the body length.
    assert out == (
        b"<<\n/Length 11\n>>\n"
        b"stream\r\n"
        b"hello world\r\n"
        b"endstream\n"
    )


def test_stream_empty_body_length_zero() -> None:
    stream = COSStream()
    out = _emit(lambda w: w.visit_from_stream(stream))
    assert out == (
        b"<<\n/Length 0\n>>\n"
        b"stream\r\n"
        b"\r\n"
        b"endstream\n"
    )


def test_stream_length_hoisted_to_front() -> None:
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("Custom"))
    with stream.create_output_stream() as os:
        os.write(b"abc")
    out = _emit(lambda w: w.visit_from_stream(stream))
    # /Length must precede /Type even though /Type was set first.
    assert out == (
        b"<<\n/Length 3\n/Type /Custom\n>>\n"
        b"stream\r\n"
        b"abc\r\n"
        b"endstream\n"
    )


def test_stream_uses_crlf_around_body() -> None:
    stream = COSStream()
    with stream.create_output_stream() as os:
        os.write(b"X")
    out = _emit(lambda w: w.visit_from_stream(stream))
    # exactly CR LF after "stream" and before "endstream".
    assert b"stream\r\nX\r\nendstream" in out


# ---------------------------------------------------------------------------
# Indirect reference — N G R format
# ---------------------------------------------------------------------------


def test_reference_format() -> None:
    # A dictionary value that is indirect emits "N 0 R".
    inner = COSDictionary()
    inner.set_item(COSName.get_pdf_name("X"), COSInteger.get(1))
    # leave indirect (default) so it becomes a reference
    outer = COSDictionary()
    outer.set_item(COSName.get_pdf_name("Ref"), inner)
    out = _emit(lambda w: w.visit_from_dictionary(outer))
    assert out == b"<<\n/Ref 1 0 R\n>>\n"


def test_reference_array_of_refs() -> None:
    d1 = COSDictionary()
    d1.set_item(COSName.get_pdf_name("A"), COSInteger.get(1))
    d2 = COSDictionary()
    d2.set_item(COSName.get_pdf_name("B"), COSInteger.get(2))
    a = COSArray()
    a.add(d1)
    a.add(d2)
    out = _emit(lambda w: w.visit_from_array(a))
    assert out == b"[1 0 R 2 0 R]\n"
