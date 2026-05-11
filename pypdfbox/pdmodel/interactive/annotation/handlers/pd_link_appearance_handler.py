from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSFloat, COSInteger

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


_LOG = logging.getLogger(__name__)


class PDLinkAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a link annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDLinkAppearanceHandler``.

    Acrobat does not generate an appearance for link annotations — the
    underline / rectangle is drawn at render time. This handler exists so
    callers that explicitly want a baked-in appearance can request one.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDLinkAppearanceHandler.java:55)."""
        from ..pd_annotation_link import PDAnnotationLink
        from ..pd_border_style_dictionary import PDBorderStyleDictionary

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationLink):
            return
        rect = annotation.get_rectangle()
        if rect is None:
            # 660402-p1-AnnotationEmptyRect.pdf has /Rect entry with
            # 0 elements (PDLinkAppearanceHandler.java:62).
            return
        line_width = self.get_line_width()
        stroke_components = self._color_components_from_annotation(annotation)
        # Spec is unclear, but black is what Adobe does
        # (PDLinkAppearanceHandler.java:72).
        if stroke_components is None:
            stroke_components = [0.0]
        with self.get_normal_appearance_as_content_stream() as cs:
            cs.set_stroking_color(stroke_components)
            has_stroke = True
            cs.set_border_line(
                line_width, annotation.get_border_style(), annotation.get_border()
            )
            border_edge = self.get_padded_rectangle(
                self.get_rectangle(), line_width / 2
            )
            paths_array = annotation.get_quad_points()
            if paths_array is not None:
                # QuadPoints shall be ignored if any coordinate lies
                # outside Rect (PDLinkAppearanceHandler.java:88).
                for i in range(len(paths_array) // 2):
                    x = paths_array[i * 2]
                    y = paths_array[i * 2 + 1]
                    if not rect.contains(x, y):
                        _LOG.warning(
                            "At least one /QuadPoints entry (%s;%s) is "
                            "outside of rectangle %s, /QuadPoints are "
                            "ignored and /Rect is used instead",
                            x,
                            y,
                            rect,
                        )
                        paths_array = None
                        break
            if paths_array is None:
                # Convert rectangle coordinates as if it were a
                # /QuadPoints entry.
                paths_array = [
                    border_edge.get_lower_left_x(),
                    border_edge.get_lower_left_y(),
                    border_edge.get_upper_right_x(),
                    border_edge.get_lower_left_y(),
                    border_edge.get_upper_right_x(),
                    border_edge.get_upper_right_y(),
                    border_edge.get_lower_left_x(),
                    border_edge.get_upper_right_y(),
                ]
            underlined = False
            if len(paths_array) >= 8:
                border_style = annotation.get_border_style()
                if border_style is not None:
                    underlined = (
                        border_style.get_style()
                        == PDBorderStyleDictionary.STYLE_UNDERLINE
                    )
            offset = 0
            while offset + 7 < len(paths_array):
                cs.move_to(paths_array[offset], paths_array[offset + 1])
                cs.line_to(paths_array[offset + 2], paths_array[offset + 3])
                if not underlined:
                    cs.line_to(paths_array[offset + 4], paths_array[offset + 5])
                    cs.line_to(paths_array[offset + 6], paths_array[offset + 7])
                    cs.close_path()
                offset += 8
            cs.draw_shape(line_width, has_stroke, False)

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDLinkAppearanceHandler.java:149)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDLinkAppearanceHandler.java:155)
        return None

    def get_line_width(self) -> float:
        """Mirrors upstream's package-private ``getLineWidth``
        (PDLinkAppearanceHandler.java:175)."""
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


__all__ = ["PDLinkAppearanceHandler"]
