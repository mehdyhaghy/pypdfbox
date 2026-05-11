from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


_ADOBE_DEFAULT_WIDTH: float = 1.5


class PDStrikeoutAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a strikeout annotation.

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers``
    ``.PDStrikeoutAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDStrikeoutAppearanceHandler.java:47)."""
        from ..pd_annotation_strikeout import PDAnnotationStrikeout

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationStrikeout):
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

        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_stroking_color(stroke_components)
            if ab.dash_array is not None:
                cs.set_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)
            for i in range(len(paths_array) // 8):
                base = i * 8
                len0 = math.hypot(
                    paths_array[base] - paths_array[base + 4],
                    paths_array[base + 1] - paths_array[base + 5],
                )
                x0 = paths_array[base + 4]
                y0 = paths_array[base + 5]
                if len0 != 0:
                    x0 += (
                        (paths_array[base] - paths_array[base + 4])
                        / len0
                        * (len0 / 2 - ab.width)
                    )
                    y0 += (
                        (paths_array[base + 1] - paths_array[base + 5])
                        / len0
                        * (len0 / 2 - ab.width)
                    )
                len1 = math.hypot(
                    paths_array[base + 2] - paths_array[base + 6],
                    paths_array[base + 3] - paths_array[base + 7],
                )
                x1 = paths_array[base + 6]
                y1 = paths_array[base + 7]
                if len1 != 0:
                    x1 += (
                        (paths_array[base + 2] - paths_array[base + 6])
                        / len1
                        * (len1 / 2 - ab.width)
                    )
                    y1 += (
                        (paths_array[base + 3] - paths_array[base + 7])
                        / len1
                        * (len1 / 2 - ab.width)
                    )
                cs.move_to(x0, y0)
                cs.line_to(x1, y1)
            cs.stroke()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDStrikeoutAppearanceHandler.java:146)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDStrikeoutAppearanceHandler.java:152)
        return None


__all__ = ["PDStrikeoutAppearanceHandler"]
