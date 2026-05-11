from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


_ADOBE_DEFAULT_WIDTH: float = 1.5


class PDSquigglyAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a squiggly annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDSquigglyAppearanceHandler``.

    Partial implementation: upstream paints the squiggly via a tiling
    pattern (zig-zag) wrapped in a form XObject — that path depends on
    :class:`PDTilingPattern` + :class:`PDPatternContentStream`, which
    don't yet exist in the lite port. We draw a simpler approximation:
    one zig-zag polyline per quad, stroked in the annotation color. The
    ``TODO: full path generation`` note marks this for a follow-up wave.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDSquigglyAppearanceHandler.java:58)."""
        from ..pd_annotation_squiggly import PDAnnotationSquiggly

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationSquiggly):
            return
        rect = annotation.get_rectangle()
        if rect is None:
            return
        paths_array = annotation.get_quad_points()
        if paths_array is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        stroke_components = self._color_components_from_annotation(annotation)
        if stroke_components is None:
            return
        if ab.width == 0:
            ab.width = _ADOBE_DEFAULT_WIDTH

        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for i in range(len(paths_array) // 2):
            x = paths_array[i * 2]
            y = paths_array[i * 2 + 1]
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
        rect.set_lower_left_x(min(min_x - ab.width / 2, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width / 2, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width / 2, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width / 2, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        # TODO: full path generation — port the tiling-pattern fill.
        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_stroking_color(stroke_components)
            cs.set_line_width(ab.width)
            # Lite approximation: draw a simple zig-zag along the baseline
            # of each quad. The tiling-pattern version preserves better
            # spacing at sub-pixel resolutions but the basic shape is
            # adequate for parity tests.
            for i in range(len(paths_array) // 8):
                base = i * 8
                x_left = paths_array[base + 4]
                y_left = paths_array[base + 5]
                x_right = paths_array[base + 6]
                y_right = paths_array[base + 7]
                length = math.hypot(x_right - x_left, y_right - y_left)
                if length == 0:
                    continue
                # 10-pt zig-zag step (matches the upstream pattern XStep).
                step = 10.0
                amplitude = 2.0
                segments = max(1, int(length / step))
                dx = (x_right - x_left) / segments
                dy = (y_right - y_left) / segments
                # Unit perpendicular for the zig-zag amplitude.
                nx = -dy / (length / segments) if length else 0
                ny = dx / (length / segments) if length else 0
                cs.move_to(x_left, y_left)
                for s in range(1, segments + 1):
                    px = x_left + dx * s
                    py = y_left + dy * s
                    sign = 1 if s % 2 == 1 else -1
                    cs.line_to(px + nx * amplitude * sign, py + ny * amplitude * sign)
                cs.stroke()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDSquigglyAppearanceHandler.java:172)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDSquigglyAppearanceHandler.java:178)
        return None


__all__ = ["PDSquigglyAppearanceHandler"]
