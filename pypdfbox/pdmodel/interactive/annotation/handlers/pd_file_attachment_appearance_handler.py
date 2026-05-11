from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation
    from ..pd_appearance_content_stream import PDAppearanceContentStream


_GLYPH_SIZE: int = 18


class PDFileAttachmentAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a file-attachment annotation.

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers``
    ``.PDFileAttachmentAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDFileAttachmentAppearanceHandler.java:49)."""
        from ..pd_annotation_file_attachment import PDAnnotationFileAttachment

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationFileAttachment):
            return
        rect = self.get_rectangle()
        if rect is None:
            return
        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            # Mimic upstream's adjustRectAndBBox minimum-code:
            #   rect.setUpperRightX(rect.getLowerLeftX() + size);
            #   rect.setLowerLeftY(rect.getUpperRightY() - size);
            rect.set_upper_right_x(rect.get_lower_left_x() + _GLYPH_SIZE)
            rect.set_lower_left_y(rect.get_upper_right_y() - _GLYPH_SIZE)
            annotation.set_rectangle(rect)
            normal_stream = annotation.get_normal_appearance_stream()
            if normal_stream is not None:
                from ....pd_rectangle import PDRectangle

                normal_stream.set_bbox(
                    PDRectangle.from_width_height(_GLYPH_SIZE, _GLYPH_SIZE)
                )
            name = annotation.get_attachment_name()
            if name == "Paperclip":
                self._draw_paperclip(cs)
            elif name == "Graph":
                self._draw_graph(cs)
            elif name == "Tag":
                self._draw_tag(cs)
            else:
                self._draw_push_pin(cs)

    def draw_paperclip(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawPaperclip``
        (PDFileAttachmentAppearanceHandler.java:100).

        Stylized paperclip drawn from two stacked rounded rectangles
        approximating the bent metal loops. The result is a recognizable
        paperclip icon visible in viewers and is functionally compatible
        with upstream's filled-glyph approach.
        """
        # Outer loop (filled outline) — strokes a tall pill shape.
        cs.set_line_width(1.5)
        # Outer loop body
        cs.move_to(6.0, 3.0)
        cs.curve_to(6.0, 1.5, 9.0, 1.5, 9.0, 3.0)
        cs.line_to(9.0, 13.0)
        cs.curve_to(9.0, 15.0, 6.0, 15.0, 6.0, 13.0)
        cs.line_to(6.0, 3.0)
        cs.close_path()
        cs.stroke()
        # Inner loop — shorter pill nested inside.
        cs.move_to(7.5, 5.0)
        cs.line_to(7.5, 11.0)
        cs.stroke()

    # Backwards-compatible private-name alias.
    _draw_paperclip = draw_paperclip

    def draw_push_pin(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawPushPin``
        (PDFileAttachmentAppearanceHandler.java:132).

        Stylized push-pin: a head triangle with a needle line. Drawn
        with stroke + fill to remain recognizable at the 18 pt glyph
        size used by upstream.
        """
        # Pin head (triangle/diamond at top)
        cs.move_to(9.0, 16.0)
        cs.line_to(5.0, 10.0)
        cs.line_to(13.0, 10.0)
        cs.close_path()
        cs.fill()
        # Pin needle
        cs.set_line_width(1.0)
        cs.move_to(9.0, 10.0)
        cs.line_to(9.0, 3.0)
        cs.stroke()
        # Pin shaft cap
        cs.add_rect(7.0, 9.0, 4.0, 1.0)
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_push_pin = draw_push_pin

    def draw_graph(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawGraph``
        (PDFileAttachmentAppearanceHandler.java:185).

        Bar-chart histogram: axes plus four ascending bars matching the
        Carbon Design source semantically.
        """
        # Axes
        cs.set_line_width(0.5)
        cs.move_to(2.0, 2.0)
        cs.line_to(2.0, 16.0)
        cs.stroke()
        cs.move_to(2.0, 2.0)
        cs.line_to(16.0, 2.0)
        cs.stroke()
        # Four ascending bars
        cs.add_rect(4.0, 2.0, 2.0, 4.0)
        cs.fill()
        cs.add_rect(7.0, 2.0, 2.0, 7.0)
        cs.fill()
        cs.add_rect(10.0, 2.0, 2.0, 10.0)
        cs.fill()
        cs.add_rect(13.0, 2.0, 2.0, 13.0)
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_graph = draw_graph

    def draw_tag(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawTag``
        (PDFileAttachmentAppearanceHandler.java:273).

        Price-tag silhouette: a five-sided polygon with the punched
        eyelet at the corner.
        """
        # Tag body
        cs.move_to(2.0, 9.0)
        cs.line_to(9.0, 2.0)
        cs.line_to(16.0, 2.0)
        cs.line_to(16.0, 9.0)
        cs.line_to(9.0, 16.0)
        cs.close_path()
        cs.set_line_width(1.0)
        cs.stroke()
        # Eyelet hole — small filled circle near the wide corner.
        cx, cy, r = 13.0, 6.0, 1.2
        magic = r * 0.5523
        cs.move_to(cx + r, cy)
        cs.curve_to(cx + r, cy + magic, cx + magic, cy + r, cx, cy + r)
        cs.curve_to(cx - magic, cy + r, cx - r, cy + magic, cx - r, cy)
        cs.curve_to(cx - r, cy - magic, cx - magic, cy - r, cx, cy - r)
        cs.curve_to(cx + magic, cy - r, cx + r, cy - magic, cx + r, cy)
        cs.close_path()
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_tag = draw_tag

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDFileAttachmentAppearanceHandler.java:326)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDFileAttachmentAppearanceHandler.java:332)
        return None


__all__ = ["PDFileAttachmentAppearanceHandler"]
