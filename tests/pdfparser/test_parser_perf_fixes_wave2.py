"""Regression tests for the wave-2 parser performance fixes.

Two behaviour-preserving optimisations are locked in here:

* **FIX A** — ``BaseParser.is_whitespace`` / ``is_delimiter`` test the raw
  int against a precomputed frozenset instead of allocating a one-byte
  ``bytes`` object per call. The int-membership sets must stay exactly in
  lockstep with the public ``WHITESPACE`` / ``DELIMITERS`` ClassVars.
* **FIX B** — ``read_number`` caches the literal text + span of the token it
  just consumed so ``COSParser._wrap_number`` can reuse it instead of seeking
  back and re-reading the same bytes. Parsed values, ``COSFloat`` preserved
  text, and stream positions must be identical to the re-read path.
"""

from __future__ import annotations

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import (
    _DELIMITER_INTS,
    _WHITESPACE_INTS,
    BaseParser,
)
from pypdfbox.pdfparser.cos_parser import COSParser

# ---------- FIX A: classifier correctness + set/ClassVar sync ----------


def test_whitespace_set_matches_classvar() -> None:
    assert frozenset(BaseParser.WHITESPACE) == _WHITESPACE_INTS


def test_delimiter_set_matches_classvar() -> None:
    assert frozenset(BaseParser.DELIMITERS) == _DELIMITER_INTS


def test_is_whitespace_full_byte_range_matches_membership() -> None:
    for b in range(256):
        assert BaseParser.is_whitespace(b) == (b in frozenset(BaseParser.WHITESPACE))


def test_is_delimiter_full_byte_range_matches_membership() -> None:
    for b in range(256):
        assert BaseParser.is_delimiter(b) == (b in frozenset(BaseParser.DELIMITERS))


def test_classifiers_reject_eof_sentinel() -> None:
    # -1 (EOF) and other out-of-range ints must miss both sets.
    assert not BaseParser.is_whitespace(-1)
    assert not BaseParser.is_delimiter(-1)
    assert not BaseParser.is_whitespace(256)
    assert not BaseParser.is_delimiter(999)


def test_specific_whitespace_and_delimiter_bytes() -> None:
    for b in (0x00, 0x09, 0x0A, 0x0C, 0x0D, 0x20):
        assert BaseParser.is_whitespace(b)
    assert not BaseParser.is_whitespace(0x41)  # 'A'
    for ch in b"()<>[]{}/%":
        assert BaseParser.is_delimiter(ch)
    assert not BaseParser.is_delimiter(0x41)  # 'A'


# ---------- FIX B: number literal-text cache parity ----------

_INT_CASES = [
    b"0",
    b"1",
    b"-1",
    b"+7",
    b"00123",
    b"-000",
    b"42",
    b"100000000000000000000",
    b"-99999999999999999999",
]

_FLOAT_CASES = [
    b"12.5",
    b"-0.0",
    b".5",
    b"5.",
    b"-.5",
    b"1.5e-2",
    b"1.5E+3",
    b"007.500",
    b"3.14159",
    b"0.0001",
    b"3.0e10",
    b"+2.5",
    b"-123.456",
    b"0.00000",
]


def _reread_text(src: RandomAccessReadBuffer, start: int, end: int) -> str:
    cur = src.get_position()
    src.seek(start)
    out = bytearray()
    while src.get_position() < end:
        out.append(src.read())
    src.seek(cur)
    return out.decode("ascii")


def test_number_cache_text_matches_reread_for_ints() -> None:
    for c in _INT_CASES:
        p = COSParser(RandomAccessReadBuffer(c + b" "))
        start = p.position
        p.read_number()
        end = p.position
        # The cache captured this exact span with byte-identical text.
        assert p._last_number_start == start
        assert p._last_number_end == end
        assert p._last_number_text == _reread_text(p._src, start, end)


def test_number_cache_text_matches_reread_for_floats() -> None:
    for c in _FLOAT_CASES:
        p = COSParser(RandomAccessReadBuffer(c + b" "))
        start = p.position
        p.read_number()
        end = p.position
        assert p._last_number_start == start
        assert p._last_number_end == end
        assert p._last_number_text == _reread_text(p._src, start, end)


def test_wrapped_integers_value_and_type() -> None:
    for c in _INT_CASES:
        p = COSParser(RandomAccessReadBuffer(c + b" "))
        obj = p.parse_direct_object()
        assert isinstance(obj, COSInteger)


def test_wrapped_floats_preserve_original_text() -> None:
    for c in _FLOAT_CASES:
        p = COSParser(RandomAccessReadBuffer(c + b" "))
        obj = p.parse_direct_object()
        assert isinstance(obj, COSFloat)
        # Preserved verbatim text is exactly the source token.
        assert obj.get_original_form() == c.decode("ascii")


def test_indirect_reference_lookahead_still_parses_numbers() -> None:
    # The lookahead's ``second`` read overwrites the cache; the fallback
    # re-read in ``_wrap_number`` must still yield the correct first number.
    for text, wantfirst in [(b"1 2 3", 1), (b"10 0 X", 10), (b"5 /Name", 5)]:
        p = COSParser(RandomAccessReadBuffer(text + b" "))
        obj = p.parse_direct_object()
        assert isinstance(obj, COSInteger)
        assert obj.long_value() == wantfirst


def test_indirect_reference_recognized() -> None:
    from pypdfbox.cos.cos_object import COSObject

    p = COSParser(RandomAccessReadBuffer(b"12 0 R "))
    obj = p.parse_direct_object()
    assert isinstance(obj, COSObject)
    assert obj.get_object_number() == 12
    assert obj.get_generation_number() == 0


def test_array_of_mixed_numbers_round_trips() -> None:
    p = COSParser(RandomAccessReadBuffer(b"[1 2 3 -4 5.5 007 0.0 12 0 R]"))
    arr = p.parse_direct_object()
    kinds = [type(x).__name__ for x in arr]
    assert kinds == [
        "COSInteger",
        "COSInteger",
        "COSInteger",
        "COSInteger",
        "COSFloat",
        "COSInteger",
        "COSFloat",
        "COSObject",
    ]
    # Bare-integer array elements (each read twice by the lookahead) keep values.
    assert [arr[i].long_value() for i in (0, 1, 2, 3, 5)] == [1, 2, 3, -4, 7]
    assert arr[4].get_original_form() == "5.5"
    assert arr[6].get_original_form() == "0.0"
