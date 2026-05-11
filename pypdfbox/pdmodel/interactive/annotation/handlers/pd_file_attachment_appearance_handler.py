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

    The full upstream port carries large hard-coded SVG-derived paths
    (paperclip / push-pin / graph / tag). The lite port lays down the
    rectangle / bbox plumbing and dispatches to the four ``_draw_*``
    methods — each of which currently stubs the icon with a simple
    rectangle marker plus a ``TODO: full path generation`` note. The
    method signatures match upstream so the icon paths can be filled in
    incrementally without further API changes.
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
        (PDFileAttachmentAppearanceHandler.java:100). TODO: full path
        generation — port the Iconscout paperclip path."""
        cs.add_rect(2.0, 2.0, _GLYPH_SIZE - 4, _GLYPH_SIZE - 4)
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_paperclip = draw_paperclip

    def draw_push_pin(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawPushPin``
        (PDFileAttachmentAppearanceHandler.java:132). TODO: full path
        generation — port the svgrepo push-pin path."""
        cs.add_rect(2.0, 2.0, _GLYPH_SIZE - 4, _GLYPH_SIZE - 4)
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_push_pin = draw_push_pin

    def draw_graph(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawGraph``
        (PDFileAttachmentAppearanceHandler.java:185). TODO: full path
        generation."""
        cs.add_rect(2.0, 2.0, _GLYPH_SIZE - 4, _GLYPH_SIZE - 4)
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_graph = draw_graph

    def draw_tag(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawTag``
        (PDFileAttachmentAppearanceHandler.java:273). TODO: full path
        generation."""
        cs.add_rect(2.0, 2.0, _GLYPH_SIZE - 4, _GLYPH_SIZE - 4)
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
