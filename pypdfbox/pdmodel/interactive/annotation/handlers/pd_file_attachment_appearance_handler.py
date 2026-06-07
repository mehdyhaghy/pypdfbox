from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.util.matrix import Matrix

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation
    from ..pd_appearance_content_stream import PDAppearanceContentStream


_GLYPH_SIZE: int = 18


def _apply_matrix(cs: PDAppearanceContentStream, matrix: Matrix) -> None:
    """Emit the ``cm`` operator with the six components of ``matrix``.

    Required because the runtime ``PDAppearanceContentStream.transform``
    method (inherited from :class:`PDPageContentStream`) takes six explicit
    floats, not a :class:`Matrix` instance — whereas upstream's Java
    equivalent accepts the Matrix directly.
    """
    cs.transform(
        matrix.get_scale_x(),
        matrix.get_shear_y(),
        matrix.get_shear_x(),
        matrix.get_scale_y(),
        matrix.get_translate_x(),
        matrix.get_translate_y(),
    )


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

        Shape is from
        https://raw.githubusercontent.com/Iconscout/unicons/master/svg/line/paperclip.svg
        (Apache licensed).
        """
        cs.move_to(13.574, 9.301)
        cs.line_to(8.926, 13.949)
        cs.curve_to(7.648, 15.227, 5.625, 15.227, 4.426, 13.949)
        cs.curve_to(3.148, 12.676, 3.148, 10.648, 4.426, 9.449)
        cs.line_to(10.426, 3.449)
        cs.curve_to(11.176, 2.773, 12.301, 2.773, 13.051, 3.449)
        cs.curve_to(13.801, 4.199, 13.801, 5.398, 13.051, 6.074)
        cs.line_to(7.875, 11.25)
        cs.curve_to(7.648, 11.477, 7.273, 11.477, 7.051, 11.25)
        cs.curve_to(6.824, 11.023, 6.824, 10.648, 7.051, 10.426)
        cs.line_to(10.875, 6.602)
        cs.curve_to(11.176, 6.301, 11.176, 5.852, 10.875, 5.551)
        cs.curve_to(10.574, 5.25, 10.125, 5.25, 9.824, 5.551)
        cs.line_to(6.0, 9.449)
        cs.curve_to(5.176, 10.273, 5.176, 11.551, 6.0, 12.375)
        cs.curve_to(6.824, 13.125, 8.102, 13.125, 8.926, 12.375)
        cs.line_to(14.102, 7.199)
        cs.curve_to(15.449, 5.852, 15.449, 3.75, 14.102, 2.398)
        cs.curve_to(12.75, 1.051, 10.648, 1.051, 9.301, 2.398)
        cs.line_to(3.301, 8.398)
        cs.curve_to(2.398, 9.301, 1.949, 10.5, 1.949, 11.699)
        cs.curve_to(1.949, 14.324, 4.051, 16.352, 6.676, 16.352)
        cs.curve_to(7.949, 16.352, 9.074, 15.824, 9.977, 15.0)
        cs.line_to(14.625, 10.352)
        cs.curve_to(14.926, 10.051, 14.926, 9.602, 14.625, 9.301)
        cs.curve_to(14.324, 9.0, 13.875, 9.0, 13.574, 9.301)
        cs.close_path()
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_paperclip = draw_paperclip

    def draw_push_pin(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawPushPin``
        (PDFileAttachmentAppearanceHandler.java:132).

        Source: https://www.svgrepo.com/svg/269187/push-pin (License: CC0).
        """
        # ty 18 is from the caller, scale 0.022 is by trial and error
        _apply_matrix(cs, Matrix(0.022, 0, 0, -0.022, 0.0, 18.0))
        _apply_matrix(cs, Matrix.get_translate_instance(586.47, 178.97))
        cs.move_to(0, 0)
        cs.curve_to(13.0, 0.0, 23.43, -10.58, 23.43, -23.57)
        cs.line_to(23.43, -70.53)
        cs.curve_to(23.43, -109.32, -8.19, -141.06, -47.03, -141.06)
        cs.line_to(-329.17, -141.06)
        cs.curve_to(-368.17, -141.06, -399.79, -109.32, -399.79, -70.53)
        cs.line_to(-399.79, -23.57)
        cs.curve_to(-399.79, -10.58, -389.19, 0.0, -376.19, 0.0)
        cs.line_to(-305.74, 0.0)
        cs.line_to(-305.74, 129.52)
        cs.curve_to(-364.0, 168.47, -399.79, 234.67, -399.79, 305.36)
        cs.curve_to(-399.79, 318.34, -389.19, 328.76, -376.19, 328.76)
        cs.line_to(-211.69, 328.76)
        cs.line_to(-211.69, 555.9)
        cs.curve_to(-211.69, 568.88, -201.1, 579.3, -188.1, 579.3)
        cs.curve_to(-175.1, 579.3, -164.67, 568.88, -164.67, 555.9)
        cs.line_to(-164.67, 328.76)
        cs.line_to(0.0, 328.76)
        cs.curve_to(13.0, 328.76, 23.43, 318.34, 23.43, 305.36)
        cs.curve_to(23.43, 234.67, -12.2, 168.47, -70.62, 129.52)
        cs.line_to(-70.62, 0.0)
        cs.line_to(0.0, 0.0)
        cs.close_path()
        cs.move_to(-25.2, 281.79)
        cs.line_to(-351.0, 281.79)
        cs.curve_to(-343.77, 232.42, -314.24, 188.18, -270.43, 162.86)
        cs.curve_to(-263.21, 158.69, -258.71, 150.99, -258.71, 142.5)
        cs.line_to(-258.71, 0.0)
        cs.line_to(-117.64, 0.0)
        cs.line_to(-117.64, 142.5)
        cs.curve_to(-117.64, 150.99, -113.15, 158.69, -105.77, 162.86)
        cs.curve_to(-61.95, 188.18, -32.42, 232.42, -25.2, 281.79)
        cs.close_path()
        cs.move_to(-352.76, -46.97)
        cs.line_to(-352.76, -70.53)
        cs.curve_to(-352.76, -83.52, -342.17, -93.93, -329.17, -93.93)
        cs.line_to(-47.03, -93.93)
        cs.curve_to(-34.03, -93.93, -23.59, -83.52, -23.59, -70.53)
        cs.line_to(-23.59, -46.97)
        cs.line_to(-352.76, -46.97)
        cs.line_to(-352.76, -46.97)
        cs.close_path()
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_push_pin = draw_push_pin

    def draw_graph(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawGraph``
        (PDFileAttachmentAppearanceHandler.java:185).

        Source: https://www.svgrepo.com/svg/339018/chart-histogram
        Author: Carbon Design https://github.com/carbon-design-system/carbon
        (License: Apache).
        """
        # ty 18 is from the caller, scale 0.022 is by trial and error
        _apply_matrix(cs, Matrix(0.022, 0, 0, -0.022, 0.0, 18.0))
        _apply_matrix(cs, Matrix.get_translate_instance(736.04, 907.89))
        cs.move_to(0.0, 0.0)
        cs.line_to(-675.23, 0.0)
        cs.curve_to(-679.72, 0.0, -683.41, -3.53, -683.41, -8.01)
        cs.line_to(-683.41, -683.37)
        cs.line_to(-667.22, -683.37)
        cs.line_to(-667.22, -353.95)
        cs.curve_to(-583.85, -357.8, -541.53, -419.99, -500.49, -480.27)
        cs.curve_to(-459.93, -539.74, -418.09, -601.46, -337.61, -601.46)
        cs.curve_to(-257.14, -601.46, -215.3, -539.74, -174.74, -480.27)
        cs.curve_to(-132.58, -418.07, -88.81, -353.79, 0.0, -353.79)
        cs.line_to(0.0, -337.6)
        cs.curve_to(-97.31, -337.6, -143.48, -405.41, -188.2, -471.13)
        cs.curve_to(-228.12, -529.8, -265.8, -585.27, -337.61, -585.27)
        cs.curve_to(-409.43, -585.27, -447.11, -529.8, -487.03, -471.13)
        cs.curve_to(-530.47, -407.33, -575.36, -341.45, -667.22, -337.76)
        cs.line_to(-667.22, -16.19)
        cs.line_to(-615.76, -16.19)
        cs.line_to(-615.76, -255.68)
        cs.curve_to(-615.76, -260.17, -612.23, -263.7, -607.74, -263.7)
        cs.line_to(-525.82, -263.7)
        cs.line_to(-525.82, -345.77)
        cs.curve_to(-525.82, -350.26, -522.13, -353.79, -517.64, -353.79)
        cs.line_to(-435.73, -353.79)
        cs.line_to(-435.73, -458.31)
        cs.curve_to(-435.73, -462.8, -432.2, -466.32, -427.71, -466.32)
        cs.line_to(-337.61, -466.32)
        cs.curve_to(-333.13, -466.32, -329.6, -462.8, -329.6, -458.31)
        cs.line_to(-329.6, -421.28)
        cs.line_to(-247.68, -421.28)
        cs.curve_to(-243.19, -421.28, -239.5, -417.75, -239.5, -413.26)
        cs.line_to(-239.5, -331.35)
        cs.line_to(-157.58, -331.35)
        cs.curve_to(-153.1, -331.35, -149.41, -327.66, -149.41, -323.17)
        cs.line_to(-149.41, -218.81)
        cs.line_to(-67.49, -218.81)
        cs.curve_to(-63.0, -218.81, -59.47, -215.13, -59.47, -210.64)
        cs.line_to(-59.47, -16.19)
        cs.line_to(0.0, -16.19)
        cs.line_to(0.0, 0.0)
        cs.close_path()
        cs.move_to(-149.41, -16.19)
        cs.line_to(-75.67, -16.19)
        cs.line_to(-75.67, -202.62)
        cs.line_to(-149.41, -202.62)
        cs.line_to(-149.41, -16.19)
        cs.close_path()
        cs.move_to(-239.5, -16.19)
        cs.line_to(-165.76, -16.19)
        cs.line_to(-165.76, -315.16)
        cs.line_to(-239.5, -315.16)
        cs.line_to(-239.5, -16.19)
        cs.close_path()
        cs.move_to(-329.6, -16.19)
        cs.line_to(-255.7, -16.19)
        cs.line_to(-255.7, -405.09)
        cs.line_to(-329.6, -405.09)
        cs.line_to(-329.6, -16.19)
        cs.close_path()
        cs.move_to(-419.53, -16.19)
        cs.line_to(-345.79, -16.19)
        cs.line_to(-345.79, -450.13)
        cs.line_to(-419.53, -450.13)
        cs.line_to(-419.53, -16.19)
        cs.close_path()
        cs.move_to(-509.63, -16.19)
        cs.line_to(-435.73, -16.19)
        cs.line_to(-435.73, -337.6)
        cs.line_to(-509.63, -337.6)
        cs.line_to(-509.63, -16.19)
        cs.close_path()
        cs.move_to(-599.56, -16.19)
        cs.line_to(-525.82, -16.19)
        cs.line_to(-525.82, -247.51)
        cs.line_to(-599.56, -247.51)
        cs.line_to(-599.56, -16.19)
        cs.close_path()
        cs.fill()

    # Backwards-compatible private-name alias.
    _draw_graph = draw_graph

    def draw_tag(self, cs: PDAppearanceContentStream) -> None:
        """Mirrors upstream ``drawTag``
        (PDFileAttachmentAppearanceHandler.java:273).

        Source: https://www.svgrepo.com/svg/29652/tag (License: CC0).
        """
        # ty 18 is from the caller, scale 0.022 is by trial and error
        _apply_matrix(cs, Matrix(0.022, 0, 0, -0.022, 0.0, 18.0))
        cs.save_graphics_state()
        _apply_matrix(cs, Matrix.get_translate_instance(209.26, 128.32))
        cs.move_to(0.0, 0.0)
        cs.curve_to(-44.73, 0.0, -80.64, 36.23, -80.64, 80.64)
        cs.curve_to(-80.64, 125.2, -44.57, 161.27, 0.0, 161.27)
        cs.curve_to(44.56, 161.27, 80.47, 125.04, 80.47, 80.64)
        cs.curve_to(80.63, 36.07, 44.56, 0.0, 0.0, 0.0)
        cs.close_path()
        cs.move_to(0.0, 132.74)
        cs.curve_to(-28.7, 132.74, -52.1, 109.33, -52.1, 80.64)
        cs.curve_to(-52.1, 51.94, -28.7, 28.54, 0.0, 28.54)
        cs.curve_to(28.69, 28.54, 51.93, 51.94, 51.93, 80.64)
        cs.curve_to(51.93, 109.33, 28.85, 132.74, 0.0, 132.74)
        cs.close_path()
        cs.fill()
        cs.restore_graphics_state()
        cs.save_graphics_state()
        _apply_matrix(cs, Matrix.get_translate_instance(382.22, 79.91))
        cs.move_to(0.0, 0.0)
        cs.curve_to(-14.58, -16.19, -35.1, -24.85, -57.22, -24.85)
        cs.line_to(-208.23, -26.45)
        cs.curve_to(-240.45, -26.45, -271.23, -14.75, -293.35, 8.66)
        cs.curve_to(-316.76, 30.78, -328.46, 61.56, -328.46, 93.78)
        cs.line_to(-327.02, 244.95)
        cs.curve_to(-325.57, 265.47, -318.2, 285.98, -302.17, 302.18)
        cs.line_to(58.68, 663.02)
        cs.line_to(360.85, 360.69)
        cs.line_to(0.0, 0.0)
        cs.line_to(0.0, 0.0)
        cs.close_path()
        cs.move_to(57.23, 621.82)
        cs.line_to(-283.09, 281.5)
        cs.curve_to(-293.35, 271.24, -299.12, 258.09, -299.12, 243.34)
        cs.line_to(-300.57, 93.78)
        cs.curve_to(-300.57, 70.38, -290.31, 46.81, -274.12, 29.34)
        cs.curve_to(-256.64, 11.7, -233.08, 1.44, -208.23, 1.44)
        cs.line_to(-58.67, 2.89)
        cs.curve_to(-44.08, 2.89, -30.77, 8.66, -20.51, 19.08)
        cs.line_to(319.81, 359.4)
        cs.line_to(57.23, 621.82)
        cs.close_path()
        cs.fill()
        cs.restore_graphics_state()

    # Backwards-compatible private-name alias.
    _draw_tag = draw_tag

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDFileAttachmentAppearanceHandler.java:326)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDFileAttachmentAppearanceHandler.java:332)
        return None


__all__ = ["PDFileAttachmentAppearanceHandler"]
