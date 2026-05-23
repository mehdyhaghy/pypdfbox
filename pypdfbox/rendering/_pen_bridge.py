"""Bridge layer between fontTools' :class:`BasePen` camelCase contract
and the snake_case Pen-protocol used by pypdfbox's internal pens.

The fontTools pen protocol (``glyph.draw(pen)``) calls ``moveTo`` /
``lineTo`` / ``curveTo`` / ``qCurveTo`` / ``closePath`` / ``endPath`` /
``addComponent`` on its argument by **name**. To keep our own pen
classes strictly snake_case (no Java-style aliases, project rule
"feedback_no_camelcase_aliases"), we route every ``glyph.draw`` call
through :class:`_BasePenBridge`, which subclasses fontTools' real
:class:`BasePen` and dispatches each camelCase entry-point to the
matching snake_case method on a delegate object.

The bridge is the **only** place in pypdfbox that is allowed to declare
camelCase methods; the seven ``# noqa: N802`` comments below are the
fontTools BasePen contract — not aliases, but the framework's own
public method names that we are required to expose when extending
``BasePen``.
"""

from __future__ import annotations

from typing import Any, Protocol


class _SnakePen(Protocol):
    """Minimal snake_case pen protocol the bridge delegates to.

    Implementations only need to define the methods they actually use;
    missing methods fall through to a silent no-op (so the bridge can
    be reused with collectors that, for example, ignore composite
    ``add_component`` references).
    """

    def move_to(self, pt: tuple[float, float]) -> None: ...
    def line_to(self, pt: tuple[float, float]) -> None: ...
    def curve_to(self, *points: tuple[float, float]) -> None: ...
    def q_curve_to(self, *points: tuple[float, float] | None) -> None: ...
    def close_path(self) -> None: ...
    def end_path(self) -> None: ...
    def add_component(
        self,
        glyph_name: str,
        transformation: tuple[float, float, float, float, float, float],
    ) -> None: ...


def make_base_pen_bridge(delegate: Any, glyph_set: Any | None = None) -> Any:
    """Build and return a :class:`fontTools.pens.basePen.BasePen`-shaped
    bridge whose camelCase methods forward to ``delegate``'s snake_case
    methods. ``glyph_set`` is forwarded to ``BasePen.__init__`` for
    fontTools' built-in composite decomposition (when ``addComponent``
    isn't overridden in the delegate).

    Lazily imports :mod:`fontTools.pens.basePen` so callers that never
    rasterise glyphs do not pay the import cost (fontTools pulls in a
    fairly large module graph).
    """
    from fontTools.pens.basePen import BasePen  # type: ignore[import-untyped]  # noqa: PLC0415

    class _BasePenBridge(BasePen):  # type: ignore[misc]
        """Bridge between fontTools' BasePen camelCase API and a
        snake_case Pen-protocol delegate.

        Overrides each of the seven public ``BasePen`` entry points so
        the delegate receives the exact same call shape fontTools
        produced — no quadratic-to-cubic decomposition, no per-segment
        unrolling. The delegate is free to do whatever segmentation it
        likes in its own snake_case method bodies.
        """

        def __init__(
            self, delegate: Any, glyph_set: Any | None = None
        ) -> None:
            super().__init__(glyph_set)
            self._delegate = delegate

        def moveTo(self, pt: tuple[float, float]) -> None:  # noqa: N802 - BasePen contract
            fn = getattr(self._delegate, "move_to", None)
            if fn is not None:
                fn(pt)

        def lineTo(self, pt: tuple[float, float]) -> None:  # noqa: N802 - BasePen contract
            fn = getattr(self._delegate, "line_to", None)
            if fn is not None:
                fn(pt)

        def curveTo(self, *points: tuple[float, float]) -> None:  # noqa: N802 - BasePen contract
            fn = getattr(self._delegate, "curve_to", None)
            if fn is not None:
                fn(*points)

        def qCurveTo(  # noqa: N802 - BasePen contract
            self, *points: tuple[float, float] | None
        ) -> None:
            fn = getattr(self._delegate, "q_curve_to", None)
            if fn is not None:
                fn(*points)

        def closePath(self) -> None:  # noqa: N802 - BasePen contract
            fn = getattr(self._delegate, "close_path", None)
            if fn is not None:
                fn()

        def endPath(self) -> None:  # noqa: N802 - BasePen contract
            fn = getattr(self._delegate, "end_path", None)
            if fn is not None:
                fn()

        def addComponent(  # noqa: N802 - BasePen contract
            self,
            glyphName: str,  # noqa: N803 - matches BasePen signature
            transformation: tuple[float, float, float, float, float, float],
        ) -> None:
            fn = getattr(self._delegate, "add_component", None)
            if fn is not None:
                fn(glyphName, transformation)

    return _BasePenBridge(delegate, glyph_set)
