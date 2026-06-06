from __future__ import annotations

from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


_ADOBE_DEFAULT_WIDTH: float = 1.5


class PDSquigglyAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a squiggly annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDSquigglyAppearanceHandler``.

    The squiggly sawtooth is painted exactly like upstream: for each quad
    a form XObject is drawn whose body fills a rectangle with an *uncolored
    tiling pattern* (``/PaintType 2``) whose one-cell content stream strokes
    the single zig-zag tooth ``0 1 m 5 11 l 10 1 l S``. The annotation
    colour is supplied through the ``/Pattern`` colour space
    (``patternName scn``). See
    ``PDSquigglyAppearanceHandler.java:106-163`` (PDFBox 3.0.7).
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDSquigglyAppearanceHandler.java:58)."""
        from ..pd_annotation_squiggly import PDAnnotationSquiggly

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationSquiggly):
            return
        rect = annotation.get_rectangle()
        if rect is None:
            return
        paths_array = annotation.get_quad_points()
        if paths_array is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        stroke_components = self._color_components_from_annotation(annotation)
        if stroke_components is None:
            return
        if ab.width == 0:
            ab.width = _ADOBE_DEFAULT_WIDTH

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
        rect.set_lower_left_x(min(min_x - ab.width / 2, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width / 2, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width / 2, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width / 2, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        from ....graphics.color.pd_color import PDColor
        from ....graphics.color.pd_device_rgb import PDDeviceRGB
        from ....graphics.color.pd_pattern import PDPattern
        from ....graphics.form.pd_form_x_object import PDFormXObject
        from ....graphics.pattern.pd_tiling_pattern import PDTilingPattern
        from ....pd_form_content_stream import PDFormContentStream
        from ....pd_pattern_content_stream import PDPatternContentStream
        from ....pd_rectangle import PDRectangle
        from ....pd_resources import PDResources

        # Mirrors upstream PDSquigglyAppearanceHandler.java:106-163. The
        # zig-zag is painted via an uncolored tiling pattern wrapped in a
        # form XObject, one per quad.
        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())

            # Upstream passes the typed PDColor to setStrokingColor, so the
            # appearance stream emits "/DeviceRGB CS r g b SC" (color-space
            # select + components + SC), not the device-shorthand RG.
            color = self._pd_color_from_components(stroke_components)
            cs.set_stroking_color(color)

            # quadpoints spec is incorrect
            # https://stackoverflow.com/questions/9855814/pdf-spec-vs-acrobat-creation-quadpoints
            for i in range(len(paths_array) // 8):
                base = i * 8
                # Adobe uses a fixed pattern that assumes a height of 40 and
                # transforms to that height horizontally and the same / 1.8
                # vertically. Translation based on bottom left, but slightly
                # different in Adobe (Java:123-124).
                height = paths_array[base + 1] - paths_array[base + 5]
                cs.transform(
                    height / 40.0,
                    0.0,
                    0.0,
                    height / 40.0 / 1.8,
                    paths_array[base + 4],
                    paths_array[base + 5],
                )

                # Create the form; BBox is mostly fixed, except for the
                # horizontal size (Java:129-133).
                form = PDFormXObject(self.create_cos_stream())
                # Upstream ``new PDRectangle(-0.5f, -0.5f, w, 13)`` where the
                # 4-arg Java ctor is (x, y, width, height); ``from_xywh``
                # matches that signature exactly (Java:130).
                form.set_bbox(
                    PDRectangle.from_xywh(
                        -0.5,
                        -0.5,
                        (paths_array[base + 2] - paths_array[base])
                        / height
                        * 40.0
                        + 0.5,
                        13.0,
                    )
                )
                form.set_resources(PDResources())
                form.set_matrix([1.0, 0.0, 0.0, 1.0, 0.5, 0.5])
                cs.draw_form(form)

                with PDFormContentStream(form) as form_cs:
                    pattern = PDTilingPattern()
                    pattern.set_b_box(PDRectangle.from_xywh(0, 0, 10, 12))
                    pattern.set_x_step(10)
                    pattern.set_y_step(13)
                    pattern.set_tiling_type(
                        PDTilingPattern.TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING
                    )
                    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
                    with PDPatternContentStream(pattern) as pattern_cs:
                        # from Adobe (Java:145-152)
                        pattern_cs.set_line_cap_style(1)
                        pattern_cs.set_line_join_style(1)
                        pattern_cs.set_line_width(1)
                        pattern_cs.set_miter_limit(10)
                        pattern_cs.move_to(0, 1)
                        pattern_cs.line_to(5, 11)
                        pattern_cs.line_to(10, 1)
                        pattern_cs.stroke()
                    pattern_name = form.get_resources().add(pattern)
                    # Upstream ``new PDPattern(null, PDDeviceRGB.INSTANCE)``
                    # (Java:155); the lite ``PDPattern`` ctor takes the
                    # underlying colour space as its sole positional arg.
                    pattern_color_space = PDPattern(PDDeviceRGB.INSTANCE)
                    pattern_color = PDColor(
                        list(stroke_components),
                        pattern_name,
                        pattern_color_space,
                    )
                    form_cs.set_non_stroking_color(pattern_color)

                    # With Adobe the horizontal size is slightly different,
                    # don't know why (Java:159-161).
                    form_cs.add_rect(
                        0,
                        0,
                        (paths_array[base + 2] - paths_array[base])
                        / height
                        * 40.0,
                        12,
                    )
                    form_cs.fill()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDSquigglyAppearanceHandler.java:172)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDSquigglyAppearanceHandler.java:178)
        return None


__all__ = ["PDSquigglyAppearanceHandler"]
