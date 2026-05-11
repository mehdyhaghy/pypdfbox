"""Tests for the ``pdmodel.graphics.blend`` cluster (Wave 1281)."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.blend import (
    BlendChannelFunction,
    BlendComposite,
    BlendCompositeContext,
    BlendFunction,
)
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode


def test_blend_channel_function_call_and_method():
    fn = BlendChannelFunction(lambda s, d: s + d)
    assert fn.blend_channel(0.3, 0.4) == pytest.approx(0.7)
    assert fn(0.1, 0.2) == pytest.approx(0.3)


def test_blend_function_call_and_method():
    def add_rgb(src, dest, result):
        for i in range(3):
            result[i] = src[i] + dest[i]

    fn = BlendFunction(add_rgb)
    out = [0.0, 0.0, 0.0]
    fn.blend([0.1, 0.2, 0.3], [0.4, 0.4, 0.4], out)
    assert out == pytest.approx([0.5, 0.6, 0.7])


def test_blend_composite_normal_returns_src_over_sentinel():
    result = BlendComposite.get_instance(BlendMode.NORMAL, 0.5)
    assert isinstance(result, tuple)
    assert result[0] == "AlphaComposite.SRC_OVER"
    assert result[1] == 0.5


def test_blend_composite_alpha_is_clamped():
    above = BlendComposite.get_instance(BlendMode.NORMAL, 1.5)
    below = BlendComposite.get_instance(BlendMode.NORMAL, -0.2)
    assert above[1] == 1.0
    assert below[1] == 0.0


def test_blend_composite_rejects_null_mode():
    with pytest.raises(ValueError):
        BlendComposite.get_instance(None, 0.5)


def test_blend_composite_nonnormal_builds_instance():
    bc = BlendComposite.get_instance(BlendMode.MULTIPLY, 0.7)
    assert isinstance(bc, BlendComposite)
    assert bc.blend_mode is BlendMode.MULTIPLY
    assert bc.constant_alpha == 0.7
    ctx = bc.create_context(None, None, None)
    assert isinstance(ctx, BlendCompositeContext)
    ctx.dispose()
