"""Wave 1369 round-out tests for ``hmtx`` and ``vmtx``.

Exercises:

* Boundary GIDs (``num_h_metrics - 1``, ``num_h_metrics``, ``num_glyphs``)
  on monospaced-style tables where the trailing LSB / TSB array is the
  only metric source.
* Signed 16-bit boundary values (-32768 / 32767) round-trip through the
  signed-short reader.
* ``num_glyphs == num_h_metrics`` (no trailing array): every GID resolves
  from the per-glyph hMetric block.
* Empty-state defaults for both tables (no ``read`` ever called).
* Monospaced font fallback: every GID past ``num_h_metrics`` returns the
  width of the last per-glyph entry, not the LSB array value.
* ``num_glyphs == 0`` is legal — neither array is sized incorrectly.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import cast

from pypdfbox.fontbox.ttf.horizontal_metrics_table import HorizontalMetricsTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.vertical_metrics_table import VerticalMetricsTable


@dataclass
class _StubHHEA:
    num_h_metrics: int

    def get_number_of_h_metrics(self) -> int:
        return self.num_h_metrics


@dataclass
class _StubVHEA:
    num_v_metrics: int

    def get_number_of_v_metrics(self) -> int:
        return self.num_v_metrics


@dataclass
class _StubTTF:
    num_glyphs: int
    h_header: _StubHHEA | None = None
    v_header: _StubVHEA | None = None

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs

    def get_horizontal_header(self) -> _StubHHEA | None:
        return self.h_header

    def get_vertical_header(self) -> _StubVHEA | None:
        return self.v_header


def _ttf(stub: _StubTTF) -> TrueTypeFont:
    return cast(TrueTypeFont, stub)


def _pack_h(advance: int, lsb: int) -> bytes:
    return struct.pack(">Hh", advance, lsb)


def _pack_v(advance: int, tsb: int) -> bytes:
    return struct.pack(">Hh", advance, tsb)


# ---------- hmtx ------------------------------------------------------------


def test_hmtx_boundary_gid_at_num_h_metrics_minus_one() -> None:
    """``gid == num_h_metrics - 1`` is the *last* index served from the
    per-glyph hMetric array — picks the last advance / LSB pair directly,
    not the fallback "last entry" path."""
    blob = _pack_h(500, 10) + _pack_h(700, -5) + _pack_h(900, 0) + _pack_h(11, 4)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=4, h_header=_StubHHEA(num_h_metrics=4))),
        MemoryTTFDataStream(blob),
    )
    # gid 3 is the 4th entry — not the fallback last-entry shortcut.
    assert table.get_advance_width(3) == 11
    assert table.get_left_side_bearing(3) == 4
    # gid 2 still resolves correctly from the per-glyph array
    assert table.get_advance_width(2) == 900


def test_hmtx_num_glyphs_equals_num_h_metrics_no_trailing_lsb_array() -> None:
    """The common case for non-monospaced fonts: every glyph has its own
    full hMetric record. No trailing LSB array is consumed, and the
    table length matches the per-glyph block exactly."""
    blob = _pack_h(500, 10) + _pack_h(600, -5) + _pack_h(700, 0)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=3, h_header=_StubHHEA(num_h_metrics=3))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_advance_width(0) == 500
    assert table.get_advance_width(2) == 700
    assert table.get_left_side_bearing(2) == 0


def test_hmtx_monospaced_uses_last_advance_for_all_extra_gids() -> None:
    """Monospaced fonts collapse the advance array down to 1 entry and
    rely on the trailing LSB array for per-glyph bearings. ``get_advance_width``
    must return the single defined width for every glyph past index 0,
    not the LSB values."""
    blob = _pack_h(600, 0) + struct.pack(">hhhh", -3, 4, -5, 6)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=5, h_header=_StubHHEA(num_h_metrics=1))),
        MemoryTTFDataStream(blob),
    )
    for gid in range(5):
        assert table.get_advance_width(gid) == 600
    # Per-glyph LSBs for non-horizontal glyphs:
    assert table.get_left_side_bearing(0) == 0
    assert table.get_left_side_bearing(1) == -3
    assert table.get_left_side_bearing(2) == 4
    assert table.get_left_side_bearing(3) == -5
    assert table.get_left_side_bearing(4) == 6


def test_hmtx_signed_lsb_boundary_values() -> None:
    """Signed 16-bit boundary values round-trip through the signed-short
    reader: -32768 and 32767 must come back as themselves."""
    blob = _pack_h(1000, -32768) + _pack_h(1000, 32767)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=2, h_header=_StubHHEA(num_h_metrics=2))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_left_side_bearing(0) == -32768
    assert table.get_left_side_bearing(1) == 32767


def test_hmtx_unsigned_advance_full_uint16_range() -> None:
    """Advance widths are uint16 — the full 0..65535 range is valid."""
    blob = _pack_h(0, 0) + _pack_h(65535, 0)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=2, h_header=_StubHHEA(num_h_metrics=2))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_advance_width(0) == 0
    assert table.get_advance_width(1) == 65535


def test_hmtx_default_advance_width_unread_table_returns_250() -> None:
    """An unread :class:`HorizontalMetricsTable` returns the upstream
    default advance of 250 design units for every GID (see
    ``HorizontalMetricsTable.getAdvanceWidth`` upstream)."""
    table = HorizontalMetricsTable()
    for gid in (0, 5, 100, 65535):
        assert table.get_advance_width(gid) == 250
        assert table.get_left_side_bearing(gid) == 0


# ---------- vmtx ------------------------------------------------------------


def test_vmtx_boundary_gid_at_num_v_metrics_minus_one() -> None:
    blob = _pack_v(800, 5) + _pack_v(900, -3) + _pack_v(1000, 0)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=3, v_header=_StubVHEA(num_v_metrics=3))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_advance_height(0) == 800
    assert table.get_advance_height(2) == 1000
    assert table.get_top_side_bearing(2) == 0


def test_vmtx_monospaced_uses_last_advance_for_extra_gids() -> None:
    """Vertical-monospace companion of the hmtx test: a single per-glyph
    vMetric followed by per-glyph TSBs."""
    blob = _pack_v(1000, 0) + struct.pack(">hhh", -10, 11, -12)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=4, v_header=_StubVHEA(num_v_metrics=1))),
        MemoryTTFDataStream(blob),
    )
    for gid in range(4):
        assert table.get_advance_height(gid) == 1000
    assert table.get_top_side_bearing(0) == 0
    assert table.get_top_side_bearing(1) == -10
    assert table.get_top_side_bearing(2) == 11
    assert table.get_top_side_bearing(3) == -12


def test_vmtx_signed_tsb_boundary_values() -> None:
    blob = _pack_v(1000, -32768) + _pack_v(1000, 32767)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=2, v_header=_StubVHEA(num_v_metrics=2))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_top_side_bearing(0) == -32768
    assert table.get_top_side_bearing(1) == 32767


def test_vmtx_truncated_tsb_array_pads_with_zeros() -> None:
    """Companion of ``hmtx``'s ``test_read_truncated_lsb_array_pads_with_zeros``
    — same guard for the vMetric path."""
    blob = _pack_v(1000, 5) + struct.pack(">h", 7)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=4, v_header=_StubVHEA(num_v_metrics=1))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_top_side_bearing(0) == 5
    assert table.get_top_side_bearing(1) == 7
    assert table.get_top_side_bearing(2) == 0
    assert table.get_top_side_bearing(3) == 0


def test_vmtx_too_many_v_metrics_does_not_crash() -> None:
    """A bad font where ``numberOfVMetrics > numGlyphs`` must not raise
    or allocate a negative-length list. Upstream's hardening clamps
    ``number_non_vertical`` to ``num_glyphs`` in that case."""
    blob = _pack_v(800, 5) + _pack_v(900, -3)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _ttf(_StubTTF(num_glyphs=1, v_header=_StubVHEA(num_v_metrics=2))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_advance_height(0) == 800
