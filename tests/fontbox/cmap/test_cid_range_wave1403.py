"""Wave 1403 — branch round-out for :mod:`pypdfbox.fontbox.cmap.cid_range`.

Closes the partial arc ``6->8`` in :func:`_to_int` — the ``data_len is
None`` True branch, where the length is derived from ``len(data)`` and
control then enters the accumulation loop.
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap.cid_range import _to_int


def test_to_int_without_explicit_length_derives_from_data() -> None:
    """Calling ``_to_int`` without ``data_len`` takes the
    ``data_len is None`` True arc (6->8): the length is derived from the
    buffer and the big-endian value is accumulated."""
    assert _to_int(b"\x01\x02") == 0x0102


def test_to_int_with_explicit_length_matches() -> None:
    """Companion: an explicit ``data_len`` yields the same value via the
    other arc of the same guard."""
    assert _to_int(b"\x01\x02\x03", 3) == 0x010203
