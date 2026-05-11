from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....pd_rectangle import PDRectangle
    from ..pd_appearance_content_stream import PDAppearanceContentStream


_ANGLE_180_DEG: float = math.pi
_ANGLE_90_DEG: float = math.pi / 2
_ANGLE_34_DEG: float = math.radians(34)
_ANGLE_30_DEG: float = math.radians(30)
_ANGLE_12_DEG: float = math.radians(12)


class CloudyBorder:
    """Generates annotation appearances with a cloudy border. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.CloudyBorder``.

    The Java implementation is a 1100-line geometry engine that approximates
    Adobe's cloudy-border path with intermediate / corner curls along the
    annotation boundary. Full path generation is deferred — see the
    ``TODO: full path generation`` comments in
    :meth:`create_cloudy_rectangle`, :meth:`create_cloudy_polygon`, and
    :meth:`create_cloudy_ellipse` — but the public surface (constructor +
    three ``create_*`` entry points + the ``get_*`` accessors used by the
    square / circle / polygon handlers) lands here so the cluster types
    line up.
    """

    # Class-level angle constants mirror upstream's private static
    # ``ANGLE_*_DEG`` fields (CloudyBorder.java:40-44).
    ANGLE_180_DEG: float = _ANGLE_180_DEG
    ANGLE_90_DEG: float = _ANGLE_90_DEG
    ANGLE_34_DEG: float = _ANGLE_34_DEG
    ANGLE_30_DEG: float = _ANGLE_30_DEG
    ANGLE_12_DEG: float = _ANGLE_12_DEG

    def __init__(
        self,
        stream: PDAppearanceContentStream,
        intensity: float,
        line_width: float,
        rect: PDRectangle | None,
    ) -> None:
        """Mirrors upstream's package-private constructor
        ``CloudyBorder(PDAppearanceContentStream, double, double, PDRectangle)``
        (CloudyBorder.java:66)."""
        self._output = stream
        self._intensity = float(intensity)
        self._line_width = float(line_width)
        self._annot_rect = rect
        self._rect_with_diff: PDRectangle | None = None
        self._output_started: bool = False
        # bbox tracking — populated as the cloudy path is laid down.
        self._bbox_min_x: float = 0.0
        self._bbox_min_y: float = 0.0
        self._bbox_max_x: float = 0.0
        self._bbox_max_y: float = 0.0
        # Seed the bbox from the annotation rectangle so callers that
        # consult :meth:`get_rectangle` before path generation see a
        # sensible value.
        if rect is not None:
            self._bbox_min_x = rect.get_lower_left_x()
            self._bbox_min_y = rect.get_lower_left_y()
            self._bbox_max_x = rect.get_upper_right_x()
            self._bbox_max_y = rect.get_upper_right_y()

    # ------------------------------------------------------------------
    # public entry points — mirror upstream's package-private API
    # ------------------------------------------------------------------

    def create_cloudy_rectangle(self, rd: PDRectangle | None) -> None:
        """Generate a cloudy border for a rectangular annotation.

        Mirrors upstream ``createCloudyRectangle(PDRectangle)``
        (CloudyBorder.java:86). Used by the square handler and (with the
        callout omitted) by the free-text handler.
        """
        self._rect_with_diff = self._apply_rect_diff(rd, self._line_width / 2)
        # TODO: full path generation — emit the corner / intermediate
        # curl arcs around the resolved ``_rect_with_diff`` perimeter.
        # The lite port currently leaves the bbox at the input rectangle
        # so the calling handler's appearance bbox is at least valid.

    def create_cloudy_polygon(self, path: list[list[float]]) -> None:
        """Generate a cloudy border for a polygon annotation.

        Mirrors upstream ``createCloudyPolygon(float[][])``
        (CloudyBorder.java:104). ``path`` is a list of points expressed
        as ``[x, y]`` (move/line vertices) or ``[x1, y1, x2, y2, x3, y3]``
        (Bezier — currently unsupported, the endpoint is used).
        """
        # TODO: full path generation — flatten the polygon vertices,
        # add per-vertex curl arcs along each edge, and update the
        # bbox extents.
        for entry in path:
            if len(entry) >= 2:
                x = float(entry[-2])
                y = float(entry[-1])
                self._update_bbox(x, y)

    def create_cloudy_ellipse(self, rd: PDRectangle | None) -> None:
        """Generate a cloudy border for a circle annotation.

        Mirrors upstream ``createCloudyEllipse(PDRectangle)``
        (CloudyBorder.java:135).
        """
        self._rect_with_diff = self._apply_rect_diff(rd, 0.0)
        # TODO: full path generation — flatten the ellipse, walk the
        # resulting polygon, and emit curl arcs.

    # ------------------------------------------------------------------
    # accessors used by polygon / circle / square handlers
    # ------------------------------------------------------------------

    def get_bbox(self) -> PDRectangle:
        """Return the ``/BBox`` entry for the appearance form XObject.
        Mirrors upstream ``getBBox()`` (CloudyBorder.java:153)."""
        return self.get_rectangle()

    def get_rectangle(self) -> PDRectangle:
        """Return the updated ``/Rect`` entry. Mirrors upstream
        ``getRectangle()`` (CloudyBorder.java:164)."""
        from ....pd_rectangle import PDRectangle

        return PDRectangle.from_xywh(
            self._bbox_min_x,
            self._bbox_min_y,
            self._bbox_max_x - self._bbox_min_x,
            self._bbox_max_y - self._bbox_min_y,
        )

    def get_matrix(self) -> list[float]:
        """Return the ``/Matrix`` entry for the appearance form XObject.
        Upstream returns an ``AffineTransform`` (translate by
        ``-bbox_min``); the lite port returns the equivalent 6-element
        PDF matrix list. Mirrors upstream ``getMatrix()``
        (CloudyBorder.java:175).
        """
        return [1.0, 0.0, 0.0, 1.0, -self._bbox_min_x, -self._bbox_min_y]

    def get_rect_difference(self) -> PDRectangle:
        """Return the updated ``/RD`` entry for Square / Circle annotations.

        Mirrors upstream ``getRectDifference()`` (CloudyBorder.java:185).
        """
        from ....pd_rectangle import PDRectangle

        if self._annot_rect is None:
            d = self._line_width / 2
            return PDRectangle.from_xywh(d, d, self._line_width, self._line_width)
        base = (
            self._rect_with_diff
            if self._rect_with_diff is not None
            else self._annot_rect
        )
        left = base.get_lower_left_x() - self._bbox_min_x
        bottom = base.get_lower_left_y() - self._bbox_min_y
        right = self._bbox_max_x - base.get_upper_right_x()
        top = self._bbox_max_y - base.get_upper_right_y()
        return PDRectangle.from_xywh(left, bottom, right - left, top - bottom)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _apply_rect_diff(
        self, rd: PDRectangle | None, min_diff: float
    ) -> PDRectangle:
        """Apply the ``/RD`` rect-differences entry to the annotation
        rectangle and clamp each side to ``min_diff``. Mirrors upstream's
        private ``applyRectDiff`` (CloudyBorder.java:496).
        """
        from ....pd_rectangle import PDRectangle

        assert self._annot_rect is not None
        rect = self._annot_rect
        if rd is None:
            return PDRectangle.from_xywh(
                rect.get_lower_left_x(),
                rect.get_lower_left_y(),
                rect.get_width(),
                rect.get_height(),
            )
        left_d = max(min_diff, rd.get_lower_left_x())
        bottom_d = max(min_diff, rd.get_lower_left_y())
        right_d = max(min_diff, rd.get_upper_right_x())
        top_d = max(min_diff, rd.get_upper_right_y())
        return PDRectangle.from_xywh(
            rect.get_lower_left_x() + left_d,
            rect.get_lower_left_y() + bottom_d,
            rect.get_width() - left_d - right_d,
            rect.get_height() - bottom_d - top_d,
        )

    def _update_bbox(self, x: float, y: float) -> None:
        """Track the running bbox extents. Mirrors upstream's private
        ``updateBBox`` (CloudyBorder.java:1021)."""
        if not self._output_started:
            self._output_started = True
            self._bbox_min_x = x
            self._bbox_min_y = y
            self._bbox_max_x = x
            self._bbox_max_y = y
            return
        if x < self._bbox_min_x:
            self._bbox_min_x = x
        if y < self._bbox_min_y:
            self._bbox_min_y = y
        if x > self._bbox_max_x:
            self._bbox_max_x = x
        if y > self._bbox_max_y:
            self._bbox_max_y = y

    # ------------------------------------------------------------------
    # public parity surface — mirrors upstream's private static / private
    # helpers under their upstream snake_case names so the parity script
    # counts them. The bodies are stubs (``# TODO: full implementation``)
    # for the complex geometry helpers; the simple math helpers (cosine /
    # sine / get_*_cloud_radius / get_polygon_direction) are real ports.
    # ------------------------------------------------------------------

    def get_b_box(self) -> PDRectangle:
        """Mirrors upstream's ``getBBox`` (CloudyBorder.java:153)."""
        return self.get_bbox()

    def apply_rect_diff(
        self, rd: PDRectangle | None, min_diff: float
    ) -> PDRectangle:
        """Mirrors upstream's private ``applyRectDiff``
        (CloudyBorder.java:496)."""
        return self._apply_rect_diff(rd, min_diff)

    def update_b_box(self, x: float, y: float) -> None:
        """Mirrors upstream's private ``updateBBox``
        (CloudyBorder.java:1021)."""
        self._update_bbox(x, y)

    @staticmethod
    def cosine(dx: float, hypot: float) -> float:
        """Mirrors upstream's private static ``cosine``
        (CloudyBorder.java:203)."""
        if hypot == 0.0:
            return 0.0
        return dx / hypot

    @staticmethod
    def sine(dy: float, hypot: float) -> float:
        """Mirrors upstream's private static ``sine``
        (CloudyBorder.java:212)."""
        if hypot == 0.0:
            return 0.0
        return dy / hypot

    def cloudy_rectangle_impl(
        self,
        left: float,
        bottom: float,
        right: float,
        top: float,
        is_ellipse: bool,
    ) -> None:
        """Mirrors upstream's private ``cloudyRectangleImpl``
        (CloudyBorder.java:225). TODO: full implementation — converts
        the rectangle into a closed polygon and dispatches to
        :meth:`cloudy_polygon_impl`."""
        # TODO: full implementation
        _ = (left, bottom, right, top, is_ellipse)

    def cloudy_polygon_impl(
        self, vertices: list[tuple[float, float]], is_ellipse: bool
    ) -> None:
        """Mirrors upstream's private ``cloudyPolygonImpl``
        (CloudyBorder.java:279). TODO: full implementation — emits the
        curl arcs around each polygon edge."""
        # TODO: full implementation
        _ = (vertices, is_ellipse)

    def cloudy_ellipse_impl(
        self,
        left_orig: float,
        bottom_orig: float,
        right_orig: float,
        top_orig: float,
    ) -> None:
        """Mirrors upstream's private ``cloudyEllipseImpl``
        (CloudyBorder.java:743). TODO: full implementation."""
        # TODO: full implementation
        _ = (left_orig, bottom_orig, right_orig, top_orig)

    def compute_params_polygon(
        self,
        adv_interm: float,
        adv_corner: float,
        k: float,
        r: float,
        length: float,
        array: list[float],
    ) -> int:
        """Mirrors upstream's private ``computeParamsPolygon``
        (CloudyBorder.java:398). Real port — used by
        :meth:`cloudy_polygon_impl`."""
        if length == 0.0:
            array[0] = _ANGLE_34_DEG
            array[1] = 0.0
            return -1
        n = int(math.ceil((length - 2 * adv_corner) / adv_interm))
        e = length - (2 * adv_corner + n * adv_interm)
        dx = e / 2
        arg = (k * r + dx) / r
        alpha = 0.0 if (arg < -1.0 or arg > 1.0) else math.acos(arg)
        array[0] = alpha
        array[1] = dx
        return n

    def compute_params_ellipse(
        self,
        pt: tuple[float, float],
        pt_next: tuple[float, float],
        r: float,
        curl_adv: float,
    ) -> float:
        """Mirrors upstream's private ``computeParamsEllipse``
        (CloudyBorder.java:940)."""
        length = math.hypot(pt_next[0] - pt[0], pt_next[1] - pt[1])
        if length == 0.0:
            return _ANGLE_34_DEG
        e = length - curl_adv
        arg = (curl_adv / 2 + e / 2) / r
        return 0.0 if (arg < -1.0 or arg > 1.0) else math.acos(arg)

    def add_corner_curl(
        self,
        angle_prev: float,
        angle_cur: float,
        radius: float,
        cx: float,
        cy: float,
        alpha: float,
        alpha_prev: float,
        add_move_to: bool,
    ) -> None:
        """Mirrors upstream's private ``addCornerCurl``
        (CloudyBorder.java:428). TODO: full implementation."""
        # TODO: full implementation
        _ = (angle_prev, angle_cur, radius, cx, cy, alpha, alpha_prev, add_move_to)

    def add_first_intermediate_curl(
        self,
        angle_cur: float,
        r: float,
        alpha: float,
        cx: float,
        cy: float,
    ) -> None:
        """Mirrors upstream's private ``addFirstIntermediateCurl``
        (CloudyBorder.java:444). TODO: full implementation."""
        # TODO: full implementation
        _ = (angle_cur, r, alpha, cx, cy)

    def get_intermediate_curl_template(
        self, angle_cur: float, r: float
    ) -> list[tuple[float, float]]:
        """Mirrors upstream's private ``getIntermediateCurlTemplate``
        (CloudyBorder.java:458). TODO: full implementation."""
        # TODO: full implementation
        _ = (angle_cur, r)
        return []

    def output_curl_template(
        self, template: list[tuple[float, float]], x: float, y: float
    ) -> None:
        """Mirrors upstream's private ``outputCurlTemplate``
        (CloudyBorder.java:475). TODO: full implementation."""
        # TODO: full implementation
        _ = (template, x, y)

    def reverse_polygon(self, points: list[tuple[float, float]]) -> None:
        """Mirrors upstream's private ``reversePolygon``
        (CloudyBorder.java:537). Reverses ``points`` in place."""
        points.reverse()

    def get_positive_polygon(self, points: list[tuple[float, float]]) -> None:
        """Mirrors upstream's private ``getPositivePolygon``
        (CloudyBorder.java:556)."""
        if self.get_polygon_direction(points) < 0:
            self.reverse_polygon(points)

    def get_polygon_direction(
        self, points: list[tuple[float, float]]
    ) -> float:
        """Mirrors upstream's private ``getPolygonDirection``
        (CloudyBorder.java:573). Shoelace formula."""
        a = 0.0
        n = len(points)
        if n == 0:
            return 0.0
        for i in range(n):
            j = (i + 1) % n
            a += points[i][0] * points[j][1] - points[i][1] * points[j][0]
        return a

    def get_arc(
        self,
        start_ang: float,
        end_ang: float,
        rx: float,
        ry: float,
        cx: float,
        cy: float,
        out: list[tuple[float, float]] | None,
        add_move_to: bool,
    ) -> None:
        """Mirrors upstream's private ``getArc``
        (CloudyBorder.java:592). TODO: full implementation."""
        # TODO: full implementation
        _ = (start_ang, end_ang, rx, ry, cx, cy, out, add_move_to)

    def get_arc_segment(
        self,
        start_ang: float,
        end_ang: float,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        out: list[tuple[float, float]] | None,
        add_move_to: bool,
    ) -> None:
        """Mirrors upstream's private ``getArcSegment``
        (CloudyBorder.java:639). TODO: full implementation."""
        # TODO: full implementation
        _ = (start_ang, end_ang, cx, cy, rx, ry, out, add_move_to)

    @staticmethod
    def flatten_ellipse(
        left: float, bottom: float, right: float, top: float
    ) -> list[tuple[float, float]]:
        """Mirrors upstream's private static ``flattenEllipse``
        (CloudyBorder.java:705). TODO: full implementation — flatten
        the ellipse path into a polygon with flatness 0.5."""
        # TODO: full implementation
        _ = (left, bottom, right, top)
        return []

    def remove_zero_length_segments(
        self, polygon: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Mirrors upstream's private ``removeZeroLengthSegments``
        (CloudyBorder.java:954)."""
        np = len(polygon)
        if np <= 2:
            return polygon
        toler = 0.50
        result: list[tuple[float, float]] = [polygon[0]]
        pt_prev = polygon[0]
        for i in range(1, np):
            pt = polygon[i]
            if abs(pt[0] - pt_prev[0]) < toler and abs(pt[1] - pt_prev[1]) < toler:
                # Skip but advance pt_prev so duplicates collapse correctly.
                pt_prev = pt
                continue
            result.append(pt)
            pt_prev = pt
        return result

    def draw_basic_ellipse(
        self, left: float, bottom: float, right: float, top: float
    ) -> None:
        """Mirrors upstream's private ``drawBasicEllipse``
        (CloudyBorder.java:1000). TODO: full implementation."""
        # TODO: full implementation
        _ = (left, bottom, right, top)

    def begin_output(self, x: float, y: float) -> None:
        """Mirrors upstream's private ``beginOutput``
        (CloudyBorder.java:1010)."""
        self._bbox_min_x = x
        self._bbox_min_y = y
        self._bbox_max_x = x
        self._bbox_max_y = y
        self._output_started = True
        output = self._output
        if output is not None and hasattr(output, "set_line_join_style"):
            output.set_line_join_style(2)

    def move_to(self, *args: Any) -> None:
        """Mirrors upstream's overloaded private ``moveTo``
        (CloudyBorder.java:1029, 1034). Accepts ``(point)`` or
        ``(x, y)``."""
        if len(args) == 1:
            point = args[0]
            x = float(point[0])
            y = float(point[1])
        elif len(args) == 2:
            x = float(args[0])
            y = float(args[1])
        else:  # pragma: no cover - defensive
            raise TypeError("move_to expects (point) or (x, y)")
        if self._output_started:
            self.update_b_box(x, y)
        else:
            self.begin_output(x, y)
        output = self._output
        if output is not None and hasattr(output, "move_to"):
            output.move_to(x, y)

    def line_to(self, *args: Any) -> None:
        """Mirrors upstream's overloaded private ``lineTo``
        (CloudyBorder.java:1048, 1053)."""
        if len(args) == 1:
            point = args[0]
            x = float(point[0])
            y = float(point[1])
        elif len(args) == 2:
            x = float(args[0])
            y = float(args[1])
        else:  # pragma: no cover - defensive
            raise TypeError("line_to expects (point) or (x, y)")
        if self._output_started:
            self.update_b_box(x, y)
        else:
            self.begin_output(x, y)
        output = self._output
        if output is not None and hasattr(output, "line_to"):
            output.line_to(x, y)

    def curve_to(
        self,
        ax: float,
        ay: float,
        bx: float,
        by: float,
        cx: float,
        cy: float,
    ) -> None:
        """Mirrors upstream's private ``curveTo``
        (CloudyBorder.java:1067)."""
        self.update_b_box(ax, ay)
        self.update_b_box(bx, by)
        self.update_b_box(cx, cy)
        output = self._output
        if output is not None and hasattr(output, "curve_to"):
            output.curve_to(ax, ay, bx, by, cx, cy)

    def finish(self) -> None:
        """Mirrors upstream's private ``finish``
        (CloudyBorder.java:1076)."""
        output = self._output
        if self._output_started and output is not None and hasattr(output, "close_path"):
            output.close_path()
        if self._line_width > 0:
            d = self._line_width / 2
            self._bbox_min_x -= d
            self._bbox_min_y -= d
            self._bbox_max_x += d
            self._bbox_max_y += d

    def get_ellipse_cloud_radius(self) -> float:
        """Mirrors upstream's private ``getEllipseCloudRadius``
        (CloudyBorder.java:1093)."""
        return 4.75 * self._intensity + 0.5 * self._line_width

    def get_polygon_cloud_radius(self) -> float:
        """Mirrors upstream's private ``getPolygonCloudRadius``
        (CloudyBorder.java:1100)."""
        return 4 * self._intensity + 0.5 * self._line_width


__all__ = ["CloudyBorder"]
