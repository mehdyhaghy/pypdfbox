"""Robustness (wave 1404): deeply nested direct ``[...]`` / ``<<...>>`` in a
malformed PDF must raise ``PDFParseError``, not leak Python's ``RecursionError``.

``parse_dir_object`` recurses through ``parse_cos_array`` /
``parse_cos_dictionary`` for each nested element. Like upstream PDFBox, the
parser counts those calls against ``MAX_RECURSION_DEPTH`` (500) and fails with
upstream's "Reached maximum recursion depth 500" well before Python's own
recursion limit. See ``test_deep_nesting.py`` for the full depth matrix.
"""

import sys

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _parse(payload: bytes):
    return BaseParser(RandomAccessReadBuffer(payload)).parse_dir_object()


def test_deeply_nested_array_raises_pdfparseerror_not_recursionerror() -> None:
    # Deeper than the ambient recursion limit: the depth limit must stop the
    # parse before Python's stack does.
    depth = sys.getrecursionlimit() + 100
    payload = b"[" * depth + b" 1 " + b"]" * depth
    with pytest.raises(PDFParseError) as exc:
        _parse(payload)
    assert not isinstance(exc.value, RecursionError)
    assert "Reached maximum recursion depth 500" in str(exc.value)


def test_deeply_nested_dictionary_raises_pdfparseerror() -> None:
    depth = sys.getrecursionlimit() + 100
    payload = b"<< /K " * depth + b"1" + b" >>" * depth
    with pytest.raises(PDFParseError):
        _parse(payload)


def test_shallow_nesting_still_parses() -> None:
    """The guard must not affect normal, shallowly-nested structures."""
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_dictionary import COSDictionary

    arr = _parse(b"[1 2 [3 4] 5]")
    assert isinstance(arr, COSArray)
    assert len(arr) == 4

    d = _parse(b"<< /A 1 /B [2 3] /C << /D 4 >> >>")
    assert isinstance(d, COSDictionary)
