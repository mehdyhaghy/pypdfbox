"""Tests ported from PDFBox 3.0 ``TestFilters`` (extended round-trip slice).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java``
on the apache/pdfbox 3.0 branch.

The other ``TestFilters`` slices live in
:mod:`tests.filter.upstream.test_filters` (RLE + ASCII85),
:mod:`tests.filter.upstream.test_filters_flate_ascii_hex`
(Flate + ASCIIHex), and
:mod:`tests.filter.upstream.test_lzw_filter_upstream` (LZW).

This file picks up the remaining surface:

- ``testFilters`` — the deterministic+non-deterministic random sweep
  across **every** registered filter (skipping the non-roundtrip image
  filters per upstream). Translates to a deterministic seed set —
  pytest reruns are reproducible without the non-deterministic seed
  upstream uses.
- ``testPDFBOX1977`` — exercises the LZW encoder/decoder against the
  exact binary fixture upstream bundles, mirroring the upstream
  ``checkEncodeDecode`` contract on that blob.
"""

from __future__ import annotations

import io
import random
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.filter import (
    CCITTFaxDecode,
    DCTDecode,
    Filter,
    FilterFactory,
    JBIG2Decode,
    JPXDecode,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "filter"

# Filters that don't round-trip at the encode/decode boundary — upstream
# skips these in ``testFilters`` because their decode is image-format
# specific (JPEG / JPEG2000 / JBIG2 / CCITT) and ``encode`` is either
# unavailable or lossy. See upstream lines 102-108.
_NON_ROUNDTRIP = (DCTDecode, CCITTFaxDecode, JPXDecode, JBIG2Decode)


def _check_encode_decode(filter_: Filter, original: bytes) -> None:
    """Mirror of upstream's ``TestFilters#checkEncodeDecode``."""
    encoded = io.BytesIO()
    filter_.encode(io.BytesIO(original), encoded)
    decoded = io.BytesIO()
    filter_.decode(io.BytesIO(encoded.getvalue()), decoded)
    assert decoded.getvalue() == original, (
        f"Round-trip mismatch through {type(filter_).__name__}"
    )


def _make_random_payload(seed: int) -> bytes:
    """Reproduce upstream's mixed pseudo-random / run-of-equal-bytes
    fill pattern (lines 70-97 of ``TestFilters.java``).

    The result is between 10_000 and 30_000 bytes — same range as
    upstream — and contains a mix of pseudo-random and short
    constant-fill runs to exercise the predictor and RLE paths.
    """
    rng = random.Random(seed)
    num_bytes = 10_000 + rng.randrange(20_000)
    out = bytearray(num_bytes)
    upto = 0
    while upto < num_bytes:
        left = num_bytes - upto
        if rng.random() < 0.5 or left < 2:
            # Pseudo-random fill chunk.
            end = upto + min(left, 10 + rng.randrange(100))
            while upto < end:
                out[upto] = rng.randrange(256)
                upto += 1
        else:
            # Constant fill chunk — exercises RLE compression.
            end = upto + min(left, 2 + rng.randrange(10))
            value = rng.randrange(4)
            while upto < end:
                out[upto] = value
                upto += 1
    return bytes(out)


# Seeds chosen so the matrix is reproducible across runs. Upstream
# uses a ``Random(123456)``-derived stream; we keep that root seed and
# enumerate the first ten derivatives below so the corpus has the
# same diversity without inheriting Java's RNG internals.
_SEEDS = [123456, 17, 42, 1024, 65537, 1_000_003, 2_147_483_647, 11, 31, 97]


@pytest.mark.parametrize("seed", _SEEDS)
def test_filters_round_trip(seed: int) -> None:
    """Port of ``TestFilters#testFilters`` — round-trip every
    registered filter through a random payload, skipping the
    image-format filters upstream also skips."""
    payload = _make_random_payload(seed)
    for filter_ in FilterFactory.get_all_filters():
        if isinstance(filter_, _NON_ROUNDTRIP):
            continue
        _check_encode_decode(filter_, payload)


def test_pdf_box_1977() -> None:
    """Port of ``TestFilters#testPDFBOX1977`` — LZW round-trip on the
    exact upstream binary fixture."""
    blob = (_FIXTURE_DIR / "PDFBOX-1977.bin").read_bytes()
    lzw_filter = FilterFactory.get(COSName.get_pdf_name("LZWDecode"))
    _check_encode_decode(lzw_filter, blob)
