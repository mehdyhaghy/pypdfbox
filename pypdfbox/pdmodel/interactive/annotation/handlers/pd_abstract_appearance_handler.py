from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pypdfbox.cos import COSName, COSStream

from ..pd_annotation_line import PDAnnotationLine
from ..pd_appearance_content_stream import PDAppearanceContentStream
from ..pd_appearance_dictionary import PDAppearanceDictionary
from ..pd_appearance_entry import PDAppearanceEntry
from ..pd_appearance_stream import PDAppearanceStream
from .pd_appearance_handler import PDAppearanceHandler

if TYPE_CHECKING:
    from pypdfbox.cos import COSArray

    from ....pd_document import PDDocument
    from ....pd_rectangle import PDRectangle
    from ..pd_annotation import PDAnnotation
    from ..pd_annotation_square_circle import PDAnnotationSquareCircle


_TYPE: COSName = COSName.get_pdf_name("Type")
_X_OBJECT: COSName = COSName.get_pdf_name("XObject")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_FORM: COSName = COSName.get_pdf_name("Form")
_FORM_TYPE: COSName = COSName.get_pdf_name("FormType")
_BBOX: COSName = COSName.get_pdf_name("BBox")


class PDAbstractAppearanceHandler(PDAppearanceHandler):
    """Generic base for annotation appearance handlers. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDAbstractAppearanceHandler``.

    Concrete subclasses implement ``generate_normal_appearance`` (and
    optionally rollover/down). The base provides the appearance-stream
    plumbing (allocate the Form XObject body, ensure ``/AP`` is wired,
    open a writer) plus a few small geometry helpers that get reused
    across handlers — line-ending shape primitives, rectangle padding,
    and a shared border-box helper for square/circle annotations.
    """

    #: Half-arrowhead angle in radians (Adobe matches roughly 30 degrees).
    #: Mirrors upstream ``ARROW_ANGLE`` (PDAbstractAppearanceHandler.java:61).
    ARROW_ANGLE: float = math.radians(30)

    @staticmethod
    def create_short_styles() -> frozenset[str]:
        """Build the immutable set of line-ending styles where the line
        has to be drawn shorter (minus line width). Mirrors upstream's
        private static ``createShortStyles`` (PDAbstractAppearanceHandler.java:436).
        """
        return frozenset(
            {
                PDAnnotationLine.LE_OPEN_ARROW,
                PDAnnotationLine.LE_CLOSED_ARROW,
                PDAnnotationLine.LE_SQUARE,
                PDAnnotationLine.LE_CIRCLE,
                PDAnnotationLine.LE_DIAMOND,
            }
        )

    @staticmethod
    def create_interior_color_styles() -> frozenset[str]:
        """Build the immutable set of line-ending styles where there is
        an interior color. Mirrors upstream's private static
        ``createInteriorColorStyles`` (PDAbstractAppearanceHandler.java:447).
        """
        return frozenset(
            {
                PDAnnotationLine.LE_CLOSED_ARROW,
                PDAnnotationLine.LE_CIRCLE,
                PDAnnotationLine.LE_DIAMOND,
                PDAnnotationLine.LE_R_CLOSED_ARROW,
                PDAnnotationLine.LE_SQUARE,
            }
        )

    @staticmethod
    def create_angled_styles() -> frozenset[str]:
        """Build the immutable set of line-ending styles where the shape
        changes its angle (e.g. arrows). Mirrors upstream's private static
        ``createAngledStyles`` (PDAbstractAppearanceHandler.java:458).
        """
        return frozenset(
            {
                PDAnnotationLine.LE_CLOSED_ARROW,
                PDAnnotationLine.LE_OPEN_ARROW,
                PDAnnotationLine.LE_R_CLOSED_ARROW,
                PDAnnotationLine.LE_R_OPEN_ARROW,
                PDAnnotationLine.LE_BUTT,
                PDAnnotationLine.LE_SLASH,
            }
        )

    #: Line ending styles where the line has to be drawn shorter
    #: (minus line width). Mirrors upstream ``SHORT_STYLES``.
    SHORT_STYLES: frozenset[str] = frozenset(
        {
            PDAnnotationLine.LE_OPEN_ARROW,
            PDAnnotationLine.LE_CLOSED_ARROW,
            PDAnnotationLine.LE_SQUARE,
            PDAnnotationLine.LE_CIRCLE,
            PDAnnotationLine.LE_DIAMOND,
        }
    )

    #: Line ending styles where there is an interior color. Mirrors
    #: upstream ``INTERIOR_COLOR_STYLES``.
    INTERIOR_COLOR_STYLES: frozenset[str] = frozenset(
        {
            PDAnnotationLine.LE_CLOSED_ARROW,
            PDAnnotationLine.LE_CIRCLE,
            PDAnnotationLine.LE_DIAMOND,
            PDAnnotationLine.LE_R_CLOSED_ARROW,
            PDAnnotationLine.LE_SQUARE,
        }
    )

    #: Line ending styles where the shape changes its angle, e.g. arrows.
    #: Mirrors upstream ``ANGLED_STYLES``.
    ANGLED_STYLES: frozenset[str] = frozenset(
        {
            PDAnnotationLine.LE_CLOSED_ARROW,
            PDAnnotationLine.LE_OPEN_ARROW,
            PDAnnotationLine.LE_R_CLOSED_ARROW,
            PDAnnotationLine.LE_R_OPEN_ARROW,
            PDAnnotationLine.LE_BUTT,
            PDAnnotationLine.LE_SLASH,
        }
    )

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        self._annotation = annotation
        self._document = document
        self._default_font: object | None = None  # PDFont, lazily built

    # ---------- accessors ----------

    def get_annotation(self) -> PDAnnotation:
        return self._annotation

    def get_document(self) -> PDDocument | None:
        return self._document

    def get_color(self) -> COSArray | None:
        """Return the annotation's stroke color (``/C``).

        Mirrors upstream ``PDAbstractAppearanceHandler.getColor()`` —
        package-private in Java; here it's exposed for parity since
        handlers live in the same package.

        Lite surface: this returns the raw ``COSArray`` of color
        components rather than a typed :class:`PDColor` because
        :meth:`PDAnnotation.get_color` itself does — the typed wrapper
        lands with the rendering cluster (PRD §6.12). See ``CHANGES.md``.
        """
        return self._annotation.get_color()

    def get_rectangle(self) -> PDRectangle | None:
        return self._annotation.get_rectangle()

    def get_default_font(self) -> object:
        """Return a lazily-constructed Helvetica :class:`PDType1Font` for
        appearance text. Mirrors upstream ``getDefaultFont()`` — used by
        text-bearing handlers (free-text, widget) that need *some* usable
        font without forcing the caller to build a font dictionary.

        Constructed via :meth:`PDFontFactory.create_default_font` so the
        font dictionary carries the right ``/Subtype`` and ``/BaseFont``
        for embedding-free Standard 14 use.
        """
        if self._default_font is None:
            from ....font.pd_font_factory import PDFontFactory

            self._default_font = PDFontFactory.create_default_font()
        return self._default_font

    # ---------- appearance allocation ----------

    def create_cos_stream(self) -> COSStream:
        """Allocate a fresh ``COSStream`` for an appearance body. Upstream
        routes through ``PDDocument.getDocument().createCOSStream()`` when
        a document is available so the new stream gets registered with
        the COSDocument; the lite port falls back to a bare ``COSStream``
        when ``document`` is ``None``."""
        if self._document is not None:
            cos_doc = self._document.get_document()
            create = getattr(cos_doc, "create_cos_stream", None)
            if callable(create):
                stream = create()
                if isinstance(stream, COSStream):
                    return stream
        return COSStream()

    def get_appearance(self) -> PDAppearanceDictionary:
        """Return the annotation's ``/AP`` dictionary, creating one if
        absent (and writing it back on the annotation). Mirrors upstream's
        ``getAppearance``."""
        existing = self._annotation.get_appearance_dictionary()
        if existing is not None:
            return existing
        ap = PDAppearanceDictionary()
        self._annotation.set_appearance_dictionary(ap)
        return ap

    def get_normal_appearance(self) -> PDAppearanceEntry:
        """Return the ``/AP /N`` appearance entry, creating a fresh single
        stream when ``/N`` is absent or is a state subdictionary.

        Mirrors upstream's private ``getNormalAppearance()`` (returns the
        entry, not the stream). Exposed in the port because helper
        callers in the same package use it.
        """
        appearance = self.get_appearance()
        normal_entry = appearance.get_normal_appearance()
        if normal_entry is None or normal_entry.is_sub_dictionary():
            new_entry = PDAppearanceEntry(self.create_cos_stream())
            appearance.set_normal_appearance(new_entry)
            return new_entry
        return normal_entry

    def get_normal_appearance_stream(self) -> PDAppearanceStream:
        """Return the (single-stream) ``/AP /N`` appearance, creating a
        fresh one when ``/N`` is absent or is a state subdictionary.

        The returned stream has ``/Type /XObject /Subtype /Form
        /FormType 1 /BBox <annotation rect>`` set so it is a valid Form
        XObject.
        """
        ap = self.get_appearance()
        entry = ap.get_normal_appearance()
        if entry is not None and entry.is_stream():
            stream = entry.get_appearance_stream()
            assert stream is not None
            return stream
        # Either /N is absent or it's a state subdictionary — replace it
        # with a fresh single-stream appearance.
        cos_stream = self.create_cos_stream()
        cos_stream.set_item(_TYPE, _X_OBJECT)
        cos_stream.set_item(_SUBTYPE, _FORM)
        cos_stream.set_int(_FORM_TYPE, 1)
        rect = self.get_rectangle()
        if rect is not None:
            cos_stream.set_item(_BBOX, rect.to_cos_array())
        appearance_stream = PDAppearanceStream(cos_stream)
        ap.set_normal_appearance(appearance_stream)
        return appearance_stream

    def get_normal_appearance_as_content_stream(
        self, compress: bool = False
    ) -> PDAppearanceContentStream:
        """Open a writer over the ``/AP /N`` appearance stream. Caller is
        responsible for ``close()`` (use ``with``).

        Mirrors upstream's overloaded ``getNormalAppearanceAsContentStream``
        (lines 143 / 159). Both Java overloads route through
        :meth:`get_appearance_entry_as_content_stream` after fetching the
        normal entry; we follow the same dispatch.
        """
        appearance_entry = self.get_normal_appearance()
        return self.get_appearance_entry_as_content_stream(
            appearance_entry, compress
        )

    def get_appearance_entry_as_content_stream(
        self,
        appearance_entry: PDAppearanceEntry,
        compress: bool = False,
    ) -> PDAppearanceContentStream:
        """Open a writer over an arbitrary appearance entry, applying the
        annotation's transformation matrix and seeding ``/Resources`` if
        absent.

        Mirrors upstream's private
        ``getAppearanceEntryAsContentStream(PDAppearanceEntry, boolean)``
        (PDAbstractAppearanceHandler.java:494). Java keeps it private; the
        Python port exposes it because handlers in the same package are
        free functions / methods rather than nested classes — direct
        package access does not exist.
        """
        appearance = appearance_entry.get_appearance_stream()
        if appearance is None:
            # Fall back to the always-allocated single-stream form when the
            # entry doesn't yet point at a real appearance stream.
            appearance = self.get_normal_appearance_stream()
        self.set_transformation_matrix(appearance)
        if appearance.get_resources() is None:
            from ....pd_resources import PDResources

            appearance.set_resources(PDResources())
        return PDAppearanceContentStream(appearance, compress=compress)

    def get_down_appearance(self) -> PDAppearanceEntry:
        """Return the ``/AP /D`` appearance entry, creating a fresh single
        stream when ``/D`` is a state subdictionary. Mirrors upstream's
        ``getDownAppearance()``.
        """
        appearance = self.get_appearance()
        down = appearance.get_down_appearance()
        if down is None or down.is_sub_dictionary():
            new_entry = PDAppearanceEntry(self.create_cos_stream())
            appearance.set_down_appearance(new_entry)
            return new_entry
        return down

    def get_rollover_appearance(self) -> PDAppearanceEntry:
        """Return the ``/AP /R`` appearance entry, creating a fresh single
        stream when ``/R`` is a state subdictionary. Mirrors upstream's
        ``getRolloverAppearance()``.
        """
        appearance = self.get_appearance()
        rollover = appearance.get_rollover_appearance()
        if rollover is None or rollover.is_sub_dictionary():
            new_entry = PDAppearanceEntry(self.create_cos_stream())
            appearance.set_rollover_appearance(new_entry)
            return new_entry
        return rollover

    def set_transformation_matrix(
        self, appearance_stream: PDAppearanceStream
    ) -> None:
        """Set the appearance ``/BBox`` to the annotation rectangle and
        ``/Matrix`` to a translation that moves the rectangle's
        lower-left corner to the origin. Mirrors upstream's private
        ``setTransformationMatrix`` (PDAbstractAppearanceHandler.java:511).

        Java keeps this private; Python exposes it because helper callers
        in the same package — concrete handler subclasses, the parity
        tests — invoke it directly without going through reflection.
        """
        bbox = self.get_rectangle()
        if bbox is None:
            return
        appearance_stream.set_bbox(bbox)
        appearance_stream.set_matrix(
            [1.0, 0.0, 0.0, 1.0, -bbox.get_lower_left_x(), -bbox.get_lower_left_y()]
        )

    # Back-compat alias used by earlier-wave call sites and tests.
    _set_transformation_matrix = set_transformation_matrix

    # ---------- geometry helpers ----------

    @staticmethod
    def get_padded_rectangle(
        rectangle: PDRectangle, padding: float
    ) -> PDRectangle:
        from ....pd_rectangle import PDRectangle

        # Note: upstream constructs ``new PDRectangle(x, y, w, h)`` whose Java
        # 4-arg form is ``(x, y, width, height)``. The Python ``PDRectangle``
        # 4-arg constructor takes ``(lower_left_x, lower_left_y, upper_right_x,
        # upper_right_y)`` instead, so we use the explicit ``from_xywh``
        # factory to get the same semantics as upstream.
        return PDRectangle.from_xywh(
            rectangle.get_lower_left_x() + padding,
            rectangle.get_lower_left_y() + padding,
            rectangle.get_width() - 2 * padding,
            rectangle.get_height() - 2 * padding,
        )

    @staticmethod
    def add_rect_differences(
        rectangle: PDRectangle, differences: list[float] | None
    ) -> PDRectangle:
        if differences is None or len(differences) != 4:
            return rectangle
        from ....pd_rectangle import PDRectangle

        return PDRectangle.from_xywh(
            rectangle.get_lower_left_x() - differences[0],
            rectangle.get_lower_left_y() - differences[1],
            rectangle.get_width() + differences[0] + differences[2],
            rectangle.get_height() + differences[1] + differences[3],
        )

    @staticmethod
    def apply_rect_differences(
        rectangle: PDRectangle, differences: list[float] | None
    ) -> PDRectangle:
        if differences is None or len(differences) != 4:
            return rectangle
        from ....pd_rectangle import PDRectangle

        return PDRectangle.from_xywh(
            rectangle.get_lower_left_x() + differences[0],
            rectangle.get_lower_left_y() + differences[1],
            rectangle.get_width() - differences[0] - differences[2],
            rectangle.get_height() - differences[1] - differences[3],
        )

    def handle_border_box(
        self,
        annotation: PDAnnotationSquareCircle,
        line_width: float,
    ) -> PDRectangle:
        """Compute the border box for a square / circle annotation.

        Mirrors upstream's ``handleBorderBox(PDAnnotationSquareCircle,
        float)`` — implementation-specific to Adobe Reader, not part of
        the PDF specification:

        * If ``/RD`` is unset, the border box is the ``/Rect`` entry inset
          by half the line width. ``/RD`` is then seeded with the line
          width and ``/Rect`` is enlarged by the new ``/RD`` so the
          appearance bbox/matrix stay in sync.
        * If ``/RD`` is set, the border box is the ``/Rect`` with ``/RD``
          applied per side, then padded inward by half the line width.
        """
        rect_differences = annotation.get_rect_differences()
        if not rect_differences:
            border_box = self.get_padded_rectangle(
                self.get_rectangle(), line_width / 2
            )
            annotation.set_rect_differences(line_width / 2)
            annotation.set_rectangle(
                self.add_rect_differences(
                    self.get_rectangle(), annotation.get_rect_differences()
                )
            )
            # When the normal appearance stream was generated, BBox/Matrix
            # were set to the values of the original /Rect. Since /Rect
            # changed, adjust them too.
            rect = self.get_rectangle()
            appearance_stream = annotation.get_normal_appearance_stream()
            if appearance_stream is not None and rect is not None:
                appearance_stream.set_bbox(rect)
                appearance_stream.set_matrix(
                    [
                        1.0,
                        0.0,
                        0.0,
                        1.0,
                        -rect.get_lower_left_x(),
                        -rect.get_lower_left_y(),
                    ]
                )
            return border_box
        border_box = self.apply_rect_differences(
            self.get_rectangle(), rect_differences
        )
        return self.get_padded_rectangle(border_box, line_width / 2)

    # ---------- opacity / extended graphics state ----------

    @staticmethod
    def set_opacity(
        content_stream: PDAppearanceContentStream, opacity: float
    ) -> None:
        """Apply a constant stroking + non-stroking alpha via an
        ``/ExtGState``. No-op when ``opacity`` is ``>= 1`` (matches
        upstream behaviour).

        Mirrors upstream's package-private ``setOpacity`` — exposed here
        for handlers in the same package.
        """
        if opacity >= 1:
            return
        from ....graphics.state.pd_extended_graphics_state import (
            PDExtendedGraphicsState,
        )

        gs = PDExtendedGraphicsState()
        gs.set_stroking_alpha_constant(opacity)
        gs.set_non_stroking_alpha_constant(opacity)
        content_stream.set_graphics_state_parameters(gs)

    # ---------- line-ending shape primitives ----------

    def draw_style(
        self,
        style: str,
        cs: PDAppearanceContentStream,
        x: float,
        y: float,
        width: float,
        has_stroke: bool,
        has_background: bool,
        ending: bool,
    ) -> None:
        """Emit the path for a line-ending style at ``(x, y)``.

        Mirrors upstream's ``drawStyle``. ``ending`` is ``False`` for the
        left side of an imagined horizontal line, ``True`` for the
        right side (important for arrow direction).
        """
        sign = -1 if ending else 1
        if style in (
            PDAnnotationLine.LE_OPEN_ARROW,
            PDAnnotationLine.LE_CLOSED_ARROW,
        ):
            self.draw_arrow(cs, x + sign * width, y, sign * width * 9)
        elif style == PDAnnotationLine.LE_BUTT:
            cs.move_to(x, y - width * 3)
            cs.line_to(x, y + width * 3)
        elif style == PDAnnotationLine.LE_DIAMOND:
            self.draw_diamond(cs, x, y, width * 3)
        elif style == PDAnnotationLine.LE_SQUARE:
            cs.add_rect(x - width * 3, y - width * 3, width * 6, width * 6)
        elif style == PDAnnotationLine.LE_CIRCLE:
            self.draw_circle(cs, x, y, width * 3)
        elif style in (
            PDAnnotationLine.LE_R_OPEN_ARROW,
            PDAnnotationLine.LE_R_CLOSED_ARROW,
        ):
            self.draw_arrow(cs, x + (-sign) * width, y, (-sign) * width * 9)
        elif style == PDAnnotationLine.LE_SLASH:
            width9 = width * 9
            # 18 x linewidth at an angle of 60 degrees
            cs.move_to(
                x + math.cos(math.radians(60)) * width9,
                y + math.sin(math.radians(60)) * width9,
            )
            cs.line_to(
                x + math.cos(math.radians(240)) * width9,
                y + math.sin(math.radians(240)) * width9,
            )
        else:
            return
        if style in (
            PDAnnotationLine.LE_R_CLOSED_ARROW,
            PDAnnotationLine.LE_CLOSED_ARROW,
        ):
            cs.close_path()
        # Only paint a background color (/IC) for interior-color styles,
        # even when /IC is set.
        cs.draw_shape(
            width,
            has_stroke,
            style in self.INTERIOR_COLOR_STYLES and has_background,
        )

    def draw_arrow(
        self,
        cs: PDAppearanceContentStream,
        x: float,
        y: float,
        length: float,
    ) -> None:
        """Add the two arms of a horizontal arrow to the path. Positive
        ``length`` extends to the right, negative to the left. Mirrors
        upstream ``drawArrow``.
        """
        # angle 30 degrees, arm length = 9 * line width
        arm_x = x + math.cos(self.ARROW_ANGLE) * length
        arm_y_delta = math.sin(self.ARROW_ANGLE) * length
        cs.move_to(arm_x, y + arm_y_delta)
        cs.line_to(x, y)
        cs.line_to(arm_x, y - arm_y_delta)

    def draw_diamond(
        self,
        cs: PDAppearanceContentStream,
        x: float,
        y: float,
        r: float,
    ) -> None:
        """Add a square diamond shape (corner on top) to the path. ``r``
        is the radius to a corner. Mirrors upstream ``drawDiamond``.
        """
        cs.move_to(x - r, y)
        cs.line_to(x, y + r)
        cs.line_to(x + r, y)
        cs.line_to(x, y - r)
        cs.close_path()

    def draw_circle(
        self,
        cs: PDAppearanceContentStream,
        x: float,
        y: float,
        r: float,
    ) -> None:
        """Add a circle to the path in clockwise direction. Mirrors
        upstream ``drawCircle`` — uses the well-known Bezier
        ``0.551784`` control offset (http://stackoverflow.com/a/2007782).
        """
        magic = r * 0.551784
        cs.move_to(x, y + r)
        cs.curve_to(x + magic, y + r, x + r, y + magic, x + r, y)
        cs.curve_to(x + r, y - magic, x + magic, y - r, x, y - r)
        cs.curve_to(x - magic, y - r, x - r, y - magic, x - r, y)
        cs.curve_to(x - r, y + magic, x - magic, y + r, x, y + r)
        cs.close_path()

    def draw_circle2(
        self,
        cs: PDAppearanceContentStream,
        x: float,
        y: float,
        r: float,
    ) -> None:
        """Add a circle to the path in counterclockwise direction —
        useful for doughnut shapes (nonzero winding). Mirrors upstream
        ``drawCircle2``.
        """
        magic = r * 0.551784
        cs.move_to(x, y + r)
        cs.curve_to(x - magic, y + r, x - r, y + magic, x - r, y)
        cs.curve_to(x - r, y - magic, x - magic, y - r, x, y - r)
        cs.curve_to(x + magic, y - r, x + r, y - magic, x + r, y)
        cs.curve_to(x + r, y + magic, x + magic, y + r, x, y + r)
        cs.close_path()

    # ---------- color helper ----------

    @staticmethod
    def _color_components_from_annotation(
        annotation: PDAnnotation,
    ) -> list[float] | None:
        """Read /C off the annotation as raw float components. Returns
        ``None`` when /C is absent or empty.

        Note: ``PDAnnotation.get_color()`` in the lite surface still
        returns the raw ``COSArray`` rather than a typed :class:`PDColor`.
        See ``CHANGES.md``.
        """
        color = annotation.get_color()
        if color is None or color.size() == 0:
            return None
        return color.to_float_array()

    @staticmethod
    def _pd_color_from_components(components: list[float]):  # type: ignore[no-untyped-def]
        """Wrap raw ``/C`` float components in a :class:`PDColor` carrying the
        device color space implied by the component count (1 → DeviceGray,
        3 → DeviceRGB, 4 → DeviceCMYK).

        Upstream handlers pass the full ``PDColor`` returned by ``getColor()``
        to ``cs.setStrokingColor`` / ``setNonStrokingColor`` so the appearance
        stream emits ``/DeviceRGB CS <r> <g> <b> SC`` (color-space name +
        ``CS`` + components + ``SC``), never the device-shorthand ``RG`` / ``G``
        / ``K`` operators. A bare component list routes through the shorthand
        path and diverges byte-for-byte from PDFBox, so handlers that mirror an
        upstream ``setStrokingColor(getColor())`` call must wrap first.
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

    @staticmethod
    def _components_to_rgb(components: list[float]) -> tuple[float, float, float]:
        """Best-effort conversion of /C components to RGB. The annotation
        ``/C`` array uses DeviceGray (1), DeviceRGB (3), or DeviceCMYK (4)
        per PDF 32000-1:2008 §12.5.3."""
        if len(components) == 1:
            g = max(0.0, min(1.0, float(components[0])))
            return (g, g, g)
        if len(components) >= 3 and len(components) != 4:
            return (
                max(0.0, min(1.0, float(components[0]))),
                max(0.0, min(1.0, float(components[1]))),
                max(0.0, min(1.0, float(components[2]))),
            )
        if len(components) == 4:
            c, m, y, k = (float(v) for v in components[:4])
            r = (1.0 - c) * (1.0 - k)
            g = (1.0 - m) * (1.0 - k)
            b = (1.0 - y) * (1.0 - k)
            return (
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
            )
        return (0.0, 0.0, 0.0)

    # ---------- default no-ops ----------

    def generate_normal_appearance(self) -> None:  # pragma: no cover - abstract default
        return None

    def generate_rollover_appearance(self) -> None:
        # Most upstream subclasses no-op rollover.
        return None

    def generate_down_appearance(self) -> None:
        # Most upstream subclasses no-op down.
        return None


__all__ = ["PDAbstractAppearanceHandler"]
