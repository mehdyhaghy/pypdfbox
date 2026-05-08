from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.state import RenderingIntent, RenderingMode


def test_rendering_intent_java_aliases_match_pythonic_methods() -> None:
    assert RenderingIntent.fromString("Perceptual") is RenderingIntent.from_string(
        "Perceptual"
    )
    assert RenderingIntent.fromString("Bogus") is RenderingIntent.from_string("Bogus")
    assert RenderingIntent.fromString(None) is RenderingIntent.from_string(None)

    assert RenderingIntent.SATURATION.stringValue() == (
        RenderingIntent.SATURATION.string_value()
    )


def test_rendering_mode_java_aliases_match_pythonic_methods() -> None:
    assert RenderingMode.fromInt(2) is RenderingMode.from_int(2)
    with pytest.raises(IndexError):
        RenderingMode.fromInt(99)

    mode = RenderingMode.FILL_STROKE_CLIP
    assert mode.intValue() == mode.int_value()
    assert mode.isFill() is mode.is_fill()
    assert mode.isStroke() is mode.is_stroke()
    assert mode.isClip() is mode.is_clip()


@pytest.mark.parametrize(
    ("mode", "is_fill", "is_stroke", "is_clip"),
    [
        (RenderingMode.FILL, True, False, False),
        (RenderingMode.STROKE, False, True, False),
        (RenderingMode.NEITHER, False, False, False),
        (RenderingMode.NEITHER_CLIP, False, False, True),
    ],
)
def test_rendering_mode_java_predicates_keep_mode_classification(
    mode: RenderingMode, is_fill: bool, is_stroke: bool, is_clip: bool
) -> None:
    assert mode.isFill() is is_fill
    assert mode.isStroke() is is_stroke
    assert mode.isClip() is is_clip
