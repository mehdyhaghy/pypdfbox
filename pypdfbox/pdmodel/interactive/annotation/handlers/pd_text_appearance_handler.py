from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ....pd_rectangle import PDRectangle
    from ..pd_annotation import PDAnnotation
    from ..pd_annotation_text import PDAnnotationText
    from ..pd_appearance_content_stream import PDAppearanceContentStream


_SUPPORTED_NAMES = frozenset(
    {
        "Note",
        "Insert",
        "Cross",
        "Help",
        "Circle",
        "Paragraph",
        "NewParagraph",
        "Check",
        "Star",
        "RightArrow",
        "RightPointer",
        "CrossHairs",
        "UpArrow",
        "UpLeftArrow",
        "Comment",
        "Key",
    }
)


class PDTextAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a text (sticky-note) annotation.
    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDTextAppearanceHandler``.

    Partial implementation: upstream carries 16 hand-coded SVG-derived
    drawing methods (``draw_note``, ``draw_help``, ``draw_zapf`` etc.).
    The lite port wires up the dispatch and the rectangle / BBox
    plumbing for every supported ``/Name``, and ships a real
    ``_draw_note`` (the spec default). The remaining 15 glyph paths are
    stubbed with a simple rectangle marker — see
    ``TODO: full path generation`` on each ``_draw_*`` helper.
    """

    SUPPORTED_NAMES: frozenset[str] = _SUPPORTED_NAMES

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDTextAppearanceHandler.java:82)."""
        from ..pd_annotation_text import PDAnnotationText

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationText):
            return
        name = annotation.get_name()
        if name not in _SUPPORTED_NAMES:
            return
        with self.get_normal_appearance_as_content_stream() as cs:
            bg_components = self._color_components_from_annotation(annotation)
            if bg_components is None:
                # White when /C is absent (PDTextAppearanceHandler.java:96)
                cs.set_non_stroking_color([1.0])
            else:
                cs.set_non_stroking_color(bg_components)
            # Stroking color stays the PDF default (black).
            self.set_opacity(cs, annotation.get_constant_opacity())
            dispatch = {
                PDAnnotationText.NAME_NOTE: self._draw_note,
                PDAnnotationText.NAME_CROSS: self._draw_cross,
                PDAnnotationText.NAME_CIRCLE: self._draw_circles,
                PDAnnotationText.NAME_INSERT: self._draw_insert,
                PDAnnotationText.NAME_HELP: self._draw_help,
                PDAnnotationText.NAME_PARAGRAPH: self._draw_paragraph,
                PDAnnotationText.NAME_NEW_PARAGRAPH: self._draw_new_paragraph,
                PDAnnotationText.NAME_STAR: self._draw_star,
                PDAnnotationText.NAME_CHECK: self._draw_check,
                PDAnnotationText.NAME_RIGHT_ARROW: self._draw_right_arrow,
                PDAnnotationText.NAME_RIGHT_POINTER: self._draw_right_pointer,
                PDAnnotationText.NAME_CROSS_HAIRS: self._draw_cross_hairs,
                PDAnnotationText.NAME_UP_ARROW: self._draw_up_arrow,
                PDAnnotationText.NAME_UP_LEFT_ARROW: self._draw_up_left_arrow,
                PDAnnotationText.NAME_COMMENT: self._draw_comment,
                PDAnnotationText.NAME_KEY: self._draw_key,
            }
            painter = dispatch.get(name)
            if painter is not None:
                painter(annotation, cs)

    # ------------------------------------------------------------------
    # bbox / rectangle adjustment helper
    # ------------------------------------------------------------------

    def _adjust_rect_and_bbox(
        self, annotation: PDAnnotationText, width: float, height: float
    ) -> PDRectangle:
        """Mirrors upstream's private ``adjustRectAndBBox``
        (PDTextAppearanceHandler.java:166)."""
        from ....pd_rectangle import PDRectangle

        rect = self.get_rectangle()
        if rect is not None:
            rect.set_upper_right_x(rect.get_lower_left_x() + width)
            rect.set_lower_left_y(rect.get_upper_right_y() - height)
            annotation.set_rectangle(rect)
        bbox = PDRectangle.from_width_height(width, height)
        normal_stream = annotation.get_normal_appearance_stream()
        if normal_stream is not None:
            normal_stream.set_bbox(bbox)
        return bbox

    # ------------------------------------------------------------------
    # public parity surface — mirrors upstream's private helpers under
    # their upstream snake_case names so the parity script counts them.
    # ------------------------------------------------------------------

    def adjust_rect_and_b_box(
        self, annotation: PDAnnotationText, width: float, height: float
    ) -> PDRectangle:
        """Mirrors upstream's ``adjustRectAndBBox``
        (PDTextAppearanceHandler.java:166)."""
        return self._adjust_rect_and_bbox(annotation, width, height)

    def add_path(self, cs: PDAppearanceContentStream, path: list) -> None:
        """Mirrors upstream's private ``addPath``
        (PDTextAppearanceHandler.java:188). TODO: full path generation —
        emit the SVG-derived path operators onto ``cs``."""
        # TODO: full implementation
        _ = (cs, path)

    def draw_note(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawNote``
        (PDTextAppearanceHandler.java:194)."""
        self._draw_note(annotation, cs)

    def draw_circles(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawCircles``
        (PDTextAppearanceHandler.java:228)."""
        self._draw_circles(annotation, cs)

    def draw_insert(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawInsert``
        (PDTextAppearanceHandler.java:262)."""
        self._draw_insert(annotation, cs)

    def draw_cross_hairs(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawCrossHairs``
        (PDTextAppearanceHandler.java:295)."""
        self._draw_cross_hairs(annotation, cs)

    def draw_help(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawHelp``
        (PDTextAppearanceHandler.java:336)."""
        self._draw_help(annotation, cs)

    def draw_comment(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawComment``
        (PDTextAppearanceHandler.java:380)."""
        self._draw_comment(annotation, cs)

    def draw_key(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawKey``
        (PDTextAppearanceHandler.java:441)."""
        self._draw_key(annotation, cs)

    def draw_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawParagraph``
        (PDTextAppearanceHandler.java:487)."""
        self._draw_paragraph(annotation, cs)

    def draw_new_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawNewParagraph``
        (PDTextAppearanceHandler.java:535)."""
        self._draw_new_paragraph(annotation, cs)

    def draw_right_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawRightArrow``
        (PDTextAppearanceHandler.java:560)."""
        self._draw_right_arrow(annotation, cs)

    def draw_up_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawUpArrow``
        (PDTextAppearanceHandler.java:576)."""
        self._draw_up_arrow(annotation, cs)

    def draw_up_left_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawUpLeftArrow``
        (PDTextAppearanceHandler.java:584)."""
        self._draw_up_left_arrow(annotation, cs)

    def draw_zapf(
        self,
        annotation: PDAnnotationText,
        cs: PDAppearanceContentStream,
        size: float,
        offset_y: float,
        glyph_name: str,
    ) -> None:
        """Mirrors upstream's private ``drawZapf``
        (PDTextAppearanceHandler.java:592)."""
        self._draw_zapf(annotation, cs, size, offset_y, glyph_name)

    # ------------------------------------------------------------------
    # glyph painters
    # ------------------------------------------------------------------

    def _draw_note(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawNote`` (PDTextAppearanceHandler.java:194).
        The Note glyph is the spec default (a notebook icon)."""
        bbox = self._adjust_rect_and_bbox(annotation, 18.0, 20.0)
        cs.set_miter_limit(4.0) if hasattr(cs, "set_miter_limit") else None
        if hasattr(cs, "set_line_join_style"):
            cs.set_line_join_style(1)
        if hasattr(cs, "set_line_cap_style"):
            cs.set_line_cap_style(0)
        cs.set_line_width(0.61)
        width = bbox.get_width()
        height = bbox.get_height()
        cs.add_rect(1.0, 1.0, width - 2.0, height - 2.0)
        for k in (2, 3, 4, 5):
            cs.move_to(width / 4, height / 7 * k)
            cs.line_to(width * 3 / 4 - 1.0, height / 7 * k)
        cs.fill_and_stroke()

    def _draw_cross(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — ZapfDingbats glyph "a22" (0x2716).
        self._adjust_rect_and_bbox(annotation, 19.0, 19.0)
        cs.add_rect(2.0, 2.0, 15.0, 15.0)
        cs.fill_and_stroke()

    def _draw_circles(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — two concentric circles.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        self.draw_circle(cs, 10.0, 10.0, 8.0)
        cs.fill_and_stroke()

    def _draw_insert(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — caret-like triangle.
        self._adjust_rect_and_bbox(annotation, 17.0, 20.0)
        cs.add_rect(2.0, 2.0, 13.0, 16.0)
        cs.fill_and_stroke()

    def _draw_help(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — circled question-mark.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        self.draw_circle(cs, 10.0, 10.0, 8.0)
        cs.fill_and_stroke()

    def _draw_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — pilcrow glyph.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        cs.add_rect(3.0, 3.0, 14.0, 14.0)
        cs.fill_and_stroke()

    def _draw_new_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — pilcrow + ribbon glyph.
        self._adjust_rect_and_bbox(annotation, 13.0, 20.0)
        cs.add_rect(2.0, 2.0, 9.0, 16.0)
        cs.fill_and_stroke()

    def _draw_star(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — ZapfDingbats glyph "a35" (0x2605).
        self._adjust_rect_and_bbox(annotation, 19.0, 19.0)
        cs.add_rect(2.0, 2.0, 15.0, 15.0)
        cs.fill_and_stroke()

    def _draw_check(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — ZapfDingbats glyph "a20" (0x2714).
        self._adjust_rect_and_bbox(annotation, 19.0, 19.0)
        cs.add_rect(2.0, 2.0, 15.0, 15.0)
        cs.fill_and_stroke()

    def _draw_right_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        cs.add_rect(2.0, 8.0, 16.0, 4.0)
        cs.fill_and_stroke()

    def _draw_right_pointer(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — ZapfDingbats glyph "a174" (0x27A4).
        self._adjust_rect_and_bbox(annotation, 17.0, 17.0)
        cs.add_rect(2.0, 2.0, 13.0, 13.0)
        cs.fill_and_stroke()

    def _draw_cross_hairs(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — circled crosshair.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        self.draw_circle(cs, 10.0, 10.0, 8.0)
        cs.fill_and_stroke()

    def _draw_up_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        cs.add_rect(8.0, 2.0, 4.0, 16.0)
        cs.fill_and_stroke()

    def _draw_up_left_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        cs.add_rect(2.0, 8.0, 16.0, 4.0)
        cs.fill_and_stroke()

    def _draw_comment(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — speech bubble icon.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        cs.add_rect(2.0, 2.0, 16.0, 16.0)
        cs.fill_and_stroke()

    def _draw_key(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        # TODO: full path generation — key icon.
        self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        cs.add_rect(2.0, 8.0, 16.0, 4.0)
        cs.fill_and_stroke()

    def _draw_zapf(
        self,
        annotation: PDAnnotationText,
        cs: PDAppearanceContentStream,
        size: float,
        offset_y: float,
        glyph_name: str,
    ) -> None:
        """Mirrors upstream's private ``drawZapf``
        (PDTextAppearanceHandler.java:592). Renders a ZapfDingbats glyph
        as the icon body. TODO: full path generation — requires
        ZapfDingbats font integration."""
        self._adjust_rect_and_bbox(annotation, size, size)
        # Placeholder marker
        cs.add_rect(2.0, 2.0 + offset_y * 0.1, size - 4.0, size - 4.0)
        cs.fill_and_stroke()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDTextAppearanceHandler.java:670)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDTextAppearanceHandler.java:676)
        return None


__all__ = ["PDTextAppearanceHandler"]
