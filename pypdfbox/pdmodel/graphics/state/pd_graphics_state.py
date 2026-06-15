"""Current graphics state during content-stream execution.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState``.

The PDF graphics state holds the CTM, stroking/non-stroking colour and
colour space, soft mask, blend mode, alpha constants, clipping path,
text state, line dash, and a handful of device-dependent parameters.
The full upstream class is a procedural workhorse for the renderer; we
mirror the storage + accessor API but lean on the existing
``pypdfbox.util.matrix.Matrix`` and PD colour types.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

from .pd_text_state import PDTextState
from .rendering_intent import RenderingIntent

if TYPE_CHECKING:
    from pypdfbox.cos import COSBase
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    from .pd_soft_mask import PDSoftMask

# Java's BasicStroke constants — mirrored as plain ints so callers don't
# need an AWT shim.
CAP_BUTT = 0
JOIN_MITER = 0


class PDGraphicsState:
    """Current state of the graphics parameters when executing a content stream."""

    def __init__(self, page: PDRectangle | None = None) -> None:
        from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
        from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
        from pypdfbox.util.matrix import Matrix

        self._is_clipping_path_dirty = False
        # Mirror upstream: list seeded from the page rect path.
        self._clipping_paths: list[Any] = []
        if page is not None and hasattr(page, "to_general_path"):
            self._clipping_paths.append(page.to_general_path())
        self._clipping_path_cache: Any = None

        self._current_transformation_matrix = Matrix()
        device_gray = getattr(PDDeviceGray, "INSTANCE", None) or PDDeviceGray()
        initial = (
            device_gray.get_initial_color()
            if hasattr(device_gray, "get_initial_color")
            else None
        )
        self._stroking_color = initial
        self._non_stroking_color = initial
        self._stroking_color_space: PDColorSpace = device_gray
        self._non_stroking_color_space: PDColorSpace = device_gray
        self._text_state = PDTextState()
        self._line_width: float = 1.0
        self._line_cap: int = CAP_BUTT
        self._line_join: int = JOIN_MITER
        self._miter_limit: float = 10.0
        self._line_dash_pattern = PDLineDashPattern()
        self._rendering_intent: RenderingIntent | None = None
        self._stroke_adjustment: bool = False
        self._blend_mode: BlendMode = BlendMode.NORMAL
        self._soft_mask: PDSoftMask | None = None
        self._alpha_constant: float = 1.0
        self._non_stroking_alpha_constant: float = 1.0
        self._alpha_source: bool = False
        self._text_matrix: Any = None
        self._text_line_matrix: Any = None
        self._overprint: bool = False
        self._non_stroking_overprint: bool = False
        self._overprint_mode: int = 0
        self._transfer: COSBase | None = None
        self._flatness: float = 1.0
        self._smoothness: float = 0.0

    # CTM
    def get_current_transformation_matrix(self) -> Any:
        """Return the current transformation matrix."""
        return self._current_transformation_matrix

    def set_current_transformation_matrix(self, value: Any) -> None:
        """Set the current transformation matrix."""
        self._current_transformation_matrix = value

    # Line state
    def get_line_width(self) -> float:
        return self._line_width

    def set_line_width(self, value: float) -> None:
        self._line_width = float(value)

    def get_line_cap(self) -> int:
        return self._line_cap

    def set_line_cap(self, value: int) -> None:
        self._line_cap = int(value)

    def get_line_join(self) -> int:
        return self._line_join

    def set_line_join(self, value: int) -> None:
        self._line_join = int(value)

    def get_miter_limit(self) -> float:
        return self._miter_limit

    def set_miter_limit(self, value: float) -> None:
        self._miter_limit = float(value)

    def is_stroke_adjustment(self) -> bool:
        return self._stroke_adjustment

    def set_stroke_adjustment(self, value: bool) -> None:
        self._stroke_adjustment = bool(value)

    # Alpha + transparency
    def get_alpha_constant(self) -> float:
        return self._alpha_constant

    def set_alpha_constant(self, value: float) -> None:
        self._alpha_constant = float(value)

    def get_non_stroke_alpha_constant(self) -> float:
        return self._non_stroking_alpha_constant

    def set_non_stroke_alpha_constant(self, value: float) -> None:
        self._non_stroking_alpha_constant = float(value)

    def is_alpha_source(self) -> bool:
        return self._alpha_source

    def set_alpha_source(self, value: bool) -> None:
        self._alpha_source = bool(value)

    def get_soft_mask(self) -> PDSoftMask | None:
        return self._soft_mask

    def set_soft_mask(self, soft_mask: PDSoftMask | None) -> None:
        self._soft_mask = soft_mask

    def get_blend_mode(self) -> BlendMode:
        return self._blend_mode

    def set_blend_mode(self, blend_mode: BlendMode) -> None:
        if blend_mode is None:
            raise ValueError("blendMode parameter cannot be null")
        self._blend_mode = blend_mode

    # Overprint / device parameters
    def is_overprint(self) -> bool:
        return self._overprint

    def set_overprint(self, value: bool) -> None:
        self._overprint = bool(value)

    def is_non_stroking_overprint(self) -> bool:
        return self._non_stroking_overprint

    def set_non_stroking_overprint(self, value: bool) -> None:
        self._non_stroking_overprint = bool(value)

    def get_overprint_mode(self) -> int:
        return self._overprint_mode

    def set_overprint_mode(self, value: int) -> None:
        self._overprint_mode = int(value)

    def get_flatness(self) -> float:
        return self._flatness

    def set_flatness(self, value: float) -> None:
        self._flatness = float(value)

    def get_smoothness(self) -> float:
        return self._smoothness

    def set_smoothness(self, value: float) -> None:
        self._smoothness = float(value)

    # Text & line dash
    def get_text_state(self) -> PDTextState:
        return self._text_state

    def set_text_state(self, value: PDTextState) -> None:
        self._text_state = value

    def get_line_dash_pattern(self) -> Any:
        return self._line_dash_pattern

    def set_line_dash_pattern(self, value: Any) -> None:
        self._line_dash_pattern = value

    def get_rendering_intent(self) -> RenderingIntent | None:
        return self._rendering_intent

    def set_rendering_intent(self, value: RenderingIntent | None) -> None:
        self._rendering_intent = value

    # Colour
    def get_stroking_color(self) -> Any:
        return self._stroking_color

    def set_stroking_color(self, color: Any) -> None:
        self._stroking_color = color

    def get_non_stroking_color(self) -> Any:
        return self._non_stroking_color

    def set_non_stroking_color(self, color: Any) -> None:
        self._non_stroking_color = color

    def get_stroking_color_space(self) -> Any:
        return self._stroking_color_space

    def set_stroking_color_space(self, cs: Any) -> None:
        self._stroking_color_space = cs

    def get_non_stroking_color_space(self) -> Any:
        return self._non_stroking_color_space

    def set_non_stroking_color_space(self, cs: Any) -> None:
        self._non_stroking_color_space = cs

    # Clipping
    def intersect_clipping_path(self, path: Any, clone_path: bool = True) -> None:
        """Intersect the current clipping path with ``path``.

        Accepts a GeneralPath / Path2D / Area-equivalent. We perform lazy
        cloning of the path list for performance, matching upstream.
        """
        if not self._is_clipping_path_dirty:
            self._clipping_paths = list(self._clipping_paths)
            self._is_clipping_path_dirty = True
        self._clipping_paths.append(path)
        self._clipping_path_cache = None

    def get_current_clipping_path(self) -> Any:
        """Return the intersection of all clipping paths.

        Mirrors upstream ``getCurrentClippingPath`` (PDGraphicsState.java:620).
        Upstream builds a ``java.awt.geom.Area`` and intersects it with every
        sub-path's bounding box, then intersects each sub-path Area on top.

        We don't depend on AWT, so paths are represented as lists of
        ``(x, y)`` points (see :meth:`PDRectangle.to_general_path`). For
        anything beyond axis-aligned rectangles a true polygon intersection
        would need a 2-D geometry library we cannot pull in (see project
        dependency policy). The conservative approximation upstream itself
        starts from — the intersection of all sub-path bounding boxes — is
        what we materialise here: a 4-corner rectangle. This is pessimistic
        in the same direction as upstream's seed area and is safe for the
        clip-path consumers (renderer / overlay / signature region).
        """
        if not self._clipping_paths:
            return None
        if len(self._clipping_paths) == 1:
            if self._clipping_path_cache is None:
                self._clipping_path_cache = self._clipping_paths[0]
            return self._clipping_path_cache
        bbox = self._path_bounds(self._clipping_paths[0])
        if bbox is None:
            return self._clipping_paths[-1]
        min_x, min_y, max_x, max_y = bbox
        for path in self._clipping_paths[1:]:
            other = self._path_bounds(path)
            if other is None:
                continue
            min_x = max(min_x, other[0])
            min_y = max(min_y, other[1])
            max_x = min(max_x, other[2])
            max_y = min(max_y, other[3])
            if min_x >= max_x or min_y >= max_y:
                # Empty intersection — return a zero-area rectangle anchored
                # at the upper-left of the empty region.
                empty = [(min_x, min_y), (min_x, min_y), (min_x, min_y), (min_x, min_y)]
                self._clipping_path_cache = empty
                self._clipping_paths = [empty]
                return empty
        intersected = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
        ]
        self._clipping_path_cache = intersected
        # Replace the list so subsequent calls short-circuit on the cache.
        self._clipping_paths = [intersected]
        return intersected

    @staticmethod
    def _path_bounds(path: Any) -> tuple[float, float, float, float] | None:
        """Return ``(min_x, min_y, max_x, max_y)`` for a path, or ``None``."""
        if path is None:
            return None
        # PDRectangle-like objects expose explicit accessors.
        if hasattr(path, "get_lower_left_x") and hasattr(path, "get_upper_right_y"):
            return (
                float(path.get_lower_left_x()),
                float(path.get_lower_left_y()),
                float(path.get_upper_right_x()),
                float(path.get_upper_right_y()),
            )
        try:
            points = list(path)
        except TypeError:
            return None
        if not points:
            return None
        xs: list[float] = []
        ys: list[float] = []
        for point in points:
            if hasattr(point, "__len__") and len(point) >= 2:
                xs.append(float(point[0]))
                ys.append(float(point[1]))
        if not xs or not ys:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def get_current_clipping_paths(self) -> list[Any]:
        """Return the underlying list of clipping paths."""
        return self._clipping_paths

    # Composites (return BlendComposite instances)
    def get_stroking_java_composite(self) -> Any:
        from pypdfbox.pdmodel.graphics.blend.blend_composite import BlendComposite

        return BlendComposite.get_instance(self._blend_mode, float(self._alpha_constant))

    def get_non_stroking_java_composite(self) -> Any:
        from pypdfbox.pdmodel.graphics.blend.blend_composite import BlendComposite

        return BlendComposite.get_instance(
            self._blend_mode, float(self._non_stroking_alpha_constant)
        )

    # Transfer / halftone helpers
    def get_transfer(self) -> Any:
        return self._transfer

    def set_transfer(self, transfer: Any) -> None:
        self._transfer = transfer

    # Text matrices
    def get_text_line_matrix(self) -> Any:
        return self._text_line_matrix

    def set_text_line_matrix(self, value: Any) -> None:
        self._text_line_matrix = value

    def get_text_matrix(self) -> Any:
        return self._text_matrix

    def set_text_matrix(self, value: Any) -> None:
        self._text_matrix = value

    # Clone
    def clone(self) -> PDGraphicsState:
        """Deep-ish clone matching upstream's clone semantics."""
        new = copy.copy(self)
        new._text_state = self._text_state.clone()
        if hasattr(self._current_transformation_matrix, "clone"):
            new._current_transformation_matrix = self._current_transformation_matrix.clone()
        else:
            new._current_transformation_matrix = copy.copy(self._current_transformation_matrix)
        new._is_clipping_path_dirty = False
        if self._text_line_matrix is not None and hasattr(self._text_line_matrix, "clone"):
            new._text_line_matrix = self._text_line_matrix.clone()
        if self._text_matrix is not None and hasattr(self._text_matrix, "clone"):
            new._text_matrix = self._text_matrix.clone()
        return new


__all__ = ["PDGraphicsState"]
