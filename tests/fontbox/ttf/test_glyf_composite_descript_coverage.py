"""Coverage-boost tests for ``pypdfbox.fontbox.ttf.glyf_composite_descript``.

Targets the byte-stream constructor (single-component + instructions
trailer), ``init_descriptions`` (with single-arg and two-arg
``get_glyph``, both with a missing entry and with a missing
``get_glyph`` attribute), ``resolve`` early-return short circuit, the
"missing description for the requested index" branches in the accessor
helpers, and the ``from_glyph`` library-first adapter for both colored
and uncolored ranges.
"""

from __future__ import annotations

import struct
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import (
    GlyfCompositeDescript,
    _to_signed_short,
)
from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream


# ---------- Helpers -----------------------------------------------------


def _make_component_bytes(
    *, flags: int, glyph_index: int, arg1: int, arg2: int
) -> bytes:
    """Encode one minimal component record (byte args, no transform)."""
    # 16-bit flags + 16-bit glyph index, then 8-bit args (no ARG_1_AND_2_ARE_WORDS).
    return struct.pack(">HHbb", flags & 0xFFFF, glyph_index & 0xFFFF, arg1, arg2)


# ---------- _to_signed_short ----------------------------------------------


def test_to_signed_short_negative_wraparound() -> None:
    # 0xFFFF -> -1 in signed-16
    assert _to_signed_short(0xFFFF) == -1


def test_to_signed_short_positive_passthrough() -> None:
    assert _to_signed_short(0x7FFF) == 32767


def test_to_signed_short_zero() -> None:
    assert _to_signed_short(0) == 0


def test_to_signed_short_value_above_short_range_wraps() -> None:
    # 0x18000 -> & 0xFFFF -> 0x8000 -> -32768
    assert _to_signed_short(0x18000) == -32768


# ---------- Byte-stream constructor ---------------------------------------


def test_byte_stream_ctor_reads_single_component_no_instructions() -> None:
    """Single component with MORE_COMPONENTS cleared, no instructions trailer."""
    flags = GlyfCompositeComp.ARGS_ARE_XY_VALUES
    payload = _make_component_bytes(flags=flags, glyph_index=7, arg1=4, arg2=-3)
    stream = RandomAccessReadDataStream(payload)
    descript = GlyfCompositeDescript(bais=stream, glyph_table=None)
    assert descript.get_component_count() == 1
    only = descript.get_components()[0]
    assert only.get_glyph_index() == 7
    assert only.get_x_translate() == 4
    assert only.get_y_translate() == -3
    # No instructions consumed.
    assert descript._instructions is None


def test_byte_stream_ctor_reads_chain_of_two_components() -> None:
    flags_more = (
        GlyfCompositeComp.ARGS_ARE_XY_VALUES | GlyfCompositeComp.MORE_COMPONENTS
    )
    flags_last = GlyfCompositeComp.ARGS_ARE_XY_VALUES  # no MORE_COMPONENTS
    payload = _make_component_bytes(
        flags=flags_more, glyph_index=1, arg1=0, arg2=0
    ) + _make_component_bytes(
        flags=flags_last, glyph_index=2, arg1=5, arg2=6
    )
    stream = RandomAccessReadDataStream(payload)
    descript = GlyfCompositeDescript(bais=stream, glyph_table=None)
    assert descript.get_component_count() == 2
    assert descript.get_components()[0].get_glyph_index() == 1
    assert descript.get_components()[1].get_glyph_index() == 2


