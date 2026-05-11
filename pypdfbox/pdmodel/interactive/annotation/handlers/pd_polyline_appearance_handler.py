from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDPolylineAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a polyline annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDPolylineAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDPolylineAppearanceHandler.java:51)."""
        from ..pd_annotation_line import PDAnnotationLine
        from ..pd_annotation_polyline import PDAnnotationPolyline

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationPolyline):
            return
        rect = annotation.get_rectangle()
        if rect is None:
            return
        paths_array = annotation.get_vertices()
        if paths_array is None or len(paths_array) < 4:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        stroke_components = self._color_components_from_annotation(annotation)
        if stroke_components is None or ab.width == 0:
            return

        # Adjust rectangle even if not empty. Arrow length is 9 * width
        # at ~30°, so 10 * width is a safe padding (java line 87).
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
        rect.set_lower_left_x(min(min_x - ab.width * 10, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width * 10, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width * 10, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width * 10, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        with self.get_normal_appearance_as_content_stream() as cs:
            interior_components = self._interior_components(annotation)
            has_background = interior_components is not None
            if has_background:
                cs.set_non_stroking_color(interior_components)
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_stroking_color(stroke_components)
            has_stroke = True
            if ab.dash_array is not None:
                cs.set_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)
            start_style = annotation.get_start_point_ending_style()
            end_style = annotation.get_end_point_ending_style()
            n_points = len(paths_array) // 2
            for i in range(n_points):
                x = paths_array[i * 2]
                y = paths_array[i * 2 + 1]
                if i == 0:
                    if start_style in self.SHORT_STYLES:
                        x1 = paths_array[2]
                        y1 = paths_array[3]
                        length = math.hypot(x - x1, y - y1)
                        if length != 0:
                            x += (x1 - x) / length * ab.width
                            y += (y1 - y) / length * ab.width
                    cs.move_to(x, y)
                else:
                    if (
                        i == n_points - 1
                        and end_style in self.SHORT_STYLES
                    ):
                        x0 = paths_array[len(paths_array) - 4]
                        y0 = paths_array[len(paths_array) - 3]
                        length = math.hypot(x0 - x, y0 - y)
                        if length != 0:
                            x -= (x - x0) / length * ab.width
                            y -= (y - y0) / length * ab.width
                    cs.line_to(x, y)
            cs.stroke()

            # Paint line-ending styles after the polyline so a filled
            # shape isn't crossed by the polyline (java line 154).
            if start_style != PDAnnotationLine.LE_NONE:
                x2 = paths_array[2]
                y2 = paths_array[3]
                x1 = paths_array[0]
                y1 = paths_array[1]
                cs.save_graphics_state()
                if start_style in self.ANGLED_STYLES:
                    angle = math.atan2(y2 - y1, x2 - x1)
                    cs.transform(
                        math.cos(angle), math.sin(angle),
                        -math.sin(angle), math.cos(angle),
                        x1, y1,
                    )
                else:
                    cs.transform(1.0, 0.0, 0.0, 1.0, x1, y1)
                self.draw_style(
                    start_style, cs, 0.0, 0.0, ab.width,
                    has_stroke, has_background, False,
                )
                cs.restore_graphics_state()

            if end_style != PDAnnotationLine.LE_NONE:
                x1 = paths_array[len(paths_array) - 4]
                y1 = paths_array[len(paths_array) - 3]
                x2 = paths_array[len(paths_array) - 2]
                y2 = paths_array[len(paths_array) - 1]
                if end_style in self.ANGLED_STYLES:
                    angle = math.atan2(y2 - y1, x2 - x1)
                    cs.transform(
                        math.cos(angle), math.sin(angle),
                        -math.sin(angle), math.cos(angle),
                        x2, y2,
                    )
                else:
                    cs.transform(1.0, 0.0, 0.0, 1.0, x2, y2)
                self.draw_style(
                    end_style, cs, 0.0, 0.0, ab.width,
                    has_stroke, has_background, True,
                )

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDPolylineAppearanceHandler.java:202)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDPolylineAppearanceHandler.java:208)
        return None

    @staticmethod
    def _interior_components(annotation) -> list[float] | None:
        interior = getattr(annotation, "get_interior_color", lambda: None)()
        if interior is None:
            return None
        if hasattr(interior, "to_float_array"):
            arr = interior.to_float_array()
            return arr if arr else None
        if hasattr(interior, "size"):
            if interior.size() == 0:
                return None
            return interior.to_float_array()
        seq = list(interior)
        return seq if seq else None


__all__ = ["PDPolylineAppearanceHandler"]
