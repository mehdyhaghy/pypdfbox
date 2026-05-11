"""Functional-interface for separable blend modes.

Mirrors the ``BlendMode.BlendChannelFunction`` inner interface in
``org.apache.pdfbox.pdmodel.graphics.blend.BlendMode``. Java models this
as a single-abstract-method (``@FunctionalInterface``) interface; in
Python we expose a ``Protocol`` + ``__call__`` and a tiny adapter so
callers can wrap a plain function.
"""

from __future__ import annotations

from collections.abc import Callable


class BlendChannelFunction:
    """Adapter mirroring Java's functional interface.

    Holds a single callable ``f(src, dest) -> float``. ``blend_channel``
    is the upstream method name; ``__call__`` delegates so instances are
    usable wherever a plain function is.
    """

    __slots__ = ("_fn",)

    def __init__(self, fn: Callable[[float, float], float]) -> None:
        self._fn = fn

    def blend_channel(self, src: float, dest: float) -> float:
        """Apply the separable channel blend."""
        return self._fn(src, dest)

    def __call__(self, src: float, dest: float) -> float:
        return self._fn(src, dest)


__all__ = ["BlendChannelFunction"]
