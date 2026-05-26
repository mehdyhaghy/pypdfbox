"""Robustness (wave 1404): deeply nested direct ``[...]`` / ``<<...>>`` in a
malformed PDF must raise ``PDFParseError``, not leak Python's ``RecursionError``.

Found by the malformed-input fuzz harness: ``parse_dir_object`` recurses through
``parse_cos_array`` / ``parse_cos_dictionary`` for each nested element, so a
pathologically deep structure exhausts Python's recursion limit (~498-deep
arrays at the default limit of 1000). ``parse_dir_object`` now converts that
into the parser's own error type at the container-dispatch boundary.

Real PDFs are unaffected: legitimate documents nest direct containers only a
handful of levels (measured max 4 across the test corpus); logical document
depth — page trees, outlines, structure trees — is built from *indirect*
references, which do not recurse the parser. This guard only fires on hostile
input. (Upstream PDFBox is likewise recursive here; it tolerates more only
because the JVM stack is deeper than Python's recursion limit.)
"""

from __future__ import annotations

import sys

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _parse(payload: bytes):
    return BaseParser(RandomAccessReadBuffer(payload)).parse_dir_object()


def test_deeply_nested_array_raises_pdfparseerror_not_recursionerror() -> None:
    # Depth past the ambient recursion limit guarantees overflow regardless of
    # the test runner's configured limit (arrays cost ~2 frames per level).
    depth = sys.getrecursionlimit() + 100
    payload = b"[" * depth + b" 1 " + b"]" * depth
    with pytest.raises(PDFParseError) as exc:
        _parse(payload)
    assert not isinstance(exc.value, RecursionError)
    assert "nesting too deep" in str(exc.value)


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
