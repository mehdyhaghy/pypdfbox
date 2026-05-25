"""Wave 1403 branch round-out for ``BaseParser.parse_cos_array``.

Closes 966->979 — the inner ``if len(po) > 0 and isinstance(po.get(-1),
COSInteger)`` False arm of the ``num gen R`` indirect-reference recovery.

Wave 1400 covered the *outer* guard (line 964 False: only one int before the
``R``). To reach line 966 the outer guard must be True (≥2 elements, last is
an int), and after removing that trailing int the *new* last element must not
be a ``COSInteger`` — making line 966 False so ``pbo`` stays None and the
corrupt-element recovery runs.

Array ``[/X 5 R]``: parsing ``R`` yields a ``COSObject`` placeholder while
``po == [/X, 5]``. Line 964 is True (len 2 > 1, last is ``5``); after removing
``5`` the array is ``[/X]`` whose last element ``/X`` is a ``COSName`` — line
966 is False (966->979).
"""

from __future__ import annotations

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser


def test_parse_cos_array_int_preceded_by_non_int_before_R() -> None:
    """Closes 966->979: a non-integer precedes the single trailing integer
    before the ``R`` placeholder, so the second integer check is False."""
    parser = BaseParser(RandomAccessReadBuffer(b"[/X 5 R]"))
    result = parser.parse_cos_array()
    # parse_cos_array recovers gracefully: it logs the corrupt element and
    # returns the partially-populated array without raising.
    assert result is not None
