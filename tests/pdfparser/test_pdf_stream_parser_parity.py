"""Upstream-name parity tests for ``PDFStreamParser``.

These exercise the accessor aliases that mirror PDFBox's
``org.apache.pdfbox.pdfparser.PDFStreamParser`` public surface so callers
written against PDFBox can reach the same operations under their familiar
names.
"""

from __future__ import annotations

import pytest

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


# ---------- Operator factory + str / repr parity ----------


def test_operator_str_matches_upstream_pdfoperator_form() -> None:
    # Upstream ``Operator.toString()`` returns ``"PDFOperator{<name>}"``.
    op = Operator("Tj")
    assert str(op) == "PDFOperator{Tj}"
    assert repr(op) == "PDFOperator{Tj}"


def test_operator_get_operator_caches_non_inline_operators() -> None:
    # Mirrors upstream's ConcurrentHashMap-backed cache: the same
    # operator name returns the *same* instance across calls.
    a = Operator.get_operator("Tj")
    b = Operator.get_operator("Tj")
    assert a is b
    assert a.get_name() == "Tj"


def test_operator_get_operator_skips_cache_for_inline_image_ops() -> None:
    # Upstream forces a fresh instance for BI/ID because each occurrence
    # carries distinct image_data / image_parameters payloads.
    bi1 = Operator.get_operator("BI")
    bi2 = Operator.get_operator("BI")
    id1 = Operator.get_operator("ID")
    id2 = Operator.get_operator("ID")
    assert bi1 is not bi2
    assert id1 is not id2


def test_operator_constructor_rejects_name_with_leading_slash() -> None:
    # Upstream throws IllegalArgumentException — Python equivalent is
    # ValueError. Both surface the same misuse: a "/Foo" name is a name
    # object, not an operator keyword.
    with pytest.raises(ValueError, match="not allowed to start with /"):
        Operator("/Foo")


# ---------- is_space_or_return / has_next_space_or_return ----------


def test_is_space_or_return_recognises_lf_cr_sp() -> None:
    assert PDFStreamParser.is_space_or_return(0x0A) is True  # LF
    assert PDFStreamParser.is_space_or_return(0x0D) is True  # CR
    assert PDFStreamParser.is_space_or_return(0x20) is True  # SP
    # Tab and form-feed are NOT in the EI separator set.
    assert PDFStreamParser.is_space_or_return(0x09) is False
    assert PDFStreamParser.is_space_or_return(0x0C) is False
    # Any random non-whitespace byte is False.
    assert PDFStreamParser.is_space_or_return(ord("Q")) is False


def test_has_next_space_or_return_reflects_cursor() -> None:
    p = _parser(b" Q")
    # Cursor sits at the leading space.
    assert p.has_next_space_or_return() is True
    p.parse_next_token()  # consumes "Q" (skip_whitespace eats the space).
    # After draining, peek returns -1 (EOF), which is not a separator.
    assert p.has_next_space_or_return() is False


# ---------- parse_next_token guard against closed source ----------


def test_parse_next_token_returns_none_after_close() -> None:
    p = _parser(b"100 200 m")
    p.close()
    assert p.is_closed() is True
    # Upstream returns null when source.isClosed(); we return None.
    assert p.parse_next_token() is None


# ---------- from_content_stream constructor ----------


def test_from_content_stream_uses_get_contents_for_stream_parsing() -> None:
    # Mirrors upstream's PDFStreamParser(PDContentStream) constructor,
    # which calls pd.getContentsForStreamParsing() to obtain the source.
    from pypdfbox.contentstream.pd_content_stream import PDContentStream

    raw_seen: dict[str, bool] = {"called": False}

    class _StubContentStream(PDContentStream):
        def get_contents(self):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def get_contents_for_random_access(self):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def get_contents_for_stream_parsing(self):  # type: ignore[no-untyped-def]
            raw_seen["called"] = True
            return RandomAccessReadBuffer(b"100 200 m")

        def get_resources(self):  # type: ignore[no-untyped-def]
            return None

        def get_bbox(self):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def get_matrix(self):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    p = PDFStreamParser.from_content_stream(_StubContentStream())
    assert raw_seen["called"] is True
    toks = p.parse()
    assert len(toks) == 3
    assert isinstance(toks[2], Operator) and toks[2].get_name() == "m"
