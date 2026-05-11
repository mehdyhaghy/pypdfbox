from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pypdfbox.cos import COSName

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


_COLOR_PATTERN = re.compile(r"color:\s*+#([0-9a-fA-F]{6})")


class PDFreeTextAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a free-text annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDFreeTextAppearanceHandler``.

    Partial implementation: upstream is 500 lines and handles text
    wrapping, ``/DA`` (default appearance) parsing, callout lines with
    line-ending shapes, ``/DS`` (default style string) CSS-ish color
    extraction, and the BS/Cloudy border interplay. The lite port lays
    down the box outline + callout polyline + opacity, and stubs the
    text rendering with a ``TODO: full path generation`` note. The
    method signatures match upstream so the text-render path can land
    incrementally.
    """

    DEFAULT_FONT_SIZE: float = 10.0
    DEFAULT_FONT_NAME: COSName = COSName.get_pdf_name("Helv")

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)
        self._font_size: float = self.DEFAULT_FONT_SIZE
        self._font_name: COSName = self.DEFAULT_FONT_NAME

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDFreeTextAppearanceHandler.java:72)."""
        from ..pd_annotation_free_text import PDAnnotationFreeText

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationFreeText):
            return
        if annotation.get_intent() == PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT:
            paths_array = annotation.get_callout()
            if paths_array is None or len(paths_array) not in (4, 6):
                paths_array = []
        else:
            paths_array = []
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        fill_components = self._color_components_from_annotation(annotation)

        with self.get_normal_appearance_as_content_stream(compress=True) as cs:
            has_background = fill_components is not None
            if has_background:
                cs.set_non_stroking_color(fill_components)
            self.set_opacity(cs, annotation.get_constant_opacity())
            # Adobe uses the last non-stroking color from /DA as stroking
            # color; here we mirror the fill color into stroke as a
            # simple approximation.
            stroke_components = fill_components
            # /DS color override
            default_styles = annotation.get_default_styles_string() if hasattr(
                annotation, "get_default_styles_string"
            ) else None
            if isinstance(default_styles, str):
                match = _COLOR_PATTERN.search(default_styles)
                if match is not None:
                    color_int = int(match.group(1), 16)
                    r = ((color_int >> 16) & 0xFF) / 255
                    g = ((color_int >> 8) & 0xFF) / 255
                    b = (color_int & 0xFF) / 255
                    # text color updates handled in TODO below
                    _ = (r, g, b)
            has_stroke = stroke_components is not None
            if has_stroke:
                cs.set_stroking_color(stroke_components)
            if ab.dash_array is not None:
                cs.set_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)

            line_ending_style = (
                annotation.get_line_ending_style()
                if hasattr(annotation, "get_line_ending_style")
                else None
            )
            # Callout line(s)
            for i in range(len(paths_array) // 2):
                x = paths_array[i * 2]
                y = paths_array[i * 2 + 1]
                if i == 0:
                    if (
                        line_ending_style in self.SHORT_STYLES
                        and len(paths_array) >= 4
                    ):
                        x1 = paths_array[2]
                        y1 = paths_array[3]
                        import math

                        length = math.hypot(x - x1, y - y1)
                        if length != 0:
                            x += (x1 - x) / length * ab.width
                            y += (y1 - y) / length * ab.width
                    cs.move_to(x, y)
                else:
                    cs.line_to(x, y)
            if paths_array:
                cs.stroke()

            # TODO: full path generation — paint the rectangle box (with
            # cloudy border when applicable), wrap and emit the
            # ``/Contents`` text via the parsed /DA + /DS state.
            rect = self.get_rectangle()
            if rect is not None:
                differences = annotation.get_rect_differences()
                box = self.apply_rect_differences(rect, differences)
                cs.add_rect(
                    box.get_lower_left_x(),
                    box.get_lower_left_y(),
                    box.get_width(),
                    box.get_height(),
                )
                cs.draw_shape(ab.width, has_stroke, has_background)

    def extract_non_stroking_color(self, annotation) -> list[float] | None:
        """Mirrors upstream's ``extractNonStrokingColor``
        (PDFreeTextAppearanceHandler.java:367) — full /DA parsing is
        deferred. Currently returns the annotation /C components."""
        # TODO: parse the /DA default appearance string for color ops.
        return self._color_components_from_annotation(annotation)

    # Backwards-compatible private-name alias.
    _extract_non_stroking_color = extract_non_stroking_color

    def extract_font_details(self, annotation) -> None:
        """Mirrors upstream's ``extractFontDetails``
        (PDFreeTextAppearanceHandler.java:435) — full /DA Tf parsing is
        deferred. Sets the default font_size / font_name."""
        # TODO: parse the /DA default appearance string for "Tf" entries.
        self._font_size = self.DEFAULT_FONT_SIZE
        self._font_name = self.DEFAULT_FONT_NAME

    # Backwards-compatible private-name alias.
    _extract_font_details = extract_font_details

    def generate_rollover_appearance(self) -> None:
        # TODO to be implemented (PDFreeTextAppearanceHandler.java:495)
        return None

    def generate_down_appearance(self) -> None:
        # TODO to be implemented (PDFreeTextAppearanceHandler.java:501)
        return None


__all__ = ["PDFreeTextAppearanceHandler"]
