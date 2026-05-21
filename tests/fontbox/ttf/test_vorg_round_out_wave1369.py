"""Wave 1369 round-out tests for :class:`VerticalOriginTable`.

The VORG (``Vertical Origin``) table sits between fontbox's CFF /
OpenType glyph metric helpers and the CMap renderer. Earlier waves
cover the happy path; this file fills in:

* Multiple per-glyph origin entries with mixed positive / negative Y.
* Higher-version reads — the 16.16 fixed-point version is parsed
  separately from the rest of the table so callers can inspect it.
* ``get_origin_y`` for a GID *between* explicit entries falls back to
  the default (not interpolated).
* Empty per-glyph metrics table (``numVertOriginYMetrics == 0``) — only
  the default origin is consulted.
* ``read`` flips the ``initialized`` flag on success.
* Setters reset state cleanly.
"""

from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.vertical_origin_table import VerticalOriginTable


def _pack_vorg(
    *,
    version_high: int = 1,
    version_low: int = 0,
    default_y: int = 0,
    metrics: list[tuple[int, int]] | None = None,
) -> bytes:
    """Build a VORG table payload."""
    metrics = metrics or []
    out = struct.pack(">hHhH", version_high, version_low, default_y, len(metrics))
    for gid, y in metrics:
        out += struct.pack(">Hh", gid, y)
    return out


# ---------- multi-entry round-trip -----------------------------------------


def test_read_multiple_entries_mixed_sign() -> None:
    """Per-glyph origin Y values include both positive and negative
    signed shorts; they must round-trip through the table accessor."""
    raw = _pack_vorg(
        default_y=800,
        metrics=[(1, 750), (2, -100), (3, 0), (4, 32767)],
    )
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_origin_y(1) == 750
    assert table.get_origin_y(2) == -100
    assert table.get_origin_y(3) == 0
    assert table.get_origin_y(4) == 32767


def test_get_origin_y_uses_default_for_unmapped_gid() -> None:
    """A GID *between* two explicit metric entries is not interpolated
    — the default is returned per the upstream contract (``getOriginY``
    is a simple map lookup with a default fallback)."""
    raw = _pack_vorg(
        default_y=900,
        metrics=[(1, 100), (10, 200)],
    )
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    # GIDs 0, 2..9 fall back to the default.
    for gid in (0, 2, 5, 9, 11, 99):
        assert table.get_origin_y(gid) == 900
    # Explicit entries still resolve.
    assert table.get_origin_y(1) == 100
    assert table.get_origin_y(10) == 200


def test_read_zero_metrics_only_default_consulted() -> None:
    raw = _pack_vorg(default_y=512, metrics=[])
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    # Any GID returns the default.
    for gid in (0, 1, 100, 65535):
        assert table.get_origin_y(gid) == 512


def test_read_marks_initialized() -> None:
    table = VerticalOriginTable()
    assert table.get_initialized() is False
    raw = _pack_vorg(metrics=[(0, 0)])
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_initialized() is True


def test_version_is_fixed_point_round_trip() -> None:
    """Version is a 16.16 fixed-point. ``read_32_fixed`` reconstructs the
    floating value from the integer + fractional shorts."""
    raw = _pack_vorg(version_high=1, version_low=0x8000, metrics=[(0, 0)])
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 1.5


def test_zero_version_uninitialized() -> None:
    table = VerticalOriginTable()
    assert table.get_version() == 0.0


def test_default_only_origin_y_returns_default_for_negative_gid() -> None:
    """``get_origin_y`` returns the default for any GID not explicitly
    mapped, including negative values — the lookup is a dict ``get``
    with the default as fallback."""
    raw = _pack_vorg(default_y=-50, metrics=[])
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_origin_y(-1) == -50


def test_tag_constant_is_vorg() -> None:
    assert VerticalOriginTable.TAG == "VORG"


def test_consecutive_reads_overwrite_state() -> None:
    """A second ``read`` overwrites the per-glyph dict completely — no
    leftover state from the first read leaks through."""
    table = VerticalOriginTable()
    table.read(
        None,  # type: ignore[arg-type]
        MemoryTTFDataStream(_pack_vorg(default_y=100, metrics=[(1, 10), (2, 20)])),
    )
    assert table.get_origin_y(1) == 10
    # Second read with a different default and a single entry.
    table.read(
        None,  # type: ignore[arg-type]
        MemoryTTFDataStream(_pack_vorg(default_y=200, metrics=[(3, 30)])),
    )
    assert table.get_origin_y(3) == 30
    # GID 1 / 2 no longer have explicit entries → default fallback.
    assert table.get_origin_y(1) == 200
    assert table.get_origin_y(2) == 200


def test_large_metrics_table_with_many_entries() -> None:
    """Stress-shape: a few hundred entries through the read loop —
    confirms the iterator doesn't crash on a longer input than the
    happy path covers."""
    metrics = [(gid, gid * 7) for gid in range(1, 200)]
    raw = _pack_vorg(default_y=1, metrics=metrics)
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    for gid in (1, 50, 100, 199):
        assert table.get_origin_y(gid) == gid * 7
    # GID outside the range falls back to default.
    assert table.get_origin_y(500) == 1
