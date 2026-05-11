"""Tests for the graphics state cluster (Wave 1281)."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.state import (
    PDGraphicsState,
    PDTextState,
    RenderingMode,
)


def test_text_state_defaults():
    ts = PDTextState()
    assert ts.get_character_spacing() == 0
    assert ts.get_word_spacing() == 0
    assert ts.get_horizontal_scaling() == 100
    assert ts.get_leading() == 0
    assert ts.get_rise() == 0
    assert ts.get_knockout_flag() is True
    assert ts.get_rendering_mode() is RenderingMode.FILL


def test_text_state_set_get_round_trip():
    ts = PDTextState()
    ts.set_character_spacing(2.5)
    ts.set_word_spacing(1.0)
    ts.set_horizontal_scaling(120)
    ts.set_leading(14)
    ts.set_font_size(12)
    ts.set_rise(-2)
    ts.set_knockout_flag(False)
    ts.set_rendering_mode(RenderingMode.STROKE)
    assert ts.get_character_spacing() == 2.5
    assert ts.get_word_spacing() == 1.0
    assert ts.get_horizontal_scaling() == 120
    assert ts.get_leading() == 14
    assert ts.get_font_size() == 12
    assert ts.get_rise() == -2
    assert ts.get_knockout_flag() is False
    assert ts.get_rendering_mode() is RenderingMode.STROKE


def test_text_state_clone_is_independent():
    ts = PDTextState()
    ts.set_font_size(10)
    clone = ts.clone()
    clone.set_font_size(20)
    assert ts.get_font_size() == 10
    assert clone.get_font_size() == 20


def test_graphics_state_defaults():
    gs = PDGraphicsState()
    assert gs.get_line_width() == 1.0
    assert gs.get_miter_limit() == 10
    assert gs.get_blend_mode() is BlendMode.NORMAL
    assert gs.get_alpha_constant() == 1.0
    assert gs.is_overprint() is False
    assert isinstance(gs.get_text_state(), PDTextState)


def test_graphics_state_set_blend_mode_rejects_none():
    gs = PDGraphicsState()
    with pytest.raises(ValueError):
        gs.set_blend_mode(None)


def test_graphics_state_clone_independent_text_state():
    gs = PDGraphicsState()
    gs.get_text_state().set_font_size(8)
    clone = gs.clone()
    clone.get_text_state().set_font_size(24)
    assert gs.get_text_state().get_font_size() == 8
    assert clone.get_text_state().get_font_size() == 24


def test_graphics_state_clipping_intersection():
    gs = PDGraphicsState()
    gs.intersect_clipping_path("path-1")
    gs.intersect_clipping_path("path-2")
    paths = gs.get_current_clipping_paths()
    assert "path-1" in paths
    assert "path-2" in paths


def test_graphics_state_composite_dispatches_blend_composite():
    gs = PDGraphicsState()
    gs.set_alpha_constant(0.6)
    composite = gs.get_stroking_java_composite()
    # NORMAL mode returns the SRC_OVER sentinel from BlendComposite.
    assert isinstance(composite, tuple)
    assert composite[1] == 0.6
