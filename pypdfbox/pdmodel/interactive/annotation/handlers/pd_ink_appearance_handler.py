from __future__ import annotations

from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDInkAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for an ink annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDInkAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDInkAppearanceHandler.java:48)."""
        from ..pd_annotation_ink import PDAnnotationInk

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationInk):
            return
        stroke_components = self._color_components_from_annotation(annotation)
        if stroke_components is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        if ab.width == 0:
            return
        # Upstream calls getInkList() unconditionally (returns an empty
        # float[][] when /InkList is absent or empty) and does NOT
        # early-return on an empty list — it still opens the content stream
        # and emits the stroke colour + line width with no path. Mirror that:
        # an absent or empty /InkList leaves the loop body empty and the
        # rect/bbox unchanged (the inf-seeded min/max collapse to the
        # original /Rect), matching PDFBox byte-for-byte.
        ink_list_wrapper = annotation.get_ink_list()
        path_infos = (
            ink_list_wrapper.get_paths() if ink_list_wrapper is not None else []
        )
        paths: list[list[tuple[float, float]]] = [
            info.get_points() for info in path_infos
        ]
        # Compute bounding extents over every ink path.
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for path_points in paths:
            for x, y in path_points:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
        rect = annotation.get_rectangle()
        if rect is None:
            return
        rect.set_lower_left_x(min(min_x - ab.width * 2, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width * 2, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width * 2, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width * 2, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)
        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_stroking_color(self._stroking_color(stroke_components))
            if ab.dash_array is not None:
                cs.set_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)
            for path_points in paths:
                for i, (x, y) in enumerate(path_points):
                    if i == 0:
                        cs.move_to(x, y)
                    else:
                        cs.line_to(x, y)
                cs.stroke()

    @staticmethod
    def _stroking_color(components: list[float]):  # type: ignore[no-untyped-def]
        """Wrap the raw ``/C`` components in a :class:`PDColor` carrying the
        device color space implied by the component count (1 → DeviceGray,
        3 → DeviceRGB, 4 → DeviceCMYK), mirroring upstream ``ink.getColor()``.

        Upstream passes the full ``PDColor`` to ``cs.setStrokingColor`` so the
        appearance stream emits ``/DeviceRGB CS <r> <g> <b> SC`` (color-space
        name + ``CS`` + components + ``SC``), never the device-shorthand
        ``RG``/``G``/``K`` operators. A bare component list would have routed
        through the shorthand path and diverged byte-for-byte from PDFBox.
        """
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
        from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
        from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
        from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

        if len(components) == 1:
            color_space = PDDeviceGray.INSTANCE
        elif len(components) == 4:
            color_space = PDDeviceCMYK.INSTANCE
        else:
            color_space = PDDeviceRGB.INSTANCE
        return PDColor(list(components), color_space)

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDInkAppearanceHandler.java:135)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDInkAppearanceHandler.java:141)
        return None


__all__ = ["PDInkAppearanceHandler"]
