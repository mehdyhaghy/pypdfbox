"""Port of ``pdfbox/src/test/java/org/apache/pdfbox/pdfparser/PDFStreamParserTest.java``.

Upstream baseline: apache/pdfbox 3.0.
"""
from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def _parse(s: str) -> list[object]:
    p = PDFStreamParser(RandomAccessReadBuffer(s.encode("latin-1")))
    return list(p.tokens())


def _expect_inline_2ops(s: str, image_data_str: str, op_name: str) -> None:
    """Upstream's ``testInlineImage2ops``: stream begins with ``ID``, so the
    first emitted token is the ID operator carrying the captured bytes,
    followed by the trailing operator."""
    toks = _parse(s)
    assert len(toks) == 2, f"tokens: {toks!r}"
    assert isinstance(toks[0], Operator) and toks[0].name == "ID"
    assert toks[0].image_data == image_data_str.encode("latin-1")
    assert isinstance(toks[1], Operator) and toks[1].name == op_name


def _expect_inline_1op(s: str, image_data_str: str) -> None:
    """Upstream's ``testInlineImage1op``: only the ID operator is emitted."""
    toks = _parse(s)
    assert len(toks) == 1, f"tokens: {toks!r}"
    assert isinstance(toks[0], Operator) and toks[0].name == "ID"
    assert toks[0].image_data == image_data_str.encode("latin-1")


# ---------- testInlineImages — every "ID\n12345EI ..." case in upstream ----------


@pytest.mark.parametrize(
    "stream,image,op",
    [
        ("ID\n12345EI Q", "12345", "Q"),
        ("ID\n12345EI EMC", "12345", "EMC"),
        ("ID\n12345EI Q ", "12345", "Q"),
        ("ID\n12345EI EMC ", "12345", "EMC"),
        ("ID\n12345EI  Q", "12345", "Q"),
        ("ID\n12345EI  EMC", "12345", "EMC"),
        ("ID\n12345EI  Q ", "12345", "Q"),
        ("ID\n12345EI  EMC ", "12345", "EMC"),
        ("ID\n12345EI \x00Q", "12345", "Q"),
        ("ID\n12345EI Q                             ", "12345", "Q"),
        ("ID\n12345EI EMC                           ", "12345", "EMC"),
        ("ID\n12345EI                               Q ", "12345", "Q"),
        ("ID\n12345EI                               EMC ", "12345", "EMC"),
        ("ID\n12345EI                               Q", "12345", "Q"),
        ("ID\n12345EI                               EMC", "12345", "EMC"),
        ("ID\n12EI5EIQEI Q", "12EI5EIQ", "Q"),
        ("ID\n12EI5EI Q", "12EI5", "Q"),
        ("ID\n12EI5EI Q ", "12EI5", "Q"),
        ("ID\n12EI5EI EMC", "12EI5", "EMC"),
        ("ID\n12EI5EI EMC ", "12EI5", "EMC"),
        ("ID\n12EI5EI                                Q", "12EI5", "Q"),
        ("ID\n12EI5EI                                Q ", "12EI5", "Q"),
        ("ID\n12EI5EI                                EMC", "12EI5", "EMC"),
        ("ID\n12EI5EI                                EMC ", "12EI5", "EMC"),
        # MAX_BIN_CHAR_TEST_LENGTH = 10 boundary checks
        ("ID\n12EI5EI       EMC ", "12EI5", "EMC"),
        ("ID\n12EI5EI        EMC ", "12EI5", "EMC"),
        ("ID\n12EI5EI         EMC ", "12EI5", "EMC"),
        ("ID\n12EI5EI          EMC ", "12EI5", "EMC"),
        ("ID\n12EI5EI       Q   ", "12EI5", "Q"),
        ("ID\n12EI5EI        Q   ", "12EI5", "Q"),
        ("ID\n12EI5EI         Q   ", "12EI5", "Q"),
        ("ID\n12EI5EI          Q   ", "12EI5", "Q"),
    ],
)
def test_inline_images_two_ops(stream: str, image: str, op: str) -> None:
    _expect_inline_2ops(stream, image, op)


@pytest.mark.parametrize(
    "stream,image",
    [
        ("ID\n12345EI", "12345"),
        ("ID\n12345EI                               ", "12345"),
        ("ID\n12EI5EI", "12EI5"),
        ("ID\n12EI5EI ", "12EI5"),
        ("ID\n12EI5EIQEI", "12EI5EIQ"),
    ],
)
def test_inline_images_one_op(stream: str, image: str) -> None:
    _expect_inline_1op(stream, image)


# ---------- testNestedBI (PDFBOX-6038) ----------


def test_nested_bi() -> None:
    # Upstream throws IOException — we raise PDFParseError (matches the
    # project's mapping IOException → PDFParseError in parser context).
    with pytest.raises(PDFParseError) as excinfo:
        _parse("BI/IB/IB BI/ BI")
    msg = str(excinfo.value)
    assert "Nested 'BI'" in msg
