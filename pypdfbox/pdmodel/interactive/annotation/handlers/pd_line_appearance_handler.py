from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


_FONT_SIZE: float = 9.0


class PDLineAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a line annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDLineAppearanceHandler``.

    Draws the line body, leader lines, line-ending shapes via
    :meth:`draw_style`, and inline / top caption text. Caption rendering
    uses :meth:`get_default_font` for width metrics and falls back to a
    monospace approximation if the font lacks ``get_string_width``.
    """

    FONT_SIZE: float = _FONT_SIZE

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDLineAppearanceHandler.java:52)."""
        from ..pd_annotation_line import PDAnnotationLine

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationLine):
            return
        rect = annotation.get_rectangle()
        if rect is None:
            return
        paths_array = annotation.get_line()
        if paths_array is None:
            return
        ab = AnnotationBorder.get_annotation_border(
            annotation, annotation.get_border_style()
        )
        stroke_components = self._color_components_from_annotation(annotation)
        if stroke_components is None:
            return
        ll = annotation.get_leader_line_length()
        lle = annotation.get_leader_line_extension_length()
        llo = annotation.get_leader_line_offset_length()

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
        if ll < 0:
            llo = -llo
            lle = -lle
        # Treat very thin widths as 1 for line endings, see java line 99.
        line_ending_size = 1.0 if ab.width < 1e-5 else ab.width
        padding = max(line_ending_size * 10, abs(llo + ll + lle))
        rect.set_lower_left_x(min(min_x - padding, rect.get_lower_left_x()))
        rect.set_lower_left_y(min(min_y - padding, rect.get_lower_left_y()))
        rect.set_upper_right_x(max(max_x + padding, rect.get_upper_right_x()))
        rect.set_upper_right_y(max(max_y + padding, rect.get_upper_right_y()))
        annotation.set_rectangle(rect)

        with self.get_normal_appearance_as_content_stream() as cs:
            self.set_opacity(cs, annotation.get_constant_opacity())
            cs.set_stroking_color(stroke_components)
            has_stroke = True
            if ab.dash_array is not None:
                cs.set_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)

            x1 = paths_array[0]
            y1 = paths_array[1]
            x2 = paths_array[2]
            y2 = paths_array[3]
            y = llo + ll

            cs.save_graphics_state()
            angle = math.atan2(y2 - y1, x2 - x1)
            # rotate around (x1, y1)
            ca = math.cos(angle)
            sa = math.sin(angle)
            cs.transform(
                ca, sa,
                -sa, ca,
                x1 - x1 * ca + y1 * sa,
                y1 - x1 * sa - y1 * ca,
            )
            line_length = math.hypot(x2 - x1, y2 - y1)
            # Leader lines
            cs.move_to(0.0, llo)
            cs.line_to(0.0, llo + ll + lle)
            cs.move_to(line_length, llo)
            cs.line_to(line_length, llo + ll + lle)

            start_style = annotation.get_start_point_ending_style()
            end_style = annotation.get_end_point_ending_style()

            contents = annotation.get_contents() or ""
            has_caption = (
                getattr(annotation, "has_caption", lambda: False)()
                and bool(contents)
            )

            if has_caption:
                font = self.get_default_font()
                content_length = 0.0
                try:
                    content_length = (
                        font.get_string_width(contents) / 1000 * _FONT_SIZE
                    )
                except (AttributeError, ValueError, KeyError):
                    # Adobe Reader shows placeholders; we fall back to a
                    # monospace estimate so the line geometry still
                    # accounts for the caption width.
                    content_length = len(contents) * _FONT_SIZE * 0.5

                x_offset = (line_length - content_length) / 2
                caption_positioning = getattr(
                    annotation, "get_caption_positioning", lambda: ""
                )()

                if start_style in self.SHORT_STYLES:
                    cs.move_to(line_ending_size, y)
                else:
                    cs.move_to(0.0, y)

                if caption_positioning == "Top":
                    # Adobe-derived offset constant from upstream.
                    y_offset = 1.908
                else:
                    # Inline caption — Adobe-derived offset.
                    y_offset = -2.6
                    cs.line_to(x_offset - line_ending_size, y)
                    cs.move_to(line_length - x_offset + line_ending_size, y)

                if end_style in self.SHORT_STYLES:
                    cs.line_to(line_length - line_ending_size, y)
                else:
                    cs.line_to(line_length, y)
                cs.draw_shape(line_ending_size, has_stroke, False)

                caption_h = getattr(
                    annotation, "get_caption_horizontal_offset", lambda: 0.0
                )()
                caption_v = getattr(
                    annotation, "get_caption_vertical_offset", lambda: 0.0
                )()
                if content_length > 0:
                    try:
                        cs.begin_text()
                    except (AttributeError, ValueError):
                        # Stream doesn't support text operators at all —
                        # nothing was opened, so nothing to close.
                        pass
                    else:
                        # Inside a BT block now: ``end_text`` has to run
                        # in the ``finally`` so the subsequent
                        # ``restore_graphics_state`` isn't inside a
                        # text block (which would raise RuntimeError).
                        try:
                            cs.set_font(font, _FONT_SIZE)
                            cs.new_line_at_offset(
                                x_offset + caption_h,
                                y + y_offset + caption_v,
                            )
                            cs.show_text(contents)
                        except (AttributeError, ValueError):
                            # Font without show_text support — skip the
                            # text emit but still close BT.
                            pass
                        finally:
                            cs.end_text()

                if caption_v != 0:
                    # Adobe paints a vertical bar to the caption.
                    cs.move_to(line_length / 2, y)
                    cs.line_to(line_length / 2, y + caption_v)
                    cs.draw_shape(line_ending_size, has_stroke, False)
            else:
                if start_style in self.SHORT_STYLES:
                    cs.move_to(line_ending_size, y)
                else:
                    cs.move_to(0.0, y)
                if end_style in self.SHORT_STYLES:
                    cs.line_to(line_length - line_ending_size, y)
                else:
                    cs.line_to(line_length, y)
                cs.draw_shape(line_ending_size, has_stroke, False)
            cs.restore_graphics_state()

            interior_components = self._interior_components(annotation)
            has_background = interior_components is not None
            if has_background:
                cs.set_non_stroking_color(interior_components)
            if ab.width < 1e-5:
                has_stroke = False

            if start_style != PDAnnotationLine.LE_NONE:
                cs.save_graphics_state()
                if start_style in self.ANGLED_STYLES:
                    cs.transform(
                        ca, sa, -sa, ca,
                        x1 - x1 * ca + y1 * sa,
                        y1 - x1 * sa - y1 * ca,
                    )
                    self.draw_style(
                        start_style, cs, 0.0, y, line_ending_size,
                        has_stroke, has_background, False,
                    )
                else:
                    xx1 = x1 - y * math.sin(angle)
                    yy1 = y1 + y * math.cos(angle)
                    self.draw_style(
                        start_style, cs, xx1, yy1, line_ending_size,
                        has_stroke, has_background, False,
                    )
                cs.restore_graphics_state()

            if end_style != PDAnnotationLine.LE_NONE:
                if end_style in self.ANGLED_STYLES:
                    cs.transform(
                        ca, sa, -sa, ca,
                        x2 - x2 * ca + y2 * sa,
                        y2 - x2 * sa - y2 * ca,
                    )
                    self.draw_style(
                        end_style, cs, 0.0, y, line_ending_size,
                        has_stroke, has_background, True,
                    )
                else:
                    xx2 = x2 - y * math.sin(angle)
                    yy2 = y2 + y * math.cos(angle)
                    self.draw_style(
                        end_style, cs, xx2, yy2, line_ending_size,
                        has_stroke, has_background, True,
                    )

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance generated (PDLineAppearanceHandler.java:331).
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance generated (PDLineAppearanceHandler.java:337).
        return None

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


__all__ = ["PDLineAppearanceHandler"]
