"""Live PDFBox differential parity for COS *scalar* serialisation on write.

Unlike the save-round-trip oracle (a structural-equivalence check), this is a
strict **byte-equality** check: an individual COS leaf object must serialise to
exactly the same bytes Apache PDFBox emits. The serialisation paths exercised
mirror what ``COSWriter`` drives per leaf type:

* ``COSFloat``  → ``COSWriter.visit_from_float`` → ``format_float`` /
  ``format_float_value`` (the classic divergence — float formatting).
* ``COSInteger`` → ``visit_from_integer``.
* ``COSString`` → ``COSWriter.write_string`` (literal ``(...)`` vs hex ``<...>``
  selection + ``( ) \\`` escaping).
* ``COSName`` → ``visit_from_name`` (``#xx`` escaping of non-allowlisted bytes).
* ``COSBoolean`` / ``COSNull`` → the trivial keyword writers.

The Java oracle is ``oracle/probes/WriteScalarProbe.java``, which writes each
scalar through PDFBox's own ``writePDF`` / ``COSWriter.writeString`` and prints
``<spec>: <hex>``. We parse the hex and compare to pypdfbox's bytes.

Float formatting is the headline parity point: PDFBox stores a single-precision
``float`` and serialises via ``Float.toString`` (shortest round-tripping
float32 decimal), expanding to plain notation with trailing zeros stripped only
when the magnitude leaves the ``[1e-3, 1e7)`` window. A naive ``%g`` on the
coerced double leaks float32 representation noise (``0.1`` → ``0.1000000015``);
``COSWriter.format_float`` recovers PDFBox's exact ``0.1``.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSBoolean,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe


def _oracle_bytes(*args: str) -> bytes:
    """Run ``WriteScalarProbe`` and return the written-bytes payload.

    The probe prints ``<echoed-spec>: <hex>``; we split on the last ``": "``
    and decode the hex tail."""
    raw = run_probe("WriteScalarProbe", *args)
    _, _, hex_tail = raw.rpartition(b": ")
    return bytes.fromhex(hex_tail.decode("ascii"))


def _emit(obj: object) -> bytes:
    """Serialise a single COS scalar through ``COSWriter`` exactly as the
    visitor pipeline would, capturing the raw bytes."""
    sink = io.BytesIO()
    writer = COSWriter(sink)
    obj.accept(writer)  # type: ignore[attr-defined]
    writer.close()
    return sink.getvalue()


# ---------------------------------------------------------------- floats ----

# Float values exercised as a freshly constructed ``COSFloat`` (no preserved
# original text), passed to the oracle as decimal text parsed to a Java float.
# Covers: signed zero, exact halves, small/large magnitudes, the float32
# precision boundary, and the Float.toString exponent thresholds (1e-3, 1e7).
_FLOAT_CASES = [
    "0.0",
    "1.5",
    "-0.000123",
    "1000000.0",
    "0.1",
    "0.00001",
    "-0.0",
    "100.0",
    "1e-10",
    "3.14159265358979",
    "123456789.0",
    "1234567.89",
    "2.5",
    "0.5",
    "9999999.0",
    "10000000.0",
    "0.001",
    "0.0009999",
    "0.0000001",
    "32768.0",
    "65535.5",
    "0.3333333",
]


@requires_oracle
@pytest.mark.parametrize("text", _FLOAT_CASES)
def test_float_serialisation_matches_pdfbox(text: str) -> None:
    java = _oracle_bytes("float", text)
    py = _emit(COSFloat(float(text)))
    assert py == java


# String-constructed COSFloat (round-trip / original-form preserving path).
_FLOAT_STRING_CASES = ["1.5", "0.000123", "100", "3.14", "0.0", "-2.0"]


@requires_oracle
@pytest.mark.parametrize("text", _FLOAT_STRING_CASES)
def test_float_string_constructed_matches_pdfbox(text: str) -> None:
    java = _oracle_bytes("floats", text)
    py = _emit(COSFloat(text))
    assert py == java


# -------------------------------------------------------------- integers ----

_INT_CASES = [0, 1, -1, 42, -42, 1000000, 2147483647, -2147483648, 9999999999]


@requires_oracle
@pytest.mark.parametrize("value", _INT_CASES)
def test_integer_serialisation_matches_pdfbox(value: int) -> None:
    java = _oracle_bytes("int", str(value))
    py = _emit(COSInteger.get(value))
    assert py == java


# ----------------------------------------------------------------- names ----

# Names originate from a String upstream (COSName.getPDFName(String)); writePDF
# UTF-8 encodes and #xx-escapes anything outside PDFBox's printable allowlist
# (A-Z a-z 0-9 + - _ @ * $ ; .). Includes delimiters, '#' itself, spaces, and
# non-ASCII (UTF-8 multi-byte).
_NAME_CASES = [
    "Type",
    "My Name",
    "A#B",
    "a(b)c",
    "a/b",
    "a[b]",
    "a<b>",
    "a{b}c",
    "a%b",
    "a#23b",
    "a+b-c_d@e*f$g;h.i",
    "café",
    "Ω",
    "tab\tnewline",
]


@requires_oracle
@pytest.mark.parametrize("name", _NAME_CASES)
def test_name_serialisation_matches_pdfbox(name: str) -> None:
    java = _oracle_bytes("name", name)
    py = _emit(COSName.get_pdf_name(name))
    assert py == java


# --------------------------------------------------------------- strings ----

# Hex spec → raw bytes. Exercises the literal-vs-hex selection rule
# (hex when any byte >= 0x80 or is CR/LF; else literal with ( ) \ escaping)
# plus the escaping of parens / backslash and the raw emission of other
# control bytes (tab, DEL) inside literal form.
_STRING_LITERAL_CASES = [
    ("hello", "48656c6c6f"),
    ("parens", "2829"),
    ("backslash", "5c"),
    ("mixed_escapes", "612862295c63"),
    ("binary_low", "00010203"),
    ("crlf", "0d0a"),
    ("high_byte", "ff"),
    ("ascii_then_high", "414243e9"),
    ("tab", "09"),
    ("del", "7f"),
    ("empty", ""),
    ("nul_only", "00"),
]


@requires_oracle
@pytest.mark.parametrize(
    "hex_bytes",
    [c[1] for c in _STRING_LITERAL_CASES],
    ids=[c[0] for c in _STRING_LITERAL_CASES],
)
def test_string_literal_selection_matches_pdfbox(hex_bytes: str) -> None:
    java = _oracle_bytes("strlit", hex_bytes)
    py = _emit(COSString(bytes.fromhex(hex_bytes)))
    assert py == java


_STRING_HEX_CASES = [
    ("hello", "48656c6c6f"),
    ("parens", "2829"),
    ("binary", "00010203"),
    ("high_byte", "ff"),
]


@requires_oracle
@pytest.mark.parametrize(
    "hex_bytes",
    [c[1] for c in _STRING_HEX_CASES],
    ids=[c[0] for c in _STRING_HEX_CASES],
)
def test_string_forced_hex_matches_pdfbox(hex_bytes: str) -> None:
    java = _oracle_bytes("strhex", hex_bytes)
    s = COSString(bytes.fromhex(hex_bytes))
    s.set_force_hex_form(True)
    py = _emit(s)
    assert py == java


# ----------------------------------------------------- booleans and null ----


@requires_oracle
@pytest.mark.parametrize(
    ("flag", "obj"),
    [("true", COSBoolean.TRUE), ("false", COSBoolean.FALSE)],
)
def test_boolean_serialisation_matches_pdfbox(flag: str, obj: COSBoolean) -> None:
    java = _oracle_bytes("bool", flag)
    assert _emit(obj) == java


@requires_oracle
def test_null_serialisation_matches_pdfbox() -> None:
    java = _oracle_bytes("null")
    assert _emit(COSNull.NULL) == java
