"""Robustness (wave 1404): a pathologically long integer literal must raise
``PDFParseError``, not leak CPython's int-string-conversion ``ValueError``.

Found by the malformed-input fuzz harness: ``parse_dir_object`` on a number
with more digits than ``sys.get_int_max_str_digits()`` (4300 by default) tripped
CPython's CPU-DoS guard, which raises a bare ``ValueError`` from ``int()``.
``BaseParser`` now wraps that as ``PDFParseError`` so callers catching the
parser's error type aren't surprised. Java upstream has no analogous failure
mode (its int parsing is bounded differently), so this is a Python-runtime
hardening, not a parity divergence.
"""

from __future__ import annotations

import sys

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _parser(payload: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(payload))


def test_overlong_integer_literal_raises_pdfparseerror() -> None:
    # One digit past CPython's conversion limit triggers the guard.
    digits = sys.get_int_max_str_digits() + 1
    payload = b"1" + b"0" * digits + b" "
    with pytest.raises(PDFParseError):
        _parser(payload).parse_dir_object()


def test_normal_large_integer_still_parses() -> None:
    """A realistically large integer (well under the digit cap, e.g. a big
    byte offset) must still parse normally — the guard only rejects the
    pathological case."""
    from pypdfbox.cos.cos_integer import COSInteger

    obj = _parser(b"123456789012345 ").parse_dir_object()
    assert isinstance(obj, COSInteger)
    assert obj.long_value() == 123456789012345
