from __future__ import annotations

from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDHighlightAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a highlight annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDHighlightAppearanceHandler``.

    Partial implementation: upstream uses a two-form-XObject transparency
    group with a Multiply blend mode (``BlendMode.MULTIPLY``) so the
    highlight visually multiplies over the underlying text. The lite
    port emits the filled quad shape directly into the appearance stream
    and applies the constant opacity through an ExtGState — visually
    close, but without the multiply blend. See
    ``TODO: full path generation`` below.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDHighlightAppearanceHandler.java:54)."""
        from ..pd_annotation_highlight import PDAnnotationHighlight

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationHighlight):
            return
        paths_array = annotation.get_quad_points()
        if paths_array is None:
            return
        fill_components = self._color_components_from_annotation(annotation)
        if fill_components is None:
            return
        rect = annotation.get_rectangle()
        if rect is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )

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
        max_delta = 0.0
        for i in range(len(paths_array) // 8):
            delta = max(
                (paths_array[i + 0] - paths_array[i + 4]) / 4,
                (paths_array[i + 1] - paths_array[i + 5]) / 4,
            )
            if delta > max_delta:
                max_delta = delta
        rect.set_lower_left_x(min(min_x - ab.width / 2 - max_delta, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width / 2 - max_delta, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width + max_delta, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width + max_delta, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        # TODO: full path generation — render via a multiply-blend
        # transparency group of two form XObjects (PDFormXObject +
        # PDTransparencyGroupAttributes). The lite port emits the quad
        # fill directly.
        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_non_stroking_color(fill_components)
            offset = 0
            while offset + 7 < len(paths_array):
                # Correct quadpoint ordering: 4,5 0,1 2,3 6,7
                # (PDHighlightAppearanceHandler.java:140).
                cs.move_to(paths_array[offset + 4], paths_array[offset + 5])
                cs.line_to(paths_array[offset + 0], paths_array[offset + 1])
                cs.line_to(paths_array[offset + 2], paths_array[offset + 3])
                cs.line_to(paths_array[offset + 6], paths_array[offset + 7])
                cs.close_path()
                cs.fill()
                offset += 8

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDHighlightAppearanceHandler.java:216)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDHighlightAppearanceHandler.java:222)
        return None


__all__ = ["PDHighlightAppearanceHandler"]
