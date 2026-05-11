"""Wave 1281: BruteForceParser subclass port."""

from __future__ import annotations

from pypdfbox.cos import COSDocument
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BruteForceParser, COSParser


def test_brute_force_parser_is_cos_parser_subclass() -> None:
    assert issubclass(BruteForceParser, COSParser)


def test_brute_force_parser_constructs_with_source_and_document() -> None:
    source = RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")
    doc = COSDocument()
    parser = BruteForceParser(source, doc)
    assert parser.document is doc


def test_bf_search_triggered_default_false() -> None:
    source = RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n")
    parser = BruteForceParser(source, COSDocument())
    assert parser.bf_search_triggered() is False
