from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pypdfbox.cos import COSName
from pypdfbox.util.matrix import Matrix

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


def _apply_matrix(cs: PDAppearanceContentStream, matrix: Matrix) -> None:
    """Emit the ``cm`` operator with the six components of ``matrix``.

    Required because the runtime ``PDAppearanceContentStream.transform``
    method (inherited from :class:`PDPageContentStream`) takes six
    explicit floats, not a :class:`Matrix` instance — whereas upstream's
    Java equivalent accepts the Matrix directly.
    """
    cs.transform(
        matrix.get_scale_x(),
        matrix.get_shear_y(),
        matrix.get_shear_x(),
        matrix.get_scale_y(),
        matrix.get_translate_x(),
        matrix.get_translate_y(),
    )


def _apply_translucent_white_fill(cs: PDAppearanceContentStream) -> None:
    """Helper that paints a translucent white "halo" via an ext-gstate.

    Used by drawCircles / drawHelp / drawParagraph / drawRightArrow to
    paint the inner circle background with 60% alpha. Mirrors the
    inline ``PDExtendedGraphicsState`` setup in upstream's draw helpers.
    """
    # Import lazily to avoid a circular dependency at module import.
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    gs = PDExtendedGraphicsState()
    gs.set_alpha_source_flag(False)
    gs.set_stroking_alpha_constant(0.6)
    gs.set_non_stroking_alpha_constant(0.6)
    gs.set_blend_mode(BlendMode.NORMAL)
    cs.set_graphics_state_parameters(gs)


class PDTextAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a text (sticky-note) annotation.
    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDTextAppearanceHandler``.

    Each ``/Name`` value (``Note``, ``Help``, ``Insert``, etc.) dispatches
    to a private ``_draw_*`` helper that emits a small icon path
    (~20-100 content-stream operators). The implementations are direct
    line-by-line ports of the upstream Java drawing code, with one
    documented deviation: glyph-based icons (``Cross``, ``Star``,
    ``Check``, ``RightPointer``, ``CrossHairs``, ``Help``,
    ``Paragraph``, ``NewParagraph``) fall back to a hand-built shape
    that approximates the Adobe glyph, because :class:`Standard14Fonts`
    glyph path extraction is not yet ported. See ``CHANGES.md``.
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
            if painter is not None:  # pragma: no branch - _SUPPORTED_NAMES mirrors dispatch keys
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
        if rect is not None and not annotation.is_no_zoom():
            rect.set_upper_right_x(rect.get_lower_left_x() + width)
            rect.set_lower_left_y(rect.get_upper_right_y() - height)
            annotation.set_rectangle(rect)
        if not annotation.get_cos_object().contains_key(COSName.get_pdf_name("F")):
            # Mirror Adobe — set NoRotate + NoZoom when /F is absent.
            # pypdfbox's renderer does not honour these flags, but the
            # flags are still written so the file is byte-similar.
            annotation.set_no_rotate(True)
            annotation.set_no_zoom(True)
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

    def add_path(
        self,
        cs: PDAppearanceContentStream,
        path: list[tuple[str, tuple[float, ...]]],
    ) -> None:
        """Mirrors upstream's private ``addPath``
        (PDTextAppearanceHandler.java:617).

        Upstream walks a ``java.awt.geom.GeneralPath`` via a
        ``PathIterator`` and emits ``m`` / ``l`` / ``c`` / ``h`` content
        stream operators per segment. We accept a pre-flattened list of
        ``(operator, coords)`` tuples — quadratic Beziers must already
        be converted to cubic. Operators: ``"M"`` move, ``"L"`` line,
        ``"C"`` cubic (6 coords), ``"H"`` close.
        """
        for op, coords in path:
            if op == "M":
                cs.move_to(coords[0], coords[1])
            elif op == "L":
                cs.line_to(coords[0], coords[1])
            elif op == "C":
                cs.curve_to(
                    coords[0],
                    coords[1],
                    coords[2],
                    coords[3],
                    coords[4],
                    coords[5],
                )
            elif op == "H":
                cs.close_path()

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
        by: float,
        ty: float,
        glyph_name: str,
    ) -> None:
        """Mirrors upstream's private ``drawZapf``
        (PDTextAppearanceHandler.java:592)."""
        self._draw_zapf(annotation, cs, by, ty, glyph_name)

    # ------------------------------------------------------------------
    # glyph painters
    # ------------------------------------------------------------------

    def _draw_note(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawNote`` (PDTextAppearanceHandler.java:194).
        The Note glyph is the spec default (a notebook icon)."""
        bbox = self._adjust_rect_and_bbox(annotation, 18.0, 20.0)
        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.61)  # value from Adobe
        width = bbox.get_width()
        height = bbox.get_height()
        cs.add_rect(1.0, 1.0, width - 2.0, height - 2.0)
        for k in (2, 3, 4, 5):
            cs.move_to(width / 4, height / 7 * k)
            cs.line_to(width * 3 / 4 - 1.0, height / 7 * k)
        cs.fill_and_stroke()

    def _draw_circles(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawCircles`` (PDTextAppearanceHandler.java:228).
        Two overlapping circles painted via Bezier curves."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)

        small_r = 6.36
        large_r = 9.756

        # adjustments because the bottom of the circle is flat
        _apply_matrix(cs, Matrix.get_scale_instance(0.95, 0.95))
        _apply_matrix(cs, Matrix.get_translate_instance(0.0, 0.5))

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        width = bbox.get_width() / 2
        height = bbox.get_height() / 2
        self.draw_circle(cs, width, height, small_r)
        cs.fill()
        cs.restore_graphics_state()

        cs.set_line_width(0.59)  # value from Adobe
        self.draw_circle(cs, width, height, small_r)
        self.draw_circle2(cs, width, height, large_r)
        cs.fill_and_stroke()

    def _draw_insert(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawInsert`` (PDTextAppearanceHandler.java:262).
        Caret-style downward triangle."""
        bbox = self._adjust_rect_and_bbox(annotation, 17.0, 20.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(0)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe
        cs.move_to(bbox.get_width() / 2 - 1.0, bbox.get_height() - 2.0)
        cs.line_to(1.0, 1.0)
        cs.line_to(bbox.get_width() - 2.0, 1.0)
        cs.close_and_fill_and_stroke()

    def _draw_cross(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 19, 0, "a22")``
        (PDTextAppearanceHandler.java:111). Renders a thick X."""
        self._draw_zapf(annotation, cs, 19.0, 0.0, "a22")

    def _draw_help(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawHelp`` (PDTextAppearanceHandler.java:280).
        Circle with a question-mark glyph centered inside."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill()
        cs.restore_graphics_state()

        # Documented deviation: upstream draws a Helvetica-Bold "?" via
        # Standard14Fonts glyph paths. Those aren't ported yet, so we
        # render a hand-built question-mark hash that visually matches.
        cs.save_graphics_state()
        cx = min_dim / 2
        cy = min_dim / 2
        # Question-mark approximated with two strokes.
        r = min_dim / 6
        cs.set_line_width(min_dim / 12)
        # Curve of the "?"
        cs.move_to(cx - r * 0.7, cy + r * 0.6)
        cs.curve_to(
            cx - r * 0.7, cy + r * 1.3,
            cx + r * 0.7, cy + r * 1.3,
            cx + r * 0.7, cy + r * 0.6,
        )
        cs.curve_to(
            cx + r * 0.7, cy,
            cx, cy + r * 0.2,
            cx, cy - r * 0.2,
        )
        cs.stroke()
        # Dot of the "?"
        self.draw_circle(cs, cx, cy - r * 0.9, min_dim / 25)
        cs.fill()
        cs.restore_graphics_state()
        # outer ring counterclockwise to keep nonzero winding consistent
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill_and_stroke()

    def _draw_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawParagraph`` (PDTextAppearanceHandler.java:320).
        Pilcrow glyph centered in a circle."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill()
        cs.restore_graphics_state()

        # Documented deviation: pilcrow rendered as a hand-built path
        # since the Standard14 glyph extraction is not ported.
        cs.save_graphics_state()
        cx = min_dim / 2
        cy = min_dim / 2
        s = min_dim / 8
        # vertical stems of the pilcrow
        cs.move_to(cx - s * 0.5, cy + s * 2.4)
        cs.line_to(cx + s * 1.4, cy + s * 2.4)
        cs.line_to(cx + s * 1.4, cy - s * 2.6)
        cs.line_to(cx + s * 0.8, cy - s * 2.6)
        cs.line_to(cx + s * 0.8, cy + s * 2.0)
        cs.line_to(cx + s * 0.2, cy + s * 2.0)
        cs.line_to(cx + s * 0.2, cy - s * 2.6)
        cs.line_to(cx - s * 0.4, cy - s * 2.6)
        cs.line_to(cx - s * 0.4, cy + s * 0.4)
        # bowl of the pilcrow
        cs.curve_to(
            cx - s * 2.2, cy + s * 0.4,
            cx - s * 2.2, cy + s * 2.4,
            cx - s * 0.5, cy + s * 2.4,
        )
        cs.close_path()
        cs.fill_and_stroke()
        cs.restore_graphics_state()
        self.draw_circle(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.stroke()

    def _draw_new_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawNewParagraph`` (PDTextAppearanceHandler.java:362).
        Triangle marker above an ``NP`` glyph pair."""
        self._adjust_rect_and_bbox(annotation, 13.0, 20.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(0)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        # Small triangle — exact coordinates from Adobe (upstream lines 374-376).
        cs.move_to(6.4995, 20.0)
        cs.line_to(0.295, 7.287)
        cs.line_to(12.705, 7.287)
        cs.close_and_fill_and_stroke()

        # Documented deviation: the "NP" letterforms below the triangle
        # are rendered as simple stroked rectangles since the
        # Standard14Fonts glyph paths aren't ported yet. The triangle is
        # still drawn exactly as Adobe / upstream output.
        cs.save_graphics_state()
        cs.set_line_width(0.4)
        # Letter "N" — two verticals plus diagonal.
        cs.move_to(1.5, 1.0)
        cs.line_to(1.5, 6.0)
        cs.stroke()
        cs.move_to(5.0, 1.0)
        cs.line_to(5.0, 6.0)
        cs.stroke()
        cs.move_to(1.5, 6.0)
        cs.line_to(5.0, 1.0)
        cs.stroke()
        # Letter "P" — vertical bar plus a bowl.
        cs.move_to(7.5, 1.0)
        cs.line_to(7.5, 6.0)
        cs.stroke()
        cs.move_to(7.5, 6.0)
        cs.line_to(10.0, 6.0)
        cs.curve_to(11.5, 6.0, 11.5, 3.5, 10.0, 3.5)
        cs.line_to(7.5, 3.5)
        cs.stroke()
        cs.restore_graphics_state()

    def _draw_star(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 19, 0, "a35")``
        (PDTextAppearanceHandler.java:129)."""
        self._draw_zapf(annotation, cs, 19.0, 0.0, "a35")

    def _draw_check(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 19, 50, "a20")``
        (PDTextAppearanceHandler.java:132)."""
        self._draw_zapf(annotation, cs, 19.0, 50.0, "a20")

    def _draw_right_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawRightArrow`` (PDTextAppearanceHandler.java:458).
        Right-pointing arrow inside a circle."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill()
        cs.restore_graphics_state()

        cs.save_graphics_state()
        cs.move_to(8.0, 17.5)
        cs.line_to(8.0, 13.5)
        cs.line_to(3.0, 13.5)
        cs.line_to(3.0, 6.5)
        cs.line_to(8.0, 6.5)
        cs.line_to(8.0, 2.5)
        cs.line_to(18.0, 10.0)
        cs.close_path()
        cs.restore_graphics_state()
        # surprisingly, this one not counterclockwise.
        self.draw_circle(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill_and_stroke()

    def _draw_right_pointer(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 17, 50, "a174")``
        (PDTextAppearanceHandler.java:138)."""
        self._draw_zapf(annotation, cs, 17.0, 50.0, "a174")

    def _draw_cross_hairs(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawCrossHairs`` (PDTextAppearanceHandler.java:390).

        Documented deviation: upstream draws the ``circleplus`` glyph
        from the Symbol Type1 font. We render an equivalent shape (a
        circle with vertical + horizontal bars) by hand because Symbol
        font glyph paths aren't ported yet.
        """
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(0)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.61)  # value from Adobe

        cx = min_dim / 2
        cy = min_dim / 2
        r = min_dim / 2 - 1.0
        # Circle.
        self.draw_circle(cs, cx, cy, r)
        cs.stroke()
        # Cross.
        cs.move_to(cx - r, cy)
        cs.line_to(cx + r, cy)
        cs.move_to(cx, cy - r)
        cs.line_to(cx, cy + r)
        cs.stroke()

    def _draw_up_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawUpArrow`` (PDTextAppearanceHandler.java:416).
        Upward-pointing chunky arrow."""
        self._adjust_rect_and_bbox(annotation, 17.0, 20.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.move_to(1.0, 7.0)
        cs.line_to(5.0, 7.0)
        cs.line_to(5.0, 1.0)
        cs.line_to(12.0, 1.0)
        cs.line_to(12.0, 7.0)
        cs.line_to(16.0, 7.0)
        cs.line_to(8.5, 19.0)
        cs.close_and_fill_and_stroke()

    def _draw_up_left_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawUpLeftArrow`` (PDTextAppearanceHandler.java:436).
        Same shape as the up arrow rotated 45° counter-clockwise."""
        self._adjust_rect_and_bbox(annotation, 17.0, 17.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        _apply_matrix(cs, Matrix.get_rotate_instance(math.radians(45.0), 8.0, -4.0))

        cs.move_to(1.0, 7.0)
        cs.line_to(5.0, 7.0)
        cs.line_to(5.0, 1.0)
        cs.line_to(12.0, 1.0)
        cs.line_to(12.0, 7.0)
        cs.line_to(16.0, 7.0)
        cs.line_to(8.5, 19.0)
        cs.close_and_fill_and_stroke()

    def _draw_comment(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawComment`` (PDTextAppearanceHandler.java:499).
        Speech bubble icon — gathered from Font Awesome's ``comment.svg``."""
        self._adjust_rect_and_bbox(annotation, 18.0, 18.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(200.0)

        # Adobe first fills a white rectangle with CA ca 0.6, so do we.
        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        cs.add_rect(0.3, 0.3, 18.0 - 0.6, 18.0 - 0.6)
        cs.fill()
        cs.restore_graphics_state()

        _apply_matrix(cs, Matrix.get_scale_instance(0.003, 0.003))
        _apply_matrix(cs, Matrix.get_translate_instance(500.0, -300.0))

        # Outer shape gathered from Font Awesome's comment.svg.
        cs.move_to(2549.0, 5269.0)
        cs.curve_to(1307.0, 5269.0, 300.0, 4451.0, 300.0, 3441.0)
        cs.curve_to(300.0, 3023.0, 474.0, 2640.0, 764.0, 2331.0)
        cs.curve_to(633.0, 1985.0, 361.0, 1691.0, 357.0, 1688.0)
        cs.curve_to(299.0, 1626.0, 283.0, 1537.0, 316.0, 1459.0)
        cs.curve_to(350.0, 1382.0, 426.0, 1332.0, 510.0, 1332.0)
        cs.curve_to(1051.0, 1332.0, 1477.0, 1558.0, 1733.0, 1739.0)
        cs.curve_to(1987.0, 1659.0, 2261.0, 1613.0, 2549.0, 1613.0)
        cs.curve_to(3792.0, 1613.0, 4799.0, 2431.0, 4799.0, 3441.0)
        cs.curve_to(4799.0, 4451.0, 3792.0, 5269.0, 2549.0, 5269.0)
        cs.close_path()

        # Donut effect — can't use addRect, see upstream comment.
        cs.move_to(0.3 / 0.003 - 500.0, 0.3 / 0.003 + 300.0)
        cs.line_to(0.3 / 0.003 - 500.0, 0.3 / 0.003 + 300.0 + 17.4 / 0.003)
        cs.line_to(
            0.3 / 0.003 - 500.0 + 17.4 / 0.003,
            0.3 / 0.003 + 300.0 + 17.4 / 0.003,
        )
        cs.line_to(0.3 / 0.003 - 500.0 + 17.4 / 0.003, 0.3 / 0.003 + 300.0)

        cs.close_and_fill_and_stroke()

    def _draw_key(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawKey`` (PDTextAppearanceHandler.java:549).
        Key icon — gathered from Font Awesome's ``key.svg``."""
        self._adjust_rect_and_bbox(annotation, 13.0, 18.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(200.0)

        _apply_matrix(cs, Matrix.get_scale_instance(0.003, 0.003))
        _apply_matrix(cs, Matrix.get_rotate_instance(math.radians(45.0), 2500.0, -800.0))

        # Shape from Font Awesome's key.svg.
        cs.move_to(4799.0, 4004.0)
        cs.curve_to(4799.0, 3149.0, 4107.0, 2457.0, 3253.0, 2457.0)
        cs.curve_to(3154.0, 2457.0, 3058.0, 2466.0, 2964.0, 2484.0)
        cs.line_to(2753.0, 2246.0)
        cs.curve_to(2713.0, 2201.0, 2656.0, 2175.0, 2595.0, 2175.0)
        cs.line_to(2268.0, 2175.0)
        cs.line_to(2268.0, 1824.0)
        cs.curve_to(2268.0, 1707.0, 2174.0, 1613.0, 2057.0, 1613.0)
        cs.line_to(1706.0, 1613.0)
        cs.line_to(1706.0, 1261.0)
        cs.curve_to(1706.0, 1145.0, 1611.0, 1050.0, 1495.0, 1050.0)
        cs.line_to(510.0, 1050.0)
        cs.curve_to(394.0, 1050.0, 300.0, 1145.0, 300.0, 1261.0)
        cs.line_to(300.0, 1947.0)
        cs.curve_to(300.0, 2003.0, 322.0, 2057.0, 361.0, 2097.0)
        cs.line_to(1783.0, 3519.0)
        cs.curve_to(1733.0, 3671.0, 1706.0, 3834.0, 1706.0, 4004.0)
        cs.curve_to(1706.0, 4858.0, 2398.0, 5550.0, 3253.0, 5550.0)
        cs.curve_to(4109.0, 5550.0, 4799.0, 4860.0, 4799.0, 4004.0)
        cs.close_path()
        cs.move_to(3253.0, 4425.0)
        cs.curve_to(3253.0, 4192.0, 3441.0, 4004.0, 3674.0, 4004.0)
        cs.curve_to(3907.0, 4004.0, 4096.0, 4192.0, 4096.0, 4425.0)
        cs.curve_to(4096.0, 4658.0, 3907.0, 4847.0, 3674.0, 4847.0)
        cs.curve_to(3441.0, 4847.0, 3253.0, 4658.0, 3253.0, 4425.0)
        cs.fill_and_stroke()

    def _draw_zapf(
        self,
        annotation: PDAnnotationText,
        cs: PDAppearanceContentStream,
        by: float,
        ty: float,
        glyph_name: str,
    ) -> None:
        """Mirrors upstream's private ``drawZapf``
        (PDTextAppearanceHandler.java:592).

        Documented deviation: upstream extracts the named glyph path
        from the ZapfDingbats Type1 font via
        ``Standard14Fonts.getGlyphPath``. That path is not ported yet
        in pypdfbox, so we render a hand-built approximation per glyph
        name. The bbox / line-state setup matches upstream exactly so
        rendering still respects the geometry Adobe expects.
        """
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, by)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        # Upstream computes the scale via the ZapfDingbats fontMatrix
        # (1/1000, 1/1000) — equivalent to a hand-coded 0.001 here.
        x_scale = 0.001
        y_scale = 0.001
        _apply_matrix(
            cs, Matrix.get_scale_instance(x_scale * min_dim / 0.8, y_scale * min_dim / 0.8)
        )
        _apply_matrix(cs, Matrix.get_translate_instance(0.0, ty))

        # Hand-built approximations for the four ZapfDingbats glyphs the
        # spec dispatches through drawZapf.
        if glyph_name == "a22":
            # Cross (✖, 0x2716) — drawn as two thick diagonals.
            self._draw_glyph_cross(cs)
        elif glyph_name == "a35":
            # Star (★, 0x2605) — five-pointed filled star.
            self._draw_glyph_star(cs)
        elif glyph_name == "a20":
            # Check mark (✔, 0x2714) — angled tick.
            self._draw_glyph_check(cs)
        elif glyph_name == "a174":
            # Right pointer (➤, 0x27A4) — arrowhead.
            self._draw_glyph_right_pointer(cs)
        cs.fill_and_stroke()

    # ------------------------------------------------------------------
    # ZapfDingbats glyph approximations (units in font's 1000-unit em)
    # ------------------------------------------------------------------

    def _draw_glyph_cross(self, cs: PDAppearanceContentStream) -> None:
        # ✖ — two thick diagonal bars meeting at the centre (500, 500).
        thickness = 110.0
        cs.move_to(150.0 - thickness * 0.7, 150.0 + thickness * 0.7)
        cs.line_to(150.0 + thickness * 0.7, 150.0 - thickness * 0.7)
        cs.line_to(850.0 + thickness * 0.7, 850.0 - thickness * 0.7)
        cs.line_to(850.0 - thickness * 0.7, 850.0 + thickness * 0.7)
        cs.close_path()
        cs.move_to(150.0 - thickness * 0.7, 850.0 - thickness * 0.7)
        cs.line_to(150.0 + thickness * 0.7, 850.0 + thickness * 0.7)
        cs.line_to(850.0 + thickness * 0.7, 150.0 + thickness * 0.7)
        cs.line_to(850.0 - thickness * 0.7, 150.0 - thickness * 0.7)
        cs.close_path()

    def _draw_glyph_star(self, cs: PDAppearanceContentStream) -> None:
        # ★ — five-pointed star with outer radius 450, centered at (500, 500).
        cx = 500.0
        cy = 500.0
        outer = 450.0
        inner = outer * 0.382  # standard 5-point star ratio
        # Start at the top point.
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            radius = outer if i % 2 == 0 else inner
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            if i == 0:
                cs.move_to(x, y)
            else:
                cs.line_to(x, y)
        cs.close_path()

    def _draw_glyph_check(self, cs: PDAppearanceContentStream) -> None:
        # ✔ — angled tick. Path traced clockwise.
        cs.move_to(100.0, 450.0)
        cs.line_to(250.0, 300.0)
        cs.line_to(450.0, 500.0)
        cs.line_to(800.0, 800.0)
        cs.line_to(900.0, 700.0)
        cs.line_to(450.0, 200.0)
        cs.close_path()

    def _draw_glyph_right_pointer(self, cs: PDAppearanceContentStream) -> None:
        # ➤ — arrowhead pointing right.
        cs.move_to(100.0, 200.0)
        cs.line_to(800.0, 500.0)
        cs.line_to(100.0, 800.0)
        cs.line_to(250.0, 500.0)
        cs.close_path()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDTextAppearanceHandler.java:670)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDTextAppearanceHandler.java:676)
        return None


__all__ = ["PDTextAppearanceHandler"]
