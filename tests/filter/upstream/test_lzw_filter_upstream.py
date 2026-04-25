"""
Port of upstream PDFBox LZW filter tests.

Source:
- ``pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java`` —
  the LZW-relevant pieces are ``testFilters()`` (random round-trip
  smoke test across all reversible filters) and ``testPDFBOX1977()``
  (regression test for an off-by-one in the encoder's final-chunk
  width). PDFBox doesn't have a standalone ``LzwFilterTest.java`` in
  the 3.0 branch.

The PDFBOX-1977 binary fixture is not redistributed with this port;
the regression is exercised here by a deterministic synthetic input
that drives the same code-table edge case (the encoder's final code
crossing a width boundary).
"""

from __future__ import annotations

import random
from io import BytesIO

import pytest

from pypdfbox.cos import COSName
from pypdfbox.filter import FilterFactory, LZWDecode


def _check_encode_decode(data: bytes) -> None:
    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(data), enc, None)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == data


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_filters_random_roundtrip(seed: int) -> None:
    """Mirror of upstream ``testFilters()`` — random byte arrays of
    10_000 to 30_000 bytes, deterministic per seed."""
    rng = random.Random(seed)
    size = rng.randrange(10_000, 30_000)
    data = bytes(rng.randrange(256) for _ in range(size))
    _check_encode_decode(data)


def test_pdfbox_1977_regression_synthetic() -> None:
    """Mirror of upstream ``testPDFBOX1977()`` — exercises the
    encoder's final-code-width adjustment. We synthesize an input
    long enough to push the table size past at least one width
    boundary so the closing EOD must be emitted at the post-growth
    width."""
    # A pseudo-random 16k blob blows past the 9->10 boundary several
    # times; if the encoder failed to widen for the final EOD, the
    # decoder would misinterpret the trailing bits.
    rng = random.Random(0xB1977)
    data = bytes(rng.randrange(256) for _ in range(16_000))
    _check_encode_decode(data)


def test_filter_factory_resolves_lzw_decode() -> None:
    """Mirror of upstream's ``FilterFactory.INSTANCE.getFilter(COSName.LZW_DECODE)``."""
    inst = FilterFactory.get(COSName.get_pdf_name("LZWDecode"))
    assert isinstance(inst, LZWDecode)
