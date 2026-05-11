from __future__ import annotations

from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDInkAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for an ink annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDInkAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDInkAppearanceHandler.java:48)."""
        from ..pd_annotation_ink import PDAnnotationInk

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationInk):
            return
        stroke_components = self._color_components_from_annotation(annotation)
        if stroke_components is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        if ab.width == 0:
            return
        ink_list_wrapper = annotation.get_ink_list()
        if ink_list_wrapper is None:
            return
        path_infos = ink_list_wrapper.get_paths()
        if not path_infos:
            return
        paths: list[list[tuple[float, float]]] = [
            info.get_points() for info in path_infos
        ]
        # Compute bounding extents over every ink path.
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for path_points in paths:
            for x, y in path_points:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
        rect = annotation.get_rectangle()
        if rect is None:
            return
        rect.set_lower_left_x(min(min_x - ab.width * 2, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width * 2, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width * 2, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width * 2, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)
        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_stroking_color(stroke_components)
            if ab.dash_array is not None:
                cs.set_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)
            for path_points in paths:
                for i, (x, y) in enumerate(path_points):
                    if i == 0:
                        cs.move_to(x, y)
                    else:
                        cs.line_to(x, y)
                cs.stroke()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDInkAppearanceHandler.java:135)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDInkAppearanceHandler.java:141)
        return None


__all__ = ["PDInkAppearanceHandler"]
