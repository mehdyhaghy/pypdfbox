"""Wave 1369 round-out tests for :class:`MaximumProfileTable`.

Focus areas the earlier waves did not cover:

* Outline-flavour predicate boundary across the 1.0 version threshold
  (anything ``< 1.0`` is CFF, ``>= 1.0`` is TrueType).
* Explicit version 1.0 round-trip (set + get).
* PDFBOX-6105 fix-up does **not** fire when ``read`` is fed a v0.5
  table — the post-glyph fields stay at their zero defaults.
* v1.0 ``read`` where every field is at the unsigned-short max value
  (0xFFFF) round-trips.
* The maxComponentDepth ``0 → 1`` promotion documented as PDFBOX-6105
  is bounded by the ``version >= 1.0`` predicate — a v0.5 table cannot
  promote because the field is never read.
"""

from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.maximum_profile_table import MaximumProfileTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _pack_v05(num_glyphs: int) -> bytes:
    # version 0.5 — high 16 bits = 0, low 16 bits = 0x5000 → 0.3125
    return struct.pack(">hHH", 0, 0x5000, num_glyphs)


def _pack_v10_all_max() -> bytes:
    return struct.pack(
        ">hH" + "H" * 14,
        1,
        0,  # version 1.0
        65535,  # numGlyphs
        65535, 65535, 65535, 65535, 65535, 65535,
        65535, 65535, 65535, 65535, 65535, 65535, 65535,
    )


# ---------- outline-flavour predicate boundary -----------------------------


def test_outline_predicate_just_below_one_dot_zero() -> None:
    """The boundary is strict — version ``0.9999847412109375`` (one ULP
    below 1.0 at 16.16 fixed) still resolves as PostScript outlines."""
    table = MaximumProfileTable()
    # 0x0000FFFF = 0.9999847412109375 at 16.16 fixed-point.
    table.set_version(0 + 0xFFFF / 65536.0)
    assert table.is_post_script_outlines() is True
    assert table.is_true_type_outlines() is False


def test_outline_predicate_exactly_one_dot_zero() -> None:
    table = MaximumProfileTable()
    table.set_version(1.0)
    assert table.is_true_type_outlines() is True
    assert table.is_post_script_outlines() is False


def test_outline_predicate_just_above_one_dot_zero() -> None:
    table = MaximumProfileTable()
    # 1 + tiny epsilon.
    table.set_version(1.0 + 1 / 65536.0)
    assert table.is_true_type_outlines() is True


def test_outline_predicate_pre_read_defaults_to_post_script() -> None:
    """A fresh table has version 0.0 (pre-read) and should classify as
    PostScript outlines — matches the upstream pre-init state where
    ``MaximumProfileTable.version`` defaults to 0.0f."""
    table = MaximumProfileTable()
    assert table.get_version() == 0.0
    assert table.is_post_script_outlines() is True


# ---------- PDFBOX-6105 promotion guard -------------------------------------


def test_v05_read_does_not_promote_max_component_depth() -> None:
    """The PDFBOX-6105 ``maxComponentDepth=0 → 1`` fix-up only applies
    inside the ``version >= 1.0`` branch in ``read``. A v0.5 stream never
    touches the post-glyph fields, so ``max_component_depth`` stays at 0."""
    raw = _pack_v05(42)
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_max_component_depth() == 0


def test_setter_zero_after_read_is_not_promoted() -> None:
    """``set_max_component_depth(0)`` is *not* part of the parser flow,
    so the upstream PDFBOX-6105 fix-up does not re-fire — the field
    sticks at the requested zero."""
    raw = struct.pack(
        ">hH" + "H" * 14,
        1, 0, 100,
        50, 5, 100, 10, 2, 16, 32, 64, 0, 256, 1024, 5, 3,
    )
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    # Sanity: the parser bumped 3 onto the post-glyph slot.
    assert table.get_max_component_depth() == 3
    table.set_max_component_depth(0)
    assert table.get_max_component_depth() == 0


# ---------- v1.0 with every field at unsigned-short max --------------------


def test_v10_all_fields_at_max_unsigned_short() -> None:
    """Every uint16 field at 0xFFFF must round-trip — sanity-checks the
    unsigned-short reader on the entire v1.0 layout."""
    raw = _pack_v10_all_max()
    table = MaximumProfileTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_num_glyphs() == 65535
    assert table.get_max_points() == 65535
    assert table.get_max_contours() == 65535
    assert table.get_max_composite_points() == 65535
    assert table.get_max_composite_contours() == 65535
    assert table.get_max_zones() == 65535
    assert table.get_max_twilight_points() == 65535
    assert table.get_max_storage() == 65535
    assert table.get_max_function_defs() == 65535
    assert table.get_max_instruction_defs() == 65535
    assert table.get_max_stack_elements() == 65535
    assert table.get_max_size_of_instructions() == 65535
    assert table.get_max_component_elements() == 65535
    # Promotion does not affect a non-zero field.
    assert table.get_max_component_depth() == 65535


def test_read_marks_initialized_for_both_versions() -> None:
    for raw in (_pack_v05(10), _pack_v10_all_max()):
        table = MaximumProfileTable()
        assert table.get_initialized() is False
        table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
        assert table.get_initialized() is True