def test_byte_stream_ctor_reads_instructions_trailer() -> None:
    """WE_HAVE_INSTRUCTIONS on the last component triggers the instructions read."""
    flags = (
        GlyfCompositeComp.ARGS_ARE_XY_VALUES
        | GlyfCompositeComp.WE_HAVE_INSTRUCTIONS
    )
    comp_bytes = _make_component_bytes(flags=flags, glyph_index=3, arg1=0, arg2=0)
    # uint16 count = 4, then 4 instruction bytes.
    instr_bytes = struct.pack(">H", 4) + bytes([0x01, 0x02, 0x03, 0x04])
    stream = RandomAccessReadDataStream(comp_bytes + instr_bytes)
    descript = GlyfCompositeDescript(bais=stream, glyph_table=None)
    assert descript._instructions == [0x01, 0x02, 0x03, 0x04]


# ---------- init_descriptions branches -----------------------------------


def test_init_descriptions_is_noop_without_glyph_table() -> None:
    composite = GlyfCompositeDescript()
    composite._components.append(GlyfCompositeComp())
    composite.init_descriptions(0)  # should not raise; nothing populated.
    assert composite._descriptions == {}


def test_init_descriptions_handles_table_without_get_glyph() -> None:
    """Table-like that lacks ``get_glyph`` -> nothing populated, no raise."""

    class _NoGetGlyph:
        pass

    composite = GlyfCompositeDescript()
    composite._components.append(GlyfCompositeComp())
    composite._glyph_table = _NoGetGlyph()
    composite.init_descriptions(0)
    assert composite._descriptions == {}


def test_init_descriptions_uses_two_arg_get_glyph_when_available() -> None:
    class _Sub:
        def __init__(self, desc: GlyfDescript) -> None:
            self._desc = desc

        def get_description(self) -> GlyfDescript:
            return self._desc

    sub_descript = GlyfDescript(1)

    class _GlyphTable:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        def get_glyph(self, index: int, level: int) -> _Sub:
            self.calls.append((index, level))
            return _Sub(sub_descript)

    comp = GlyfCompositeComp()
    comp._glyph_index = 4
    composite = GlyfCompositeDescript()
    composite._components.append(comp)
    table = _GlyphTable()
    composite._glyph_table = table
    composite.init_descriptions(2)
    assert table.calls == [(4, 2)]
    assert composite._descriptions[4] is sub_descript


def test_init_descriptions_falls_back_to_one_arg_get_glyph() -> None:
    sub_descript = GlyfDescript(1)

    class _Sub:
        def get_description(self) -> GlyfDescript:
            return sub_descript

    class _GlyphTable:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def get_glyph(self, index: int) -> _Sub:
            self.calls.append(index)
            return _Sub()

    comp = GlyfCompositeComp()
    comp._glyph_index = 9
    composite = GlyfCompositeDescript()
    composite._components.append(comp)
    table = _GlyphTable()
    composite._glyph_table = table
    composite.init_descriptions(0)
    assert table.calls == [9]
    assert composite._descriptions[9] is sub_descript


def test_init_descriptions_handles_none_returned_from_get_glyph() -> None:
    class _GlyphTable:
        def get_glyph(self, _index: int, _level: int) -> Any:
            return None

    comp = GlyfCompositeComp()
    comp._glyph_index = 11
    composite = GlyfCompositeDescript()
    composite._components.append(comp)
    composite._glyph_table = _GlyphTable()
    composite.init_descriptions(0)
    assert 11 not in composite._descriptions


def test_init_descriptions_swallows_oserror_from_get_glyph(caplog) -> None:
    """``get_glyph`` raising ``OSError`` is logged and skipped (lines 122-123)."""
    import logging

    class _BoomTable:
        def get_glyph(self, _index: int, _level: int) -> Any:
            raise OSError("disk gone")

    comp = GlyfCompositeComp()
    comp._glyph_index = 13
    composite = GlyfCompositeDescript()
    composite._components.append(comp)
    composite._glyph_table = _BoomTable()
    with caplog.at_level(logging.ERROR, logger="pypdfbox.fontbox.ttf.glyf_composite_descript"):
        composite.init_descriptions(0)
    assert 13 not in composite._descriptions
    assert any("failed to load component description" in r.getMessage() for r in caplog.records)


