from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSFloat, COSInteger

from .cloudy_border import CloudyBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


# Adobe-derived Bezier magic constant for circles, sampled from Acrobat
# output (PDCircleAppearanceHandler.java:100).
_CIRCLE_MAGIC: float = 0.55555417


class PDCircleAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a circle annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDCircleAppearanceHandler``.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDCircleAppearanceHandler.java:55)."""
        from ..pd_annotation_square_circle import PDAnnotationSquareCircle
        from ..pd_border_effect_dictionary import PDBorderEffectDictionary

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationSquareCircle):
            return
        line_width = self.get_line_width()
        stroke_components = self._color_components_from_annotation(annotation)
        fill_components = self._interior_components(annotation)
        with self.get_normal_appearance_as_content_stream() as cs:
            has_stroke = stroke_components is not None
            if has_stroke:
                cs.set_stroking_color(stroke_components)
            has_background = fill_components is not None
            if has_background:
                cs.set_non_stroking_color(fill_components)
            self.set_opacity(
                cs,
                getattr(annotation, "get_constant_opacity", lambda: 1.0)(),
            )
            cs.set_border_line(
                line_width, annotation.get_border_style(), annotation.get_border()
            )
            border_effect = getattr(annotation, "get_border_effect", lambda: None)()
            if (
                border_effect is not None
                and border_effect.get_style()
                == PDBorderEffectDictionary.STYLE_CLOUDY
            ):
                # TODO: full path generation — fall back to the plain
                # ellipse until CloudyBorder lands the curl arcs.
                cloudy = CloudyBorder(
                    cs,
                    border_effect.get_intensity(),
                    line_width,
                    self.get_rectangle(),
                )
                cloudy.create_cloudy_ellipse(annotation.get_rect_difference())
                self._emit_ellipse(cs, annotation, line_width)
            else:
                self._emit_ellipse(cs, annotation, line_width)
            cs.draw_shape(line_width, has_stroke, has_background)

    def _emit_ellipse(self, cs, annotation, line_width: float) -> None:
        border_box = self.handle_border_box(annotation, line_width)
        x0 = border_box.get_lower_left_x()
        y0 = border_box.get_lower_left_y()
        x1 = border_box.get_upper_right_x()
        y1 = border_box.get_upper_right_y()
        xm = x0 + border_box.get_width() / 2
        ym = y0 + border_box.get_height() / 2
        v_offset = border_box.get_height() / 2 * _CIRCLE_MAGIC
        h_offset = border_box.get_width() / 2 * _CIRCLE_MAGIC
        cs.move_to(xm, y1)
        cs.curve_to(xm + h_offset, y1, x1, ym + v_offset, x1, ym)
        cs.curve_to(x1, ym - v_offset, xm + h_offset, y0, xm, y0)
        cs.curve_to(xm - h_offset, y0, x0, ym - v_offset, x0, ym)
        cs.curve_to(x0, ym + v_offset, xm - h_offset, y1, xm, y1)
        cs.close_path()

    def generate_rollover_appearance(self) -> None:
        # TODO to be implemented (PDCircleAppearanceHandler.java:122)
        return None

    def generate_down_appearance(self) -> None:
        # TODO to be implemented (PDCircleAppearanceHandler.java:128)
        return None

    def get_line_width(self) -> float:
        """Mirrors upstream's package-private ``getLineWidth``
        (PDCircleAppearanceHandler.java:148)."""
        annotation = self.get_annotation()
        bs = annotation.get_border_style()
        if bs is not None:
            return float(bs.get_width())
        border = annotation.get_border()
        if border is not None and border.size() >= 3:
            base = border.get_object(2)
            if isinstance(base, (COSFloat, COSInteger)):
                return float(base.value)
        return 1.0

    @staticmethod
    def _interior_components(annotation) -> list[float] | None:
        interior = getattr(annotation, "get_interior_color", lambda: None)()
        if interior is None:
            return None
        if hasattr(interior, "to_float_array"):
            arr = interior.to_float_array()
            return arr if arr else None
        if hasattr(interior, "size"):
            if interior.size() == 0:
                return None
            return interior.to_float_array()
        seq = list(interior)
        return seq if seq else None


__all__ = ["PDCircleAppearanceHandler"]
