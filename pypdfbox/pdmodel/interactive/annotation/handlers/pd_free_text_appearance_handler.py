from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.cos import COSArray, COSBase, COSName
from pypdfbox.cos.cos_number import COSNumber
from pypdfbox.pdfparser.pdf_stream_parser import Operator

from .annotation_border import AnnotationBorder
from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation
    from ..pd_annotation_free_text import PDAnnotationFreeText


_COLOR_PATTERN = re.compile(r"color:\s*+#([0-9a-fA-F]{6})")


def _apply_matrix(cs: Any, matrix: Any) -> None:
    """Emit the ``cm`` operator with the six components of ``matrix``.

    The runtime ``PDAppearanceContentStream.transform`` method
    (inherited from :class:`PDPageContentStream`) takes six explicit
    floats rather than a :class:`Matrix` instance, whereas upstream's
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


class PDFreeTextAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a free-text annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDFreeTextAppearanceHandler``.

    Ports the full upstream flow: ``/DA`` parsing for font + non-stroking
    color, ``/DS`` parsing for the CSS ``color:`` override, callout line
    + line-ending styles, the rectangle / border-effect interplay and a
    text-rendering pass that emits the ``/Contents`` string inside a
    clip box. A few upstream-specific behaviours are deviated from
    (documented in ``CHANGES.md``):

    * Cloudy borders fall back to the regular straight-edged rectangle
      until :class:`CloudyBorder` is wired into the FreeText path.

    The text-layout pass routes ``/Contents`` through the ported
    :class:`PlainTextFormatter` and the *annotation-layout*
    :class:`PlainText`
    (``pypdfbox.pdmodel.interactive.annotation.layout``), word-wrapping to
    the clip width exactly as upstream's FreeText handler does (which uses
    the ``annotation.layout`` variant, **not** the AcroForm one), so the
    ``Td``/``Tj`` run cadence matches Apache PDFBox.
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

    def generate_normal_appearance(self) -> None:  # noqa: C901, PLR0915
        """Mirrors upstream ``generateNormalAppearance``
        (PDFreeTextAppearanceHandler.java:72)."""
        from ..pd_annotation_free_text import PDAnnotationFreeText
        from ..pd_annotation_line import PDAnnotationLine

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationFreeText):
            return

        # Resolve /CL (callout) when /IT is FreeTextCallout, else empty.
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
            # Adobe uses the last non-stroking color from /DA as the
            # stroking color. Default is DeviceGray 0 (black) when /DA
            # is absent or doesn't carry a non-stroking color op.
            stroke_components = self.extract_non_stroking_color(annotation)
            text_components = list(stroke_components)
            has_stroke = stroke_components is not None

            # /DS color override — CSS-ish "color: #rrggbb".
            default_style = annotation.get_default_style_string()
            if isinstance(default_style, str):
                match = _COLOR_PATTERN.search(default_style)
                if match is not None:
                    color_int = int(match.group(1), 16)
                    text_components = [
                        ((color_int >> 16) & 0xFF) / 255,
                        ((color_int >> 8) & 0xFF) / 255,
                        (color_int & 0xFF) / 255,
                    ]

            if has_stroke:  # pragma: no branch - extract_non_stroking_color never returns None
                cs.set_stroking_color(stroke_components)
            if ab.dash_array is not None:
                cs.set_line_dash_pattern(list(ab.dash_array), 0)
            cs.set_line_width(ab.width)

            line_ending_style = annotation.get_line_ending_style()

            # Draw callout lines first so the box paint doesn't cover them.
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
                        length = math.hypot(x - x1, y - y1)
                        if length != 0:
                            x += (x1 - x) / length * ab.width
                            y += (y1 - y) / length * ab.width
                    cs.move_to(x, y)
                else:
                    cs.line_to(x, y)
            if paths_array:
                cs.stroke()

            # Paint the line-ending style at the start of the callout.
            if (
                annotation.get_intent() == PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT
                and line_ending_style != PDAnnotationLine.LE_NONE
                and len(paths_array) >= 4
            ):
                from pypdfbox.util.matrix import Matrix

                x2 = paths_array[2]
                y2 = paths_array[3]
                x1 = paths_array[0]
                y1 = paths_array[1]
                cs.save_graphics_state()
                if line_ending_style in self.ANGLED_STYLES:
                    angle = math.atan2(y2 - y1, x2 - x1)
                    _apply_matrix(cs, Matrix.get_rotate_instance(angle, x1, y1))
                else:
                    _apply_matrix(cs, Matrix.get_translate_instance(x1, y1))
                self.draw_style(
                    line_ending_style,
                    cs,
                    0.0,
                    0.0,
                    ab.width,
                    has_stroke,
                    has_background,
                    False,
                )
                cs.restore_graphics_state()

            # Compute the border box. Documented deviation: cloudy borders
            # are not yet wired through for FreeText; we always emit the
            # plain rectangle.
            border_box = self.apply_rect_differences(
                self.get_rectangle(), annotation.get_rect_differences()
            )
            normal_stream = annotation.get_normal_appearance_stream()
            if normal_stream is not None:
                normal_stream.set_bbox(border_box)
            padded_rectangle = self.get_padded_rectangle(border_box, ab.width / 2)
            cs.add_rect(
                padded_rectangle.get_lower_left_x(),
                padded_rectangle.get_lower_left_y(),
                padded_rectangle.get_width(),
                padded_rectangle.get_height(),
            )
            cs.draw_shape(ab.width, has_stroke, has_background)

            # /Rotate transform. Upstream emits this unconditionally
            # (PDFreeTextAppearanceHandler.java) — when /Rotate is absent or
            # 0 the matrix is the identity, but the ``cm`` operator is still
            # written, so the appearance op-sequence carries it regardless.
            from pypdfbox.util.matrix import Matrix

            rotation = annotation.get_cos_object().get_int("Rotate", 0)
            _apply_matrix(
                cs, Matrix.get_rotate_instance(math.radians(rotation), 0.0, 0.0)
            )

            # Resolve the font from /DA + AcroForm default resources.
            self.extract_font_details(annotation)
            font = self._resolve_font()
            if font is None:
                return

            # Text layout offsets.
            y_delta = 0.7896  # upstream's empirical font ascender ratio.
            width_ref = (
                border_box.get_height()
                if rotation in (90, 270)
                else border_box.get_width()
            )
            clip_width = width_ref - ab.width * 4
            clip_height = (
                border_box.get_width() - ab.width * 4
                if rotation in (90, 270)
                else border_box.get_height() - ab.width * 4
            )
            if rotation == 180:
                x_offset = -border_box.get_upper_right_x() + ab.width * 2
                y_offset = (
                    -border_box.get_lower_left_y()
                    - ab.width * 2
                    - y_delta * self._font_size
                )
                clip_y = -border_box.get_upper_right_y() + ab.width * 2
            elif rotation == 90:
                x_offset = border_box.get_lower_left_y() + ab.width * 2
                y_offset = (
                    -border_box.get_lower_left_x()
                    - ab.width * 2
                    - y_delta * self._font_size
                )
                clip_y = -border_box.get_upper_right_x() + ab.width * 2
            elif rotation == 270:
                x_offset = -border_box.get_upper_right_y() + ab.width * 2
                y_offset = (
                    border_box.get_upper_right_x()
                    - ab.width * 2
                    - y_delta * self._font_size
                )
                clip_y = border_box.get_lower_left_x() + ab.width * 2
            else:
                x_offset = border_box.get_lower_left_x() + ab.width * 2
                y_offset = (
                    border_box.get_upper_right_y()
                    - ab.width * 2
                    - y_delta * self._font_size
                )
                clip_y = border_box.get_lower_left_y() + ab.width * 2

            # Clip the writing area.
            cs.add_rect(x_offset, clip_y, clip_width, clip_height)
            cs.clip()

            contents = annotation.get_contents()
            if contents is not None:
                cs.begin_text()
                cs.set_font(font, self._font_size)
                if text_components:
                    cs.set_non_stroking_color(text_components)
                # Word-wrap /Contents into width via the ported
                # PlainTextFormatter, matching upstream's
                # generateNormalAppearance (PDFreeTextAppearanceHandler.java:299).
                # Adobe ignores the annotation's /Q, so no textAlign is set
                # (the formatter defaults to LEFT).
                from ..layout import (  # noqa: PLC0415
                    AppearanceStyle,
                    PlainText,
                    PlainTextFormatter,
                )

                appearance_style = AppearanceStyle()
                appearance_style.set_font(font)
                appearance_style.set_font_size(self._font_size)
                formatter = (
                    PlainTextFormatter.Builder(cs)
                    .style(appearance_style)
                    .text(PlainText(contents))
                    .width(clip_width)
                    .wrap_lines(True)
                    .initial_offset(x_offset, y_offset)
                    .build()
                )
                try:
                    formatter.format()
                finally:
                    cs.end_text()

            # If a callout is present, grow the annotation /Rect so it
            # encloses the painted callout polyline as well.
            if paths_array:
                rect = self.get_rectangle()
                if rect is not None:
                    min_x = min(paths_array[i * 2] for i in range(len(paths_array) // 2))
                    min_y = min(
                        paths_array[i * 2 + 1] for i in range(len(paths_array) // 2)
                    )
                    max_x = max(paths_array[i * 2] for i in range(len(paths_array) // 2))
                    max_y = max(
                        paths_array[i * 2 + 1] for i in range(len(paths_array) // 2)
                    )
                    rect.set_lower_left_x(
                        min(min_x - ab.width * 10, rect.get_lower_left_x())
                    )
                    rect.set_lower_left_y(
                        min(min_y - ab.width * 10, rect.get_lower_left_y())
                    )
                    rect.set_upper_right_x(
                        max(max_x + ab.width * 10, rect.get_upper_right_x())
                    )
                    rect.set_upper_right_y(
                        max(max_y + ab.width * 10, rect.get_upper_right_y())
                    )
                    annotation.set_rectangle(rect)
                    if normal_stream is not None:
                        normal_stream.set_bbox(rect)

    # ------------------------------------------------------------------
    # /DA parsing helpers — ported from upstream extractNonStrokingColor
    # and extractFontDetails (PDFreeTextAppearanceHandler.java:367, 435).
    # ------------------------------------------------------------------

    def extract_non_stroking_color(
        self, annotation: PDAnnotationFreeText
    ) -> list[float]:
        """Mirror upstream's ``extractNonStrokingColor``
        (PDFreeTextAppearanceHandler.java:367) — pulls the last
        non-stroking color op out of the ``/DA`` default appearance
        string. Returns a list of components (length 1/3/4)."""
        default_appearance = annotation.get_default_appearance()
        if default_appearance is None:
            return [0.0]  # DeviceGray 0 = black, matching upstream default.

        graphic_op, colors = self._scan_da(default_appearance)
        if graphic_op is None or colors is None:
            return [0.0]
        return colors

    # Backwards-compatible private-name alias.
    _extract_non_stroking_color = extract_non_stroking_color

    def extract_font_details(self, annotation: PDAnnotationFreeText) -> None:
        """Mirror upstream's ``extractFontDetails``
        (PDFreeTextAppearanceHandler.java:435) — sets ``_font_name`` and
        ``_font_size`` from the first ``Tf`` operator in ``/DA``. When
        the annotation has no ``/DA``, falls back to the AcroForm
        default appearance."""
        default_appearance = annotation.get_default_appearance()
        if default_appearance is None and self._document is not None:
            catalog = self._document.get_document_catalog()
            acro_form = catalog.get_acro_form() if catalog is not None else None
            if acro_form is not None:
                getter = getattr(acro_form, "get_default_appearance", None)
                if callable(getter):
                    default_appearance = getter()
        if default_appearance is None:
            self._font_size = self.DEFAULT_FONT_SIZE
            self._font_name = self.DEFAULT_FONT_NAME
            return

        font_arguments = self._scan_da_for_font(default_appearance)
        if font_arguments is not None and len(font_arguments) >= 2:
            base = font_arguments[0]
            if isinstance(base, COSName):
                self._font_name = base
            base = font_arguments[1]
            if isinstance(base, COSNumber):
                self._font_size = base.float_value()

    # Backwards-compatible private-name alias.
    _extract_font_details = extract_font_details

    def _scan_da(self, default_appearance: str) -> tuple[Operator | None, list[float] | None]:
        """Scan the ``/DA`` token stream for the last non-stroking color
        op and its argument array. Returns ``(op, components)`` or
        ``(None, None)`` when no color op is found."""
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
        from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser

        try:
            parser = PDFStreamParser(
                RandomAccessReadBuffer(default_appearance.encode("ascii", "replace"))
            )
        except Exception:  # noqa: BLE001
            return None, None

        arguments: list[Any] = []
        last_op: Operator | None = None
        last_colors: list[float] | None = None
        try:
            while True:
                token = parser.parse_next_token()
                if token is None:
                    break
                if isinstance(token, Operator):
                    name = token.get_name()
                    if name in (
                        OperatorName.NON_STROKING_GRAY,
                        OperatorName.NON_STROKING_RGB,
                        OperatorName.NON_STROKING_CMYK,
                    ):
                        last_op = token
                        last_colors = [
                            float(a.float_value()) if isinstance(a, COSNumber) else 0.0
                            for a in arguments
                        ]
                    arguments = []
                else:
                    arguments.append(token)
        except Exception:  # noqa: BLE001
            return last_op, last_colors
        return last_op, last_colors

    def _scan_da_for_font(self, default_appearance: str) -> list[COSBase] | None:
        """Scan the ``/DA`` token stream for the first ``Tf`` operator
        and return its argument list."""
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
        from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser

        try:
            parser = PDFStreamParser(
                RandomAccessReadBuffer(default_appearance.encode("ascii", "replace"))
            )
        except Exception:  # noqa: BLE001
            return None

        arguments: list[COSBase] = []
        font_arguments: list[COSBase] | None = None
        try:
            while True:
                token = parser.parse_next_token()
                if token is None:
                    break
                if isinstance(token, Operator):
                    if token.get_name() == OperatorName.SET_FONT_AND_SIZE:
                        font_arguments = arguments
                    arguments = []
                else:
                    arguments.append(token)
        except Exception:  # noqa: BLE001
            return font_arguments
        return font_arguments

    def _resolve_font(self) -> Any:
        """Resolve the font from the AcroForm default resources (when a
        document is attached) or fall back to the default Helvetica."""
        if self._document is not None:
            catalog = self._document.get_document_catalog()
            acro_form = catalog.get_acro_form() if catalog is not None else None
            if acro_form is not None:
                resources_getter = getattr(acro_form, "get_default_resources", None)
                if callable(resources_getter):
                    default_resources = resources_getter()
                    if default_resources is not None:
                        font_getter = getattr(default_resources, "get_font", None)
                        if callable(font_getter):
                            try:
                                font = font_getter(self._font_name)
                            except Exception:  # noqa: BLE001
                                font = None
                            if font is not None:
                                # PDResources.get_font preserves the raw
                                # COSDictionary surface for DIRECT entries
                                # (legacy cluster #1 contract; upstream
                                # always wraps via PDFontFactory). The
                                # wave-1484 AcroForm default fixup injects
                                # /Helv as a direct entry, so wrap here
                                # before handing to set_font.
                                from pypdfbox.cos import (  # noqa: PLC0415
                                    COSDictionary,
                                )

                                if isinstance(font, COSDictionary):
                                    from pypdfbox.pdmodel.font import (  # noqa: PLC0415
                                        PDFontFactory,
                                    )

                                    font = PDFontFactory.create_font(font)
                                if font is not None:
                                    return font
        return self.get_default_font()

    def generate_rollover_appearance(self) -> None:
        # Upstream is an empty no-op (PDFreeTextAppearanceHandler.java:495).
        return None

    def generate_down_appearance(self) -> None:
        # Upstream is an empty no-op (PDFreeTextAppearanceHandler.java:501).
        return None


# Keep the unused-import shim explicit so ruff doesn't strip the COSArray
# import on next edit — we keep it available for callers that need it.
_KEEP_IMPORTS = (COSArray,)


__all__ = ["PDFreeTextAppearanceHandler"]
