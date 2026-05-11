from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSFloat, COSInteger

from .cloudy_border import CloudyBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDPolygonAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a polygon annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDPolygonAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDPolygonAppearanceHandler.java:56)."""
        from ..pd_annotation_polygon import PDAnnotationPolygon
        from ..pd_border_effect_dictionary import PDBorderEffectDictionary

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationPolygon):
            return
        line_width = self.get_line_width()
        rect = annotation.get_rectangle()
        if rect is None:
            return
        path_array = self.get_path_array(annotation)
        if path_array is None:
            return
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for entry in path_array:
            n = len(entry) // 2
            for j in range(n):
                x = entry[j * 2]
                y = entry[j * 2 + 1]
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
        rect.set_lower_left_x(min(min_x - line_width, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - line_width, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + line_width, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + line_width, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        stroke_components = self._color_components_from_annotation(annotation)
        fill_components = self._interior_components(annotation)
        with self.get_normal_appearance_as_content_stream() as cs:
            has_stroke = stroke_components is not None
            if has_stroke:
                cs.set_stroking_color(stroke_components)
            has_background = fill_components is not None
            if has_background:
                cs.set_non_stroking_color(fill_components)
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_border_line(
                line_width, annotation.get_border_style(), annotation.get_border()
            )
            border_effect = annotation.get_border_effect()
            if (
                border_effect is not None
                and border_effect.get_style()
                == PDBorderEffectDictionary.STYLE_CLOUDY
            ):
                cloudy = CloudyBorder(
                    cs,
                    border_effect.get_intensity(),
                    line_width,
                    self.get_rectangle(),
                )
                cloudy.create_cloudy_polygon(path_array)
                annotation.set_rectangle(cloudy.get_rectangle())
                appearance_stream = annotation.get_normal_appearance_stream()
                if appearance_stream is not None:
                    appearance_stream.set_bbox(cloudy.get_bbox())
                    appearance_stream.set_matrix(cloudy.get_matrix())
            else:
                self._emit_polygon(cs, path_array)
            cs.draw_shape(line_width, has_stroke, has_background)

    @staticmethod
    def _emit_polygon(cs, path_array: list[list[float]]) -> None:
        for i, points_array in enumerate(path_array):
            if i == 0 and len(points_array) == 2:
                cs.move_to(points_array[0], points_array[1])
            else:
                if len(points_array) == 2:
                    cs.line_to(points_array[0], points_array[1])
                elif len(points_array) == 6:
                    cs.curve_to(
                        points_array[0], points_array[1],
                        points_array[2], points_array[3],
                        points_array[4], points_array[5],
                    )
        cs.close_path()

    def get_path_array(self, annotation) -> list[list[float]] | None:
        """Mirrors upstream's private ``getPathArray``
        (PDPolygonAppearanceHandler.java:157). PDF 2.0 ``/Path`` takes
        priority over PDF 1.x ``/Vertices``."""
        path = annotation.get_path() if hasattr(annotation, "get_path") else None
        if path is not None:
            return path
        vertices = annotation.get_vertices()
        if vertices is None:
            return None
        points = len(vertices) // 2
        return [[vertices[i * 2], vertices[i * 2 + 1]] for i in range(points)]

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDPolygonAppearanceHandler.java:181)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDPolygonAppearanceHandler.java:187)
        return None

    def get_line_width(self) -> float:
        """Mirrors upstream's package-private ``getLineWidth``
        (PDPolygonAppearanceHandler.java:207)."""
        annotation = self.get_annotation()
        bs = annotation.get_border_style()
        if bs is not None:
            return float(bs.get_width())
        border = annotation.get_border()
        if border is not None and border.size() >= 3:
            base = border.get_object(2)
            if isinstance(base, (COSFloat, COSInteger)):
                return float(base.value)
        return 1.0

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


__all__ = ["PDPolygonAppearanceHandler"]
