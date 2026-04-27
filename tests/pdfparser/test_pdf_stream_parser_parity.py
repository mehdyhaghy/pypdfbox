"""Upstream-name parity tests for ``PDFStreamParser``.

These exercise the accessor aliases that mirror PDFBox's
``org.apache.pdfbox.pdfparser.PDFStreamParser`` public surface so callers
written against PDFBox can reach the same operations under their familiar
names.
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSInteger
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def _parser(data: bytes) -> PDFStreamParser:
    return PDFStreamParser(RandomAccessReadBuffer(data))


# ---------- parse_next_token ----------


def test_parse_next_token_returns_operand_then_operator() -> None:
    p = _parser(b"42 m")
    first = p.parse_next_token()
    second = p.parse_next_token()
    third = p.parse_next_token()
    assert isinstance(first, COSInteger)
    assert first.value == 42
    assert isinstance(second, Operator)
    assert second.get_name() == "m"
    assert third is None


def test_parse_next_token_yields_cosbase_subclasses() -> None:
    # All operands flowing back are COSBase instances; operators are not.
    p = _parser(b"100 200 m")
    a = p.parse_next_token()
    b = p.parse_next_token()
    op = p.parse_next_token()
    assert isinstance(a, COSBase)
    assert isinstance(b, COSBase)
    assert isinstance(op, Operator)


# ---------- get_tokens ----------


def test_get_tokens_drains_parser() -> None:
    p = _parser(b"1 2 3 m")
    toks = p.get_tokens()
    assert len(toks) == 4
    assert all(t is not None for t in toks)
    # Iterator is now drained — calling parse_next_token again returns None.
    assert p.parse_next_token() is None


def test_get_tokens_matches_parse_output() -> None:
    data = b"BT /F1 12 Tf (hi) Tj ET"
    eager = _parser(data).get_tokens()
    via_parse = _parser(data).parse()
    assert len(eager) == len(via_parse)
    assert [type(t).__name__ for t in eager] == [type(t).__name__ for t in via_parse]


# ---------- parse_stream alias ----------


def test_parse_stream_alias_returns_same_as_parse() -> None:
    data = b"10 20 m"
    via_alias = _parser(data).parse_stream()
    via_parse = _parser(data).parse()
    assert len(via_alias) == len(via_parse) == 3


# ---------- get_position / seek_to ----------


def test_get_position_starts_at_zero() -> None:
    p = _parser(b"100 m")
    assert p.get_position() == 0


def test_get_position_increases_as_parse_consumes_bytes() -> None:
    p = _parser(b"100 200 m")
    start = p.get_position()
    p.parse_next_token()  # "100"
    after_first = p.get_position()
    p.parse_next_token()  # "200"
    after_second = p.get_position()
    p.parse_next_token()  # "m"
    after_third = p.get_position()
    assert start == 0
    assert after_first > start
    assert after_second > after_first
    assert after_third > after_second


def test_seek_to_rewinds_source() -> None:
    p = _parser(b"100 200 m")
    p.parse_next_token()
    p.parse_next_token()
    mid = p.get_position()
    assert mid > 0
    p.seek_to(0)
    assert p.get_position() == 0
    # Re-parsing from the start yields the original first token.
    again = p.parse_next_token()
    assert isinstance(again, COSInteger)
    assert again.value == 100


# ---------- is_in_inline_image ----------


def test_is_in_inline_image_false_outside_inline_segment() -> None:
    p = _parser(b"100 200 m")
    assert p.is_in_inline_image() is False
    p.parse_next_token()
    assert p.is_in_inline_image() is False


def test_is_in_inline_image_false_after_full_inline_image_drained() -> None:
    # BI...ID...EI returns the inline-image operator and resets the depth.
    data = b"BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI Q"
    p = _parser(data)
    toks = p.get_tokens()
    # Depth is decremented when the BI operator returns, so once parsing
    # finishes we are no longer "inside" the segment.
    assert p.is_in_inline_image() is False
    # And we did get a BI operator back.
    assert any(isinstance(t, Operator) and t.get_name() == "BI" for t in toks)
