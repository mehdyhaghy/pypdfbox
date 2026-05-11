from __future__ import annotations

from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDHighlightAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a highlight annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDHighlightAppearanceHandler``.

    Upstream wraps the quad-fill in a two-form-XObject transparency
    group with a Multiply blend mode so the highlight visually
    multiplies over the underlying text. PDFormXObject does not exist in
    pypdfbox yet, so this lite port applies the same alpha + Multiply
    blend ExtGState directly to the appearance content stream — the
    visible result is equivalent for single-quad highlights.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDHighlightAppearanceHandler.java:54)."""
        from ..pd_annotation_highlight import PDAnnotationHighlight

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationHighlight):
            return
        paths_array = annotation.get_quad_points()
        if paths_array is None:
            return
        fill_components = self._color_components_from_annotation(annotation)
        if fill_components is None:
            return
        rect = annotation.get_rectangle()
        if rect is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )

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
        max_delta = 0.0
        for i in range(len(paths_array) // 8):
            delta = max(
                (paths_array[i + 0] - paths_array[i + 4]) / 4,
                (paths_array[i + 1] - paths_array[i + 5]) / 4,
            )
            if delta > max_delta:
                max_delta = delta
        rect.set_lower_left_x(min(min_x - ab.width / 2 - max_delta, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - ab.width / 2 - max_delta, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + ab.width + max_delta, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + ab.width + max_delta, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        with self.get_normal_appearance_as_content_stream() as cs:
            # Emit the alpha + Multiply blend mode via ExtGState; this
            # mirrors the two ExtGStates upstream sets on the outer
            # content stream (r0 = alpha constants, r1 = Multiply blend).
            self._apply_highlight_extgstate(cs, annotation.get_constant_opacity())
            cs.set_non_stroking_color(fill_components)
            offset = 0
            while offset + 7 < len(paths_array):
                # Correct quadpoint ordering: 4,5 0,1 2,3 6,7
                # (PDHighlightAppearanceHandler.java:140).
                # Compute Bezier control delta for the "curvy" rounded
                # ends — upstream uses ~1/4 of the quad height/width
                # depending on orientation.
                delta = 0.0
                if (
                    paths_array[offset + 0] == paths_array[offset + 4]
                    and paths_array[offset + 1] == paths_array[offset + 3]
                    and paths_array[offset + 2] == paths_array[offset + 6]
                    and paths_array[offset + 5] == paths_array[offset + 7]
                ):
                    # Horizontal highlight.
                    delta = (paths_array[offset + 1] - paths_array[offset + 5]) / 4
                elif (
                    paths_array[offset + 1] == paths_array[offset + 5]
                    and paths_array[offset + 0] == paths_array[offset + 2]
                    and paths_array[offset + 3] == paths_array[offset + 7]
                    and paths_array[offset + 4] == paths_array[offset + 6]
                ):
                    # Vertical highlight.
                    delta = (paths_array[offset + 0] - paths_array[offset + 4]) / 4

                cs.move_to(paths_array[offset + 4], paths_array[offset + 5])
                if paths_array[offset + 0] == paths_array[offset + 4]:
                    cs.curve_to(
                        paths_array[offset + 4] - delta,
                        paths_array[offset + 5] + delta,
                        paths_array[offset + 0] - delta,
                        paths_array[offset + 1] - delta,
                        paths_array[offset + 0],
                        paths_array[offset + 1],
                    )
                elif paths_array[offset + 5] == paths_array[offset + 1]:
                    cs.curve_to(
                        paths_array[offset + 4] + delta,
                        paths_array[offset + 5] + delta,
                        paths_array[offset + 0] - delta,
                        paths_array[offset + 1] + delta,
                        paths_array[offset + 0],
                        paths_array[offset + 1],
                    )
                else:
                    cs.line_to(paths_array[offset + 0], paths_array[offset + 1])

                cs.line_to(paths_array[offset + 2], paths_array[offset + 3])

                if paths_array[offset + 2] == paths_array[offset + 6]:
                    cs.curve_to(
                        paths_array[offset + 2] + delta,
                        paths_array[offset + 3] - delta,
                        paths_array[offset + 6] + delta,
                        paths_array[offset + 7] + delta,
                        paths_array[offset + 6],
                        paths_array[offset + 7],
                    )
                elif paths_array[offset + 3] == paths_array[offset + 7]:
                    cs.curve_to(
                        paths_array[offset + 2] - delta,
                        paths_array[offset + 3] - delta,
                        paths_array[offset + 6] + delta,
                        paths_array[offset + 7] - delta,
                        paths_array[offset + 6],
                        paths_array[offset + 7],
                    )
                else:
                    cs.line_to(paths_array[offset + 6], paths_array[offset + 7])

                cs.fill()
                offset += 8

    @staticmethod
    def _apply_highlight_extgstate(cs, constant_opacity: float) -> None:
        """Emit the two upstream ExtGStates as a single combined state.

        Upstream allocates two PDExtendedGraphicsState objects (alpha
        constants on r0, Multiply blend on r1) and applies them in
        sequence. The lite port collapses them so that the highlight
        path renders with the correct alpha + blend mode.
        """
        from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
        from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
            PDExtendedGraphicsState,
        )

        r0 = PDExtendedGraphicsState()
        r0.set_alpha_source_flag(False)
        r0.set_stroking_alpha_constant(constant_opacity)
        r0.set_non_stroking_alpha_constant(constant_opacity)
        cs.set_graphics_state_parameters(r0)

        r1 = PDExtendedGraphicsState()
        r1.set_alpha_source_flag(False)
        r1.set_blend_mode(BlendMode.MULTIPLY)
        cs.set_graphics_state_parameters(r1)

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDHighlightAppearanceHandler.java:216)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDHighlightAppearanceHandler.java:222)
        return None


__all__ = ["PDHighlightAppearanceHandler"]
