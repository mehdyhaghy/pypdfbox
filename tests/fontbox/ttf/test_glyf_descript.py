"""Tests for :class:`pypdfbox.fontbox.ttf.glyf_descript.GlyfDescript`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def test_outline_flag_constants() -> None:
    # Constants must match the upstream byte values from
    # GlyfDescript.java lines 33-64.
    assert GlyfDescript.ON_CURVE == 0x01
    assert GlyfDescript.X_SHORT_VECTOR == 0x02
    assert GlyfDescript.Y_SHORT_VECTOR == 0x04
    assert GlyfDescript.REPEAT == 0x08
    assert GlyfDescript.X_DUAL == 0x10
    assert GlyfDescript.Y_DUAL == 0x20


def test_default_state() -> None:
    d = GlyfDescript(3)
    assert d.get_contour_count() == 3
    assert d.get_number_of_contours() == 3
    assert d.get_instructions() is None
    # resolve() is a no-op on the base.
    d.resolve()


def test_default_abstract_methods_return_degenerate_values() -> None:
    """The base provides degenerate defaults — an "empty descript".

    Upstream's ``GlyphDescription`` interface declares these abstract;
    the Python port keeps the surface but supplies sensible defaults so
    callers holding a generic :class:`GlyfDescript` reference don't
    have to special-case the "no concrete subclass" path. Concrete
    subclasses (:class:`GlyfSimpleDescript` /
    :class:`GlyfCompositeDescript`) override every accessor.
    """
    d = GlyfDescript(0)
    assert d.is_composite() is False
    assert d.get_point_count() == 0
    assert d.get_end_pt_of_contours(0) == -1
    assert d.get_flags(0) == 0
    assert d.get_x_coordinate(0) == 0
    assert d.get_y_coordinate(0) == 0


def test_read_instructions() -> None:
    # Three bytes that should be lifted into the instructions array as
    # unsigned ints.
    stream = MemoryTTFDataStream(bytes([0xAB, 0x01, 0xFF]))
    d = GlyfDescript(0)
    d.read_instructions(stream, 3)
    assert d.get_instructions() == [0xAB, 0x01, 0xFF]


def test_default_bbox_accessors_return_zero() -> None:
    d = GlyfDescript(0)
    assert d.get_x_min() == 0
    assert d.get_x_max() == 0
    assert d.get_y_min() == 0
    assert d.get_y_max() == 0
