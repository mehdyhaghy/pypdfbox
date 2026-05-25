"""Wave 1397 branch-coverage tests for the ImageGraphicsEngine in
``pypdfbox.tools.extract_images``.

Closes False-branch arrows in ``show_glyph`` / ``process_color``:

* 125->127 — render-mode is NOT fill (skip the non-stroking branch)
* 127->exit — render-mode is NOT stroke either (both False; exit cleanly)
* 154->exit — ``cs.get_pattern(color)`` returns something that isn't a
  PDTilingPattern (skip the tiling-pattern dispatch)
"""

from __future__ import annotations

from typing import Any

from pypdfbox.tools import extract_images


def _build_engine() -> extract_images.ImageGraphicsEngine:
    outer = extract_images.ExtractImages()

    class _Page:
        def get_resources(self) -> Any:
            return None

    return extract_images.ImageGraphicsEngine(page=_Page(), outer=outer)


def test_show_glyph_render_mode_neither_fill_nor_stroke_no_op() -> None:
    """Closes 125->127 AND 127->exit: a render-mode reporting both
    ``is_fill`` and ``is_stroke`` False causes ``process_color`` never
    to be invoked."""
    engine = _build_engine()

    class _RM:
        def is_fill(self) -> bool:
            return False

        def is_stroke(self) -> bool:
            return False

    class _TextState:
        def get_rendering_mode(self) -> _RM:
            return _RM()

    class _GState:
        def get_text_state(self) -> _TextState:
            return _TextState()

        def get_non_stroking_color(self) -> Any:
            raise AssertionError("must not be called")

        def get_stroking_color(self) -> Any:
            raise AssertionError("must not be called")

    engine.get_graphics_state = lambda: _GState()  # type: ignore[method-assign]
    engine.process_color = lambda c: None  # type: ignore[method-assign]
    # Should not raise.
    engine.show_glyph(None, None, 0, None)


def test_process_color_skips_when_pattern_is_not_tiling() -> None:
    """Closes 154->exit: ``cs.get_pattern(color)`` returns a non-tiling
    abstract pattern — the ``process_tiling_pattern`` dispatch is
    skipped."""
    engine = _build_engine()
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    class _NonTilingPattern:
        """An abstract pattern that is NOT a PDTilingPattern."""

    class _PDPatternStub(PDPattern):
        def get_pattern(self, color: Any) -> Any:  # noqa: ARG002
            return _NonTilingPattern()

    class _Color:
        def get_color_space(self) -> _PDPatternStub:
            return _PDPatternStub()

    called: list[Any] = []
    engine.process_tiling_pattern = lambda *args, **kw: called.append(args)  # type: ignore[method-assign]
    engine.process_color(_Color())
    assert called == []
