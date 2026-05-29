from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSName

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDCaretAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a caret annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDCaretAppearanceHandler``.

    The caret glyph is drawn as a single filled Bezier "tooth" — two
    symmetric curves meeting at the top of the rectangle. When no
    ``/RD`` is set on the annotation, Adobe expands the BBox + rectangle
    by ``min(height/10, 5)`` so the curves don't bump the edge.
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
        from ....pd_rectangle import PDRectangle
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
                # Upstream passes the full PDColor (annotation.getColor()) so
                # the stream emits /DeviceRGB CS <r> <g> <b> SC, never the
                # device shorthand RG/G/K — see PDCaretAppearanceHandler.java.
                color = self._pd_color_from_components(components)
                cs.set_stroking_color(color)
                cs.set_non_stroking_color(color)
            self.set_opacity(cs, annotation.get_constant_opacity())

            rect_width = rect.get_width()
            rect_height = rect.get_height()
            bbox = PDRectangle.from_width_height(rect_width, rect_height)
            normal_stream = annotation.get_normal_appearance_stream()
            if not annotation.get_cos_object().contains_key(COSName.get_pdf_name("RD")):
                # Adobe expands the BBox + rectangle by min(height/10, 5)
                # when no /RD is set. The curves are still drawn relative
                # to the original rectangle dimensions.
                rd = min(rect_height / 10, 5.0)
                annotation.set_rect_differences([rd, rd, rd, rd])
                bbox = PDRectangle.from_xywh(
                    -rd, -rd, rect_width + 2 * rd, rect_height + 2 * rd
                )
                rect2 = PDRectangle.from_xywh(
                    rect.get_lower_left_x() - rd,
                    rect.get_lower_left_y() - rd,
                    rect_width + 2 * rd,
                    rect_height + 2 * rd,
                )
                annotation.set_rectangle(rect2)
            if normal_stream is not None:
                normal_stream.set_bbox(bbox)

            half_x = rect_width / 2
            half_y = rect_height / 2
            cs.move_to(0.0, 0.0)
            cs.curve_to(half_x, 0.0, half_x, half_y, half_x, rect_height)
            cs.curve_to(half_x, half_y, half_x, 0.0, rect_width, 0.0)
            cs.close_path()
            cs.fill()
            # Adobe has an additional stroke, but it has no effect because
            # fill "consumes" the path.

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDCaretAppearanceHandler.java:107).
        # Upstream's method body is empty (carries a deferred-impl note).
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDCaretAppearanceHandler.java:113).
        # Upstream's method body is empty (carries a deferred-impl note).
        return None


__all__ = ["PDCaretAppearanceHandler"]
