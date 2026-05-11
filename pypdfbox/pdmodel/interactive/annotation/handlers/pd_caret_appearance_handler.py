from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDCaretAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a caret annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDCaretAppearanceHandler``.

    The caret glyph is drawn as a single filled Bezier "tooth" — two
    symmetric curves meeting at the top of the rectangle.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDCaretAppearanceHandler.java:51)."""
        from ..pd_annotation_caret import PDAnnotationCaret

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationCaret):
            return
        rect = self.get_rectangle()
        if rect is None:
            return
        components = self._color_components_from_annotation(annotation)
        with self.get_normal_appearance_as_content_stream() as cs:
            if components is not None:
                cs.set_stroking_color(components)
                cs.set_non_stroking_color(components)
            self.set_opacity(cs, annotation.get_constant_opacity())
            rect_width = rect.get_width()
            rect_height = rect.get_height()
            half_x = rect_width / 2
            cs.move_to(0.0, 0.0)
            cs.curve_to(half_x, 0.0, half_x, rect_height / 2, half_x, rect_height)
            cs.curve_to(half_x, rect_height / 2, half_x, 0.0, rect_width, 0.0)
            cs.close_path()
            cs.fill()

    def generate_rollover_appearance(self) -> None:
        # TODO to be implemented (PDCaretAppearanceHandler.java:107)
        return None

    def generate_down_appearance(self) -> None:
        # TODO to be implemented (PDCaretAppearanceHandler.java:113)
        return None


__all__ = ["PDCaretAppearanceHandler"]
