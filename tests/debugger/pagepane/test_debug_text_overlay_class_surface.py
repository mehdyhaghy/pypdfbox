"""Class-surface visibility tests for ``DebugTextStripper`` statics.

Wave 1307 ported ``transform`` and ``calculate_glyph_bounds`` as
module-level functions. Upstream Java nests them inside the inner class
``DebugTextOverlay.DebugTextStripper``. Wave 1312 re-exposes them as
``@staticmethod``s on the Python ``DebugTextStripper`` so the parity tool
counts them and so callers can use the upstream spelling
``DebugTextStripper.transform(...)``.
"""

from __future__ import annotations

from pypdfbox.debugger.pagepane import debug_text_overlay
from pypdfbox.debugger.pagepane.debug_text_overlay import DebugTextStripper


def test_transform_on_class_surface() -> None:
    assert getattr(DebugTextStripper, "transform", None) is not None
    # Identity transform leaves points unchanged.
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    assert DebugTextStripper.transform([(1.0, 2.0), (3.0, 4.0)], identity) == [
        (1.0, 2.0),
        (3.0, 4.0),
    ]
    # Pure translation: (tx, ty) = (10, 20).
    translate = (1.0, 0.0, 0.0, 1.0, 10.0, 20.0)
    assert DebugTextStripper.transform([(1.0, 2.0)], translate) == [(11.0, 22.0)]
    # Scale by 2 on x, by 3 on y.
    scale = (2.0, 0.0, 0.0, 3.0, 0.0, 0.0)
    assert DebugTextStripper.transform([(1.0, 2.0), (4.0, 5.0)], scale) == [
        (2.0, 6.0),
        (8.0, 15.0),
    ]


def test_calculate_glyph_bounds_on_class_surface_with_none_font() -> None:
    assert getattr(DebugTextStripper, "calculate_glyph_bounds", None) is not None
    # Upstream returns ``null`` when the font is missing — Python returns
    # ``None``.
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    assert DebugTextStripper.calculate_glyph_bounds(identity, None, 0, None) is None


def test_class_statics_delegate_to_module_level_functions() -> None:
    """Each class staticmethod calls the matching module-level helper."""
    captured: dict[str, tuple[object, ...]] = {}

    def _stub_transform(*args: object, **kwargs: object) -> str:
        captured["transform"] = args
        return "stub:transform"  # type: ignore[return-value]

    def _stub_calc(*args: object, **kwargs: object) -> str:
        captured["calculate_glyph_bounds"] = args
        return "stub:calc"  # type: ignore[return-value]

    original_transform = debug_text_overlay.transform
    original_calc = debug_text_overlay.calculate_glyph_bounds
    debug_text_overlay.transform = _stub_transform  # type: ignore[assignment]
    debug_text_overlay.calculate_glyph_bounds = _stub_calc  # type: ignore[assignment]
    try:
        identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        assert DebugTextStripper.transform([(0.0, 0.0)], identity) == "stub:transform"
        assert captured["transform"] == ([(0.0, 0.0)], identity)
        assert (
            DebugTextStripper.calculate_glyph_bounds(identity, "font", 7, "disp")
            == "stub:calc"
        )
        assert captured["calculate_glyph_bounds"] == (identity, "font", 7, "disp")
    finally:
        debug_text_overlay.transform = original_transform  # type: ignore[assignment]
        debug_text_overlay.calculate_glyph_bounds = original_calc  # type: ignore[assignment]
