from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave301_allows_container_nesting_at_configured_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(COSParser, "MAX_RECURSION_DEPTH", 2)

    array = _parser(b"[[1]]").parse_direct_object()
    assert isinstance(array, COSArray)

    dictionary = _parser(b"<< /A << /B 1 >> >>").parse_direct_object()
    assert isinstance(dictionary, COSDictionary)


def test_wave301_rejects_array_nesting_beyond_configured_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(COSParser, "MAX_RECURSION_DEPTH", 2)
    parser = _parser(b"[[[1]]]")

    with pytest.raises(PDFParseError, match="maximum COS array nesting depth"):
        parser.parse_direct_object()

    assert parser._recursion_depth == 0


def test_wave301_rejects_dictionary_nesting_beyond_configured_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(COSParser, "MAX_RECURSION_DEPTH", 2)
    parser = _parser(b"<< /A << /B << /C 1 >> >> >>")

    with pytest.raises(PDFParseError, match="maximum COS dictionary nesting depth"):
        parser.parse_direct_object()

    assert parser._recursion_depth == 0
