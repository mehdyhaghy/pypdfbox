"""Translated from
``fontbox/src/test/java/org/apache/fontbox/ttf/TrueTypeFontCollectionTest.java``.

Upstream's JUnit5 ``TrueTypeFontCollectionTest`` covers the single
defensive case — the ``numFonts`` sanity check rejects values outside
the [1, 1024] bound. We mirror it here so future re-syncs are
diffable.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection


def test_number_of_fonts() -> None:
    """Mirror ``TrueTypeFontCollectionTest.testNumberOfFonts``
    (``TrueTypeFontCollectionTest.java`` lines 28-36).

    The payload is a valid TTC magic + zero-version + a clearly-too-
    large ``numFonts`` (``0x7FFFFFFF``); upstream asserts ``IOException``
    via ``assertThrows``. Our parity exception is ``OSError`` (Python's
    generic I/O class, per the project's translation table).
    """
    payload = bytes(
        [
            0x74,
            0x74,
            0x63,
            0x66,
            0x00,
            0x00,
            0x00,
            0x00,
            0x7F,
            0xFF,
            0xFF,
            0xFF,
        ]
    )
    with pytest.raises(OSError, match="Invalid number of fonts"):
        TrueTypeCollection(io.BytesIO(payload))
