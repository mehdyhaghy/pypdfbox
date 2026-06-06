"""Behavioural tests for JBIG2ReadParam validation/accessor surface.

Pins the ``javax.imageio.ImageReadParam`` subset the JBIG2 plugin relies on:
subsampling-factor / offset validation, source-region and render-size guards,
and the field accessors. Targets the validation branches not reached by the
constructor's happy path (set_source_subsampling re-entry, source-region and
render-size setters).
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam


def test_default_construction():
    p = JBIG2ReadParam()
    assert p.get_source_x_subsampling() == 1
    assert p.get_source_y_subsampling() == 1
    assert p.get_subsampling_x_offset() == 0
    assert p.get_subsampling_y_offset() == 0
    assert p.get_source_region() is None
    assert p.get_source_render_size() is None
    assert p.can_set_source_render_size_() is True


def test_constructor_rejects_subsampling_below_one():
    with pytest.raises(ValueError):
        JBIG2ReadParam(source_x_subsampling=0)
    with pytest.raises(ValueError):
        JBIG2ReadParam(source_y_subsampling=0)


def test_set_source_subsampling_stores_values():
    p = JBIG2ReadParam()
    p.set_source_subsampling(3, 4, 1, 2)
    assert p.get_source_x_subsampling() == 3
    assert p.get_source_y_subsampling() == 4
    assert p.get_subsampling_x_offset() == 1
    assert p.get_subsampling_y_offset() == 2


def test_set_source_subsampling_rejects_nonpositive_factor():
    p = JBIG2ReadParam()
    with pytest.raises(ValueError):
        p.set_source_subsampling(0, 1, 0, 0)
    with pytest.raises(ValueError):
        p.set_source_subsampling(1, 0, 0, 0)


def test_set_source_subsampling_rejects_x_offset_out_of_range():
    p = JBIG2ReadParam()
    with pytest.raises(ValueError):
        p.set_source_subsampling(2, 2, -1, 0)
    with pytest.raises(ValueError):
        p.set_source_subsampling(2, 2, 2, 0)  # offset == factor is out of range


def test_set_source_subsampling_rejects_y_offset_out_of_range():
    p = JBIG2ReadParam()
    with pytest.raises(ValueError):
        p.set_source_subsampling(2, 2, 0, -1)
    with pytest.raises(ValueError):
        p.set_source_subsampling(2, 2, 0, 2)


def test_set_source_region_round_trip():
    p = JBIG2ReadParam()
    p.set_source_region((1, 2, 3, 4))
    assert p.get_source_region() == (1, 2, 3, 4)
    p.set_source_region(None)
    assert p.get_source_region() is None


def test_set_source_region_rejects_nonpositive_dimensions():
    p = JBIG2ReadParam()
    with pytest.raises(ValueError):
        p.set_source_region((0, 0, 0, 5))
    with pytest.raises(ValueError):
        p.set_source_region((0, 0, 5, 0))


def test_set_source_render_size_round_trip():
    p = JBIG2ReadParam()
    p.set_source_render_size((10, 20))
    assert p.get_source_render_size() == (10, 20)
    p.set_source_render_size(None)
    assert p.get_source_render_size() is None


def test_set_source_render_size_rejects_nonpositive_dimensions():
    p = JBIG2ReadParam()
    with pytest.raises(ValueError):
        p.set_source_render_size((0, 5))
    with pytest.raises(ValueError):
        p.set_source_render_size((5, 0))


def test_set_source_render_size_blocked_when_not_settable():
    p = JBIG2ReadParam()
    p.can_set_source_render_size = False
    with pytest.raises(ValueError):
        p.set_source_render_size((10, 20))


def test_constructor_seeds_region_and_render_size():
    p = JBIG2ReadParam(source_region=(0, 0, 8, 8), source_render_size=(16, 16))
    assert p.get_source_region() == (0, 0, 8, 8)
    assert p.get_source_render_size() == (16, 16)
