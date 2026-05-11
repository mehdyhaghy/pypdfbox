"""Functional-interface for non-separable blend modes.

Mirrors ``BlendMode.BlendFunction`` from upstream ``BlendMode`` (PDFBox
``pdmodel.graphics.blend.BlendMode``). The single method takes ``src``,
``dest`` and a ``result`` array and writes the blended RGB into the
result in place.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence


class BlendFunction:
    """Adapter mirroring Java's functional interface."""

    __slots__ = ("_fn",)

    def __init__(
        self,
        fn: Callable[[Sequence[float], Sequence[float], list[float]], None],
    ) -> None:
        self._fn = fn

    def blend(
        self,
        src: Sequence[float],
        dest: Sequence[float],
        result: list[float],
    ) -> None:
        """Apply the non-separable blend, writing into ``result``."""
        self._fn(src, dest, result)

    def __call__(
        self,
        src: Sequence[float],
        dest: Sequence[float],
        result: list[float],
    ) -> None:
        self._fn(src, dest, result)


__all__ = ["BlendFunction"]
