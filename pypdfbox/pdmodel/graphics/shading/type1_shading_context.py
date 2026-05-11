"""Paint context for Type 1 (function-based) shading.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Type1ShadingContext``.
"""

from __future__ import annotations

import contextlib
from typing import Any

from .shading_context import ShadingContext


class Type1ShadingContext(ShadingContext):
    """Function-based shading paint context."""

    def __init__(
        self,
        shading: Any,
        color_model: Any,
        xform: Any,
        matrix: Any,
    ) -> None:
        super().__init__(shading, color_model, xform, matrix)
        self._type1_shading_type = shading
        domain = shading.get_domain()
        if domain is not None:
            self._domain: list[float] = list(domain.to_float_array())
        else:
            self._domain = [0.0, 1.0, 0.0, 1.0]

    def dispose(self) -> None:
        super().dispose()
        self._type1_shading_type = None

    def get_domain(self) -> list[float]:
        return list(self._domain)

    def get_raster(self, x: int, y: int, w: int, h: int) -> Any:
        """Generate a ``PIL.Image`` raster covering ``(x, y, w, h)`` in
        device space. Mirrors upstream
        ``Type1ShadingContext.getRaster`` (Type1ShadingContext.java
        line 91) — evaluates the 2-parameter function ``f(x, y)`` at each
        pixel against the shading's ``/Domain`` rectangle and converts
        to RGB via the shading colour space."""
        from PIL import Image  # noqa: PLC0415

        bg = self.get_background()
        domain = self._domain
        shading = self._type1_shading_type
        cs = self.get_shading_color_space()

        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pixels = out.load()
        for j in range(h):
            for i in range(w):
                px = float(x + i)
                py = float(y + j)
                use_background = False
                if (
                    px < domain[0]
                    or px > domain[1]
                    or py < domain[2]
                    or py > domain[3]
                ):
                    if bg is None:
                        continue
                    use_background = True
                if use_background:
                    tmp = list(bg) if bg is not None else [0.0, 0.0, 0.0]
                else:
                    try:
                        tmp = list(shading.eval_function([px, py]))
                    except (OSError, ValueError, ZeroDivisionError):
                        continue
                if cs is not None and hasattr(cs, "to_rgb"):
                    with contextlib.suppress(TypeError, NotImplementedError, OSError):
                        tmp = list(cs.to_rgb(tmp))
                if len(tmp) < 3:
                    tmp = tmp + [0.0] * (3 - len(tmp))
                r = int(max(0.0, min(1.0, tmp[0])) * 255)
                g = int(max(0.0, min(1.0, tmp[1])) * 255)
                b = int(max(0.0, min(1.0, tmp[2])) * 255)
                pixels[i, j] = (r, g, b, 255)
        return out
