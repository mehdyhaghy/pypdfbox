"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java

Cluster #1 slice: only the round-trip portion of upstream ``testFilters``
that applies to ``FlateDecode`` and ``ASCIIHexDecode``. The other filters
have their own per-cluster ports under ``test_filters.py``.

Skipped from upstream:
  * ``testPDFBOX4517`` — depends on ``Loader``/``PDDocument`` and a binary
    fixture; lands with the loader cluster.
  * ``testPDFBOX1977`` — LZW-specific; ported in the LZW cluster.
  * ``testRLE`` — ported in the RunLength cluster.
  * ``testEmptyFilterList`` — exercises a ``Filter.decode`` static
    dispatch helper that doesn't exist in our API surface (callers go
    through ``FilterFactory`` directly), so the failure mode it asserts
    isn't reachable from here.
"""

from __future__ import annotations

import io
import random

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCIIHexDecode, Filter, FlateDecode

# Roundtripable filters in cluster #1.
_ROUND_TRIP_FILTERS: list[Filter] = [FlateDecode(), ASCIIHexDecode()]


def _check_encode_decode(filter_: Filter, original: bytes) -> None:
    encoded = io.BytesIO()
    filter_.encode(io.BytesIO(original), encoded, COSDictionary())
    decoded = io.BytesIO()
    filter_.decode(io.BytesIO(encoded.getvalue()), decoded, COSDictionary(), 0)
    assert decoded.getvalue() == original, (
        f"data encoded then decoded through {type(filter_).__name__} "
        "does not match the original"
    )


def _generate_data(rnd: random.Random) -> bytes:
    """Mix pseudo-random and run-length-friendly bytes — same shape as
    upstream's data generator inside ``testFilters``."""
    num_bytes = 10_000 + rnd.randint(0, 19_999)
    out = bytearray(num_bytes)
    upto = 0
    while upto < num_bytes:
        left = num_bytes - upto
        if rnd.random() < 0.5 or left < 2:
            end = upto + min(left, 10 + rnd.randint(0, 99))
            while upto < end:
                out[upto] = rnd.randint(0, 255)
                upto += 1
        else:
            end = upto + min(left, 2 + rnd.randint(0, 9))
            value = rnd.randint(0, 3)
            while upto < end:
                out[upto] = value
                upto += 1
    return bytes(out)


@pytest.mark.parametrize("seed_offset", list(range(10)))
def test_filters_deterministic(seed_offset: int) -> None:
    """Mirrors the deterministic half of upstream ``testFilters``."""
    seed_picker = random.Random(123456)
    seeds = [seed_picker.randint(0, 2**31 - 1) for _ in range(10)]
    rnd = random.Random(seeds[seed_offset])
    original = _generate_data(rnd)
    for f in _ROUND_TRIP_FILTERS:
        _check_encode_decode(f, original)


@pytest.mark.parametrize("_iteration", list(range(3)))
def test_filters_non_deterministic(_iteration: int) -> None:
    """Mirrors the non-deterministic half. Three iterations rather than
    upstream's ten — the deterministic half already gives breadth and
    the suite needs to stay quick."""
    rnd = random.Random()  # system entropy
    original = _generate_data(rnd)
    for f in _ROUND_TRIP_FILTERS:
        _check_encode_decode(f, original)
