"""Abstract base for shading paints.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.ShadingPaint``
(``Paint`` implementations exposed by ``PDShading.to_paint``).

Upstream parameterises this class as ``ShadingPaint<T extends PDShading>``;
we model the same shape with a duck-typed ``shading`` attribute rather than
a Python ``Generic`` because the runtime only needs the public ``shading``
reference, not type-level distinguishing.
"""

from __future__ import annotations

from typing import Any


class ShadingPaint:
    """Abstract paint adapter holding a shading + its concatenated matrix."""

    def __init__(self, shading: Any, matrix: Any) -> None:
        self.shading: Any = shading
        self.matrix: Any = matrix

    def get_shading(self) -> Any:
        return self.shading

    def get_matrix(self) -> Any:
        return self.matrix

    def get_transparency(self) -> int:
        return 0

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any | None = None,
    ) -> Any:
        """Abstract — subclasses (Axial / Radial / Type1 / Type4-7) build
        their type-specific :class:`ShadingContext`. Mirrors upstream
        ``ShadingPaint.createContext`` which is also abstract."""
        _ = (cm, device_bounds, user_bounds, xform, hints)
        raise NotImplementedError(
            "ShadingPaint.create_context is abstract; override in a subclass"
        )
