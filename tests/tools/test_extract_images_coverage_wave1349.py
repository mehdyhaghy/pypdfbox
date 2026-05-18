"""Wave 1349 coverage-boost tests for :mod:`pypdfbox.tools.extract_images`.

Targets the three uncovered branches left by wave 1319/1332:

* line 66 — soft-mask present but its ``get_group()`` returns ``None`` →
  ``continue`` skips the dispatch.
* lines 70-71 — ``copy_into_graphics_state`` / ``process_soft_mask``
  raise ``AttributeError`` / ``NotImplementedError`` → swallowed by the
  outer ``try``/``except``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.tools import extract_images


def test_run_soft_mask_with_none_group_skipped() -> None:
    """When ``soft_mask.get_group()`` returns ``None``, the loop body
    short-circuits at line 66 without dispatching ``process_soft_mask``."""
    outer = extract_images.ExtractImages()

    class _SoftMaskNoGroup:
        def get_group(self) -> Any:
            return None

    class _ExtGState:
        def get_soft_mask(self) -> _SoftMaskNoGroup:
            return _SoftMaskNoGroup()

    class _Resources:
        def get_ext_g_state_names(self) -> list[str]:
            return ["GS-no-group"]

        def get_ext_g_state(self, _name: str) -> _ExtGState:
            return _ExtGState()

    class _Page:
        def get_resources(self) -> _Resources:
            return _Resources()

    engine = extract_images.ImageGraphicsEngine(page=_Page(), outer=outer)
    engine.process_page = lambda _p: None  # type: ignore[method-assign]
    captured: list[object] = []
    engine.process_soft_mask = lambda g: captured.append(g)  # type: ignore[method-assign]
    engine.get_graphics_state = lambda: object()  # type: ignore[method-assign]
    engine.run()
    # Group was None → process_soft_mask never called.
    assert captured == []


def test_run_soft_mask_copy_into_graphics_state_raises_swallowed() -> None:
    """If ``copy_into_graphics_state`` raises ``AttributeError`` /
    ``NotImplementedError``, the outer try-except at lines 67-71 swallows
    it and the loop continues without crashing."""
    outer = extract_images.ExtractImages()

    class _Group:
        pass

    group = _Group()

    class _SoftMask:
        def get_group(self) -> _Group:
            return group

    class _ExtGState:
        def get_soft_mask(self) -> _SoftMask:
            return _SoftMask()

        def copy_into_graphics_state(self, _state: object) -> None:
            raise AttributeError("synthetic: copy_into_graphics_state unsupported")

    class _Resources:
        def get_ext_g_state_names(self) -> list[str]:
            return ["GS-raises"]

        def get_ext_g_state(self, _name: str) -> _ExtGState:
            return _ExtGState()

    class _Page:
        def get_resources(self) -> _Resources:
            return _Resources()

    engine = extract_images.ImageGraphicsEngine(page=_Page(), outer=outer)
    engine.process_page = lambda _p: None  # type: ignore[method-assign]
    captured: list[object] = []
    engine.process_soft_mask = lambda g: captured.append(g)  # type: ignore[method-assign]
    engine.get_graphics_state = lambda: object()  # type: ignore[method-assign]
    # Should not raise; exception is caught and the loop moves on.
    engine.run()
    # process_soft_mask never reached because copy_into_graphics_state raised first.
    assert captured == []


def test_run_soft_mask_process_soft_mask_raises_swallowed() -> None:
    """If ``process_soft_mask`` raises ``NotImplementedError`` after the
    state copy succeeds, the same outer try-except swallows it."""
    outer = extract_images.ExtractImages()

    class _Group:
        pass

    class _SoftMask:
        def get_group(self) -> _Group:
            return _Group()

    class _ExtGState:
        def get_soft_mask(self) -> _SoftMask:
            return _SoftMask()

        def copy_into_graphics_state(self, _state: object) -> None:
            return None

    class _Resources:
        def get_ext_g_state_names(self) -> list[str]:
            return ["GS"]

        def get_ext_g_state(self, _name: str) -> _ExtGState:
            return _ExtGState()

    class _Page:
        def get_resources(self) -> _Resources:
            return _Resources()

    engine = extract_images.ImageGraphicsEngine(page=_Page(), outer=outer)
    engine.process_page = lambda _p: None  # type: ignore[method-assign]

    def _raise(_g: object) -> None:
        raise NotImplementedError("synthetic: process_soft_mask unsupported")

    engine.process_soft_mask = _raise  # type: ignore[method-assign]
    engine.get_graphics_state = lambda: object()  # type: ignore[method-assign]
    engine.run()  # no exception
