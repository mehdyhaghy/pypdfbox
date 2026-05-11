"""Wave 1281: FDFParser port."""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, FDFParser


def test_fdf_parser_is_cos_parser_subclass() -> None:
    assert issubclass(FDFParser, COSParser)


def test_fdf_parser_constructs_from_source() -> None:
    source = RandomAccessReadBuffer(b"%FDF-1.2\n%%EOF\n")
    parser = FDFParser(source)
    assert parser is not None


def test_parse_requires_fdf_header() -> None:
    # An empty document has no header → parse should raise.
    source = RandomAccessReadBuffer(b"")
    parser = FDFParser(source)
    with pytest.raises((OSError, ValueError)):
        parser.parse()
