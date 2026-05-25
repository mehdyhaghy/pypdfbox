"""Wave 1403 branch round-out for ``DCTFilter.get_adobe_transform_by_brute_force``.

Closes the reachable "keep scanning" False arm of the APP14 ``Adobe`` segment
parser:

* 220->192 — the segment length is large enough but the payload read back
  is truncated (fewer bytes than the transform offset), so the scan loop
  continues to EOF.
* 217->192 — the declared segment length is too short to hold the transform
  byte, so the parser skips the marker and keeps scanning.

A well-formed APP14/Adobe marker is ``FF EE <len_hi> <len_lo> 'Adobe'
<payload>``; the brute-force scanner finds ``Adobe``, rewinds to read the
``FFEE`` tag and the 2-byte length, then reads the payload.

The 217->192 arc was previously unreachable: the False arm of line 217 did
*not* restore the cursor past the matched ``Adobe`` bytes (unlike the sibling
failure paths at lines 206/210/214), so any input that reached it re-matched
the same ``Adobe`` marker forever (infinite loop). Wave 1403 fixes that by
seeking back to ``after_adobe_pos`` before rescanning; the test below now
covers the arc and guards against the loop regressing.
"""

from __future__ import annotations

import io

from pypdfbox.filter.dct_filter import DCTFilter


def _adobe_marker(seg_len: int, payload_len: int) -> bytes:
    tag = bytes([0xFF, 0xEE])
    length = bytes([(seg_len >> 8) & 0xFF, seg_len & 0xFF])
    return tag + length + b"Adobe" + bytes(payload_len)


def test_brute_force_skips_when_payload_truncated() -> None:
    """Closes 220->192: ``seg_len`` (12) is large enough but only 4 payload
    bytes follow, so ``len(app14) >= _POS_TRANSFORM + 1`` is False and the
    loop continues, returning the default transform 0."""
    data = _adobe_marker(seg_len=12, payload_len=4)
    transform = DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data))
    assert transform == 0


def test_brute_force_skips_when_segment_too_short() -> None:
    """Closes 217->192: a malformed marker declares ``seg_len`` (4) smaller
    than ``_POS_TRANSFORM + 1`` (12). Before the wave-1403 fix this hung
    (the cursor was never advanced past the matched ``Adobe`` bytes, so the
    scan re-matched the same marker forever). The fix seeks back to
    ``after_adobe_pos`` so the loop runs to EOF and returns the default 0.

    A trailing ``Adobe`` substring is appended to prove the scan keeps moving
    forward rather than spinning on the first match.
    """
    data = _adobe_marker(seg_len=4, payload_len=0) + b"Adobe"
    transform = DCTFilter().get_adobe_transform_by_brute_force(io.BytesIO(data))
    assert transform == 0