# ---------- resolve / short-circuit --------------------------------------


def test_resolve_is_idempotent() -> None:
    composite = GlyfCompositeDescript()
    composite.resolve()
    composite.resolve()  # second call short-circuits via _resolved (line 79)
    assert composite._resolved is True


def test_resolve_skips_missing_description() -> None:
    """Components with no description -> resolve() leaves first_index at 0."""
    composite = GlyfCompositeDescript()
    comp = GlyfCompositeComp()
    comp._glyph_index = 99
    composite._components.append(comp)
    # No descriptions populated for index 99.
    composite.resolve()
    assert comp.get_first_index() == 0
    assert comp.get_first_contour() == 0


# ---------- Accessor missing-description branches -----------------------


def test_get_end_pt_of_contours_missing_returns_zero() -> None:
    # No components, no descriptions -> 0.
    composite = GlyfCompositeDescript()
    assert composite.get_end_pt_of_contours(5) == 0


def test_get_flags_missing_returns_zero() -> None:
    composite = GlyfCompositeDescript()
    assert composite.get_flags(0) == 0


def test_get_x_coordinate_missing_returns_zero() -> None:
    composite = GlyfCompositeDescript()
    assert composite.get_x_coordinate(0) == 0


def test_get_y_coordinate_missing_returns_zero() -> None:
    composite = GlyfCompositeDescript()
    assert composite.get_y_coordinate(0) == 0


# ---------- get_point_count / get_contour_count missing-desc fallbacks --


def test_point_count_missing_description_returns_zero() -> None:
    composite = GlyfCompositeDescript()
    comp = GlyfCompositeComp()
    comp._glyph_index = 42
    composite._components.append(comp)
    composite._resolved = True  # bypass "called on unresolved" log
    assert composite.get_point_count() == 0


def test_contour_count_missing_description_returns_zero() -> None:
    composite = GlyfCompositeDescript()
    comp = GlyfCompositeComp()
    comp._glyph_index = 42
    composite._components.append(comp)
    composite._resolved = True
    assert composite.get_contour_count() == 0


# ---------- from_glyph (library-first adapter) --------------------------


def test_from_glyph_rejects_non_composite_glyph() -> None:
    class _SimpleGlyph:
        def isComposite(self) -> bool:
            return False

    with pytest.raises(ValueError, match="composite"):
        GlyfCompositeDescript.from_glyph(
            _SimpleGlyph(), object(), description_for_index=lambda _i: None
        )


def test_from_glyph_populates_components_and_descriptions() -> None:
    """Composite glyph with two components -> both end up in the
    components list and in the descriptions map (skipping None).
    """
    sub_desc = GlyfSimpleDescript()
    sub_desc._contour_count = 1
    sub_desc._end_pts_of_contours = [0]
    sub_desc._flags = [GlyfDescript.ON_CURVE]
    sub_desc._x_coordinates = [0]
    sub_desc._y_coordinates = [0]
    sub_desc._point_count = 1

    class _Component:
        def __init__(self, glyph_id: int) -> None:
            self.glyphID = glyph_id
            self.flags = GlyfCompositeComp.ARGS_ARE_XY_VALUES
            self.x = 1
            self.y = 2
            # Identity transform.
            self.transform = ((1.0, 0.0), (0.0, 1.0))

    class _CompositeGlyph:
        def __init__(self) -> None:
            self.components = [_Component(1), _Component(2)]

        def isComposite(self) -> bool:
            return True

    def _desc_lookup(index: int) -> GlyfSimpleDescript | None:
        return sub_desc if index == 1 else None

    descript = GlyfCompositeDescript.from_glyph(
        _CompositeGlyph(), object(), description_for_index=_desc_lookup
    )
    assert descript.get_component_count() == 2
    # Index 1 has a description, index 2 returned None -> not in dict.
    assert 1 in descript._descriptions
    assert 2 not in descript._descriptions
