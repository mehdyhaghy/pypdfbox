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

    Full port of the upstream geometry engine: corner / intermediate curl
    Bezier templates around polygons, ellipse flattening, and the bounding
    box bookkeeping that drives the form-XObject ``/BBox`` / ``/Matrix`` /
    ``/RD`` entries on the parent annotation.
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
        (CloudyBorder.java:86)."""
        self._rect_with_diff = self._apply_rect_diff(rd, self._line_width / 2)
        left = self._rect_with_diff.get_lower_left_x()
        bottom = self._rect_with_diff.get_lower_left_y()
        right = self._rect_with_diff.get_upper_right_x()
        top = self._rect_with_diff.get_upper_right_y()

        self.cloudy_rectangle_impl(left, bottom, right, top, False)
        self.finish()

    def create_cloudy_polygon(self, path: list[list[float]]) -> None:
        """Generate a cloudy border for a polygon annotation.

        Mirrors upstream ``createCloudyPolygon(float[][])``
        (CloudyBorder.java:104). ``path`` is a list of points expressed
        as ``[x, y]`` (move/line vertices) or ``[x1, y1, x2, y2, x3, y3]``
        (Bezier — the endpoint is used, curves are not yet supported).
        """
        n = len(path)
        polygon: list[tuple[float, float]] = []
        for i in range(n):
            array = path[i]
            if len(array) == 2:
                polygon.append((float(array[0]), float(array[1])))
            elif len(array) == 6:
                # Curve segments are not yet supported in cloudy border.
                polygon.append((float(array[4]), float(array[5])))
        self.cloudy_polygon_impl(polygon, False)
        self.finish()

    def create_cloudy_ellipse(self, rd: PDRectangle | None) -> None:
        """Generate a cloudy border for a circle annotation.

        Mirrors upstream ``createCloudyEllipse(PDRectangle)``
        (CloudyBorder.java:135).
        """
        self._rect_with_diff = self._apply_rect_diff(rd, 0.0)
        left = self._rect_with_diff.get_lower_left_x()
        bottom = self._rect_with_diff.get_lower_left_y()
        right = self._rect_with_diff.get_upper_right_x()
        top = self._rect_with_diff.get_upper_right_y()

        self.cloudy_ellipse_impl(left, bottom, right, top)
        self.finish()

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
        rect_left = self._annot_rect.get_lower_left_x()
        rect_bottom = self._annot_rect.get_lower_left_y()
        rect_right = self._annot_rect.get_upper_right_x()
        rect_top = self._annot_rect.get_upper_right_y()

        # Normalize — matches upstream's awkward ordering verbatim.
        rect_left = min(rect_left, rect_right)
        rect_bottom = min(rect_bottom, rect_top)
        rect_right = max(rect_left, rect_right)
        rect_top = max(rect_bottom, rect_top)

        if rd is not None:
            rd_left = max(rd.get_lower_left_x(), min_diff)
            rd_bottom = max(rd.get_lower_left_y(), min_diff)
            rd_right = max(rd.get_upper_right_x(), min_diff)
            rd_top = max(rd.get_upper_right_y(), min_diff)
        else:
            rd_left = min_diff
            rd_bottom = min_diff
            rd_right = min_diff
            rd_top = min_diff

        rect_left += rd_left
        rect_bottom += rd_bottom
        rect_right -= rd_right
        rect_top -= rd_top

        return PDRectangle.from_xywh(
            rect_left,
            rect_bottom,
            rect_right - rect_left,
            rect_top - rect_bottom,
        )

    def _update_bbox(self, x: float, y: float) -> None:
        """Track the running bbox extents. Mirrors upstream's private
        ``updateBBox`` (CloudyBorder.java:1021)."""
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
    # counts them.
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
        (CloudyBorder.java:225). Converts the rectangle into a closed
        polygon and dispatches to :meth:`cloudy_polygon_impl`."""
        w = right - left
        h = top - bottom

        if self._intensity <= 0.0:
            output = self._output
            if output is not None and hasattr(output, "add_rect"):
                output.add_rect(left, bottom, w, h)
            self._bbox_min_x = left
            self._bbox_min_y = bottom
            self._bbox_max_x = right
            self._bbox_max_y = top
            return

        if w < 1.0:
            polygon: list[tuple[float, float]] = [
                (left, bottom),
                (left, top),
                (left, bottom),
            ]
        elif h < 1.0:
            polygon = [(left, bottom), (right, bottom), (left, bottom)]
        else:
            polygon = [
                (left, bottom),
                (right, bottom),
                (right, top),
                (left, top),
                (left, bottom),
            ]

        self.cloudy_polygon_impl(polygon, is_ellipse)

    def cloudy_polygon_impl(
        self, vertices: list[tuple[float, float]], is_ellipse: bool
    ) -> None:
        """Mirrors upstream's private ``cloudyPolygonImpl``
        (CloudyBorder.java:279)."""
        polygon = self.remove_zero_length_segments(list(vertices))
        # In-place direction adjustment — match upstream semantics by
        # operating on a mutable list.
        polygon_list = list(polygon)
        self.get_positive_polygon(polygon_list)
        num_points = len(polygon_list)

        if num_points < 2:
            return
        if self._intensity <= 0.0:
            self.move_to(polygon_list[0])
            for i in range(1, num_points):
                self.line_to(polygon_list[i])
            return

        cloud_radius = (
            self.get_ellipse_cloud_radius()
            if is_ellipse
            else self.get_polygon_cloud_radius()
        )
        if cloud_radius < 0.5:
            cloud_radius = 0.5

        k = math.cos(_ANGLE_34_DEG)
        adv_interm_default = 2 * k * cloud_radius
        adv_corner_default = k * cloud_radius
        array = [0.0, 0.0]
        angle_prev = 0.0

        prev_pt = polygon_list[num_points - 2]
        first_pt = polygon_list[0]
        seed_length = math.hypot(
            first_pt[0] - prev_pt[0], first_pt[1] - prev_pt[1]
        )
        n0 = self.compute_params_polygon(
            adv_interm_default,
            adv_corner_default,
            k,
            cloud_radius,
            seed_length,
            array,
        )
        alpha_prev = array[0] if n0 == 0 else _ANGLE_34_DEG

        j = 0
        while j + 1 < num_points:
            pt = polygon_list[j]
            pt_next = polygon_list[j + 1]
            length = math.hypot(pt_next[0] - pt[0], pt_next[1] - pt[1])
            if length == 0.0:
                alpha_prev = _ANGLE_34_DEG
                j += 1
                continue

            n = self.compute_params_polygon(
                adv_interm_default,
                adv_corner_default,
                k,
                cloud_radius,
                length,
                array,
            )
            if n < 0:
                if not self._output_started:
                    self.move_to(pt)
                j += 1
                continue

            alpha = array[0]
            dx_off = array[1]

            angle_cur = math.atan2(pt_next[1] - pt[1], pt_next[0] - pt[0])
            if j == 0:
                pt_prev = polygon_list[num_points - 2]
                angle_prev = math.atan2(
                    pt[1] - pt_prev[1], pt[0] - pt_prev[0]
                )

            cos_a = self.cosine(pt_next[0] - pt[0], length)
            sin_a = self.sine(pt_next[1] - pt[1], length)
            x = pt[0]
            y = pt[1]

            self.add_corner_curl(
                angle_prev,
                angle_cur,
                cloud_radius,
                pt[0],
                pt[1],
                alpha,
                alpha_prev,
                not self._output_started,
            )
            # Advance to the center point of the first intermediate curl.
            adv = 2 * k * cloud_radius + 2 * dx_off
            x += adv * cos_a
            y += adv * sin_a

            num_interm = n
            if n >= 1:
                self.add_first_intermediate_curl(
                    angle_cur, cloud_radius, alpha, x, y
                )
                x += adv_interm_default * cos_a
                y += adv_interm_default * sin_a
                num_interm = n - 1

            template = self.get_intermediate_curl_template(
                angle_cur, cloud_radius
            )
            for _ in range(num_interm):
                self.output_curl_template(template, x, y)
                x += adv_interm_default * cos_a
                y += adv_interm_default * sin_a

            angle_prev = angle_cur
            alpha_prev = alpha if n == 0 else _ANGLE_34_DEG
            j += 1

    def cloudy_ellipse_impl(
        self,
        left_orig: float,
        bottom_orig: float,
        right_orig: float,
        top_orig: float,
    ) -> None:
        """Mirrors upstream's private ``cloudyEllipseImpl``
        (CloudyBorder.java:743)."""
        if self._intensity <= 0.0:
            self.draw_basic_ellipse(left_orig, bottom_orig, right_orig, top_orig)
            return

        left = left_orig
        bottom = bottom_orig
        right = right_orig
        top = top_orig
        width = right - left
        height = top - bottom
        cloud_radius = self.get_ellipse_cloud_radius()

        threshold1 = 0.50 * cloud_radius
        if width < threshold1 and height < threshold1:
            self.draw_basic_ellipse(left, bottom, right, top)
            return

        threshold2 = 5
        if (width < threshold2 and height > 20) or (
            width > 20 and height < threshold2
        ):
            self.cloudy_rectangle_impl(left, bottom, right, top, True)
            return

        radius_adj = math.sin(_ANGLE_12_DEG) * cloud_radius - 1.50
        if width > 2 * radius_adj:
            left += radius_adj
            right -= radius_adj
        else:
            mid = (left + right) / 2
            left = mid - 0.10
            right = mid + 0.10
        if height > 2 * radius_adj:
            top -= radius_adj
            bottom += radius_adj
        else:
            mid = (top + bottom) / 2
            top = mid + 0.10
            bottom = mid - 0.10

        flat_polygon = self.flatten_ellipse(left, bottom, right, top)
        num_points = len(flat_polygon)
        if num_points < 2:
            return

        tot_len = 0.0
        for i in range(1, num_points):
            tot_len += math.hypot(
                flat_polygon[i][0] - flat_polygon[i - 1][0],
                flat_polygon[i][1] - flat_polygon[i - 1][1],
            )

        k = math.cos(_ANGLE_34_DEG)
        curl_advance = 2 * k * cloud_radius
        n = int(math.ceil(tot_len / curl_advance))
        if n < 2:
            self.draw_basic_ellipse(left_orig, bottom_orig, right_orig, top_orig)
            return

        curl_advance = tot_len / n
        cloud_radius = curl_advance / (2 * k)

        if cloud_radius < 0.5:
            cloud_radius = 0.5
            curl_advance = 2 * k * cloud_radius
        elif cloud_radius < 3.0:
            self.draw_basic_ellipse(left_orig, bottom_orig, right_orig, top_orig)
            return

        center_points_length = n
        center_points: list[tuple[float, float]] = []
        length_remain = 0.0
        comparison_toler = self._line_width * 0.10

        for i in range(num_points - 1):
            p1 = flat_polygon[i]
            p2 = flat_polygon[i + 1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = math.hypot(dx, dy)
            if length == 0.0:
                continue
            length_todo = length + length_remain
            if (
                length_todo >= curl_advance - comparison_toler
                or i == num_points - 2
            ):
                cos_a = self.cosine(dx, length)
                sin_a = self.sine(dy, length)
                d = curl_advance - length_remain
                while True:
                    x = p1[0] + d * cos_a
                    y = p1[1] + d * sin_a
                    if len(center_points) < center_points_length:
                        center_points.append((x, y))
                    length_todo -= curl_advance
                    d += curl_advance
                    if not (length_todo >= curl_advance - comparison_toler):
                        break
                length_remain = length_todo
                if length_remain < 0:
                    length_remain = 0.0
            else:
                length_remain += length

        num_points = len(center_points)
        angle_prev = 0.0
        alpha_prev = 0.0

        for i in range(num_points):
            idx_next = i + 1
            if i + 1 >= num_points:
                idx_next = 0
            pt = center_points[i]
            pt_next = center_points[idx_next]

            if i == 0:
                pt_prev = center_points[num_points - 1]
                angle_prev = math.atan2(
                    pt[1] - pt_prev[1], pt[0] - pt_prev[0]
                )
                alpha_prev = self.compute_params_ellipse(
                    pt_prev, pt, cloud_radius, curl_advance
                )

            angle_cur = math.atan2(pt_next[1] - pt[1], pt_next[0] - pt[0])
            alpha = self.compute_params_ellipse(
                pt, pt_next, cloud_radius, curl_advance
            )

            self.add_corner_curl(
                angle_prev,
                angle_cur,
                cloud_radius,
                pt[0],
                pt[1],
                alpha,
                alpha_prev,
                not self._output_started,
            )

            angle_prev = angle_cur
            alpha_prev = alpha

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
        (CloudyBorder.java:398)."""
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
        (CloudyBorder.java:428)."""
        a = angle_prev + _ANGLE_180_DEG + alpha_prev
        b = angle_prev + _ANGLE_180_DEG + alpha_prev - math.radians(22)
        self.get_arc_segment(a, b, cx, cy, radius, radius, None, add_move_to)

        a = b
        b = angle_cur - alpha
        self.get_arc(a, b, radius, radius, cx, cy, None, False)

    def add_first_intermediate_curl(
        self,
        angle_cur: float,
        r: float,
        alpha: float,
        cx: float,
        cy: float,
    ) -> None:
        """Mirrors upstream's private ``addFirstIntermediateCurl``
        (CloudyBorder.java:444)."""
        a = angle_cur + _ANGLE_180_DEG
        self.get_arc_segment(
            a + alpha, a + alpha - _ANGLE_30_DEG, cx, cy, r, r, None, False
        )
        self.get_arc_segment(
            a + alpha - _ANGLE_30_DEG, a + _ANGLE_90_DEG, cx, cy, r, r, None, False
        )
        self.get_arc_segment(
            a + _ANGLE_90_DEG,
            a + _ANGLE_180_DEG - _ANGLE_34_DEG,
            cx,
            cy,
            r,
            r,
            None,
            False,
        )

    def get_intermediate_curl_template(
        self, angle_cur: float, r: float
    ) -> list[tuple[float, float]]:
        """Mirrors upstream's private ``getIntermediateCurlTemplate``
        (CloudyBorder.java:458)."""
        points: list[tuple[float, float]] = []
        a = angle_cur + _ANGLE_180_DEG

        self.get_arc_segment(
            a + _ANGLE_34_DEG, a + _ANGLE_12_DEG, 0.0, 0.0, r, r, points, False
        )
        self.get_arc_segment(
            a + _ANGLE_12_DEG, a + _ANGLE_90_DEG, 0.0, 0.0, r, r, points, False
        )
        self.get_arc_segment(
            a + _ANGLE_90_DEG,
            a + _ANGLE_180_DEG - _ANGLE_34_DEG,
            0.0,
            0.0,
            r,
            r,
            points,
            False,
        )
        return points

    def output_curl_template(
        self, template: list[tuple[float, float]], x: float, y: float
    ) -> None:
        """Mirrors upstream's private ``outputCurlTemplate``
        (CloudyBorder.java:475)."""
        n = len(template)
        i = 0
        if (n % 3) == 1:
            a = template[0]
            self.move_to(a[0] + x, a[1] + y)
            i += 1
        while i + 2 < n:
            a = template[i]
            b = template[i + 1]
            c = template[i + 2]
            self.curve_to(
                a[0] + x, a[1] + y, b[0] + x, b[1] + y, c[0] + x, c[1] + y
            )
            i += 3

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
        (CloudyBorder.java:592)."""
        angle_incr = math.pi / 2
        startx = rx * math.cos(start_ang) + cx
        starty = ry * math.sin(start_ang) + cy

        angle_todo = end_ang - start_ang
        while angle_todo < 0:
            angle_todo += 2 * math.pi
        sweep = angle_todo
        angle_done = 0.0

        if add_move_to:
            if out is not None:
                out.append((startx, starty))
            else:
                self.move_to(startx, starty)

        while angle_todo > angle_incr:
            self.get_arc_segment(
                start_ang + angle_done,
                start_ang + angle_done + angle_incr,
                cx,
                cy,
                rx,
                ry,
                out,
                False,
            )
            angle_done += angle_incr
            angle_todo -= angle_incr

        if angle_todo > 0:
            self.get_arc_segment(
                start_ang + angle_done,
                start_ang + sweep,
                cx,
                cy,
                rx,
                ry,
                out,
                False,
            )

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
        (CloudyBorder.java:639). Single Bezier section of an elliptical
        arc. Sweep angle must not exceed 90 degrees."""
        cos_a = math.cos(start_ang)
        sin_a = math.sin(start_ang)
        cos_b = math.cos(end_ang)
        sin_b = math.sin(end_ang)
        denom = math.sin((end_ang - start_ang) / 2.0)
        if denom == 0.0:
            if add_move_to:
                xs = cx + rx * cos_a
                ys = cy + ry * sin_a
                if out is not None:
                    out.append((xs, ys))
                else:
                    self.move_to(xs, ys)
            return
        bcp = 1.333333333 * (1 - math.cos((end_ang - start_ang) / 2.0)) / denom
        p1x = cx + rx * (cos_a - bcp * sin_a)
        p1y = cy + ry * (sin_a + bcp * cos_a)
        p2x = cx + rx * (cos_b + bcp * sin_b)
        p2y = cy + ry * (sin_b - bcp * cos_b)
        p3x = cx + rx * cos_b
        p3y = cy + ry * sin_b

        if add_move_to:
            xs = cx + rx * cos_a
            ys = cy + ry * sin_a
            if out is not None:
                out.append((xs, ys))
            else:
                self.move_to(xs, ys)

        if out is not None:
            out.append((p1x, p1y))
            out.append((p2x, p2y))
            out.append((p3x, p3y))
        else:
            self.curve_to(p1x, p1y, p2x, p2y, p3x, p3y)

    @staticmethod
    def flatten_ellipse(
        left: float, bottom: float, right: float, top: float
    ) -> list[tuple[float, float]]:
        """Mirrors upstream's private static ``flattenEllipse``
        (CloudyBorder.java:705). Flatten the ellipse path into a polygon
        with flatness 0.50.

        Upstream relies on ``java.awt.geom.Ellipse2D.getPathIterator`` to
        produce the flat polygon. The lite port emulates the same
        behaviour by stepping around the ellipse in equal-angle
        increments chosen so the chord-to-arc distance stays under the
        flatness threshold.
        """
        rx = abs(right - left) / 2
        ry = abs(top - bottom) / 2
        cx = (left + right) / 2
        cy = (bottom + top) / 2

        if rx == 0.0 and ry == 0.0:
            return [(cx, cy)]

        # Chord error for a circular arc of radius r over half-angle h is
        # r * (1 - cos(h)).  Pick the increment such that max(rx, ry) * (1
        # - cos(h)) <= flatness.
        flatness = 0.50
        r_max = max(rx, ry)
        if r_max <= flatness:
            # Tiny ellipse — a single segment is enough.
            return [
                (cx + rx, cy),
                (cx, cy + ry),
                (cx - rx, cy),
                (cx, cy - ry),
                (cx + rx, cy),
            ]
        arg = 1.0 - flatness / r_max
        if arg < -1.0:
            arg = -1.0
        if arg > 1.0:
            arg = 1.0
        # Half-angle increment.
        half = math.acos(arg)
        step = max(2 * half, math.radians(1.0))
        steps = max(8, int(math.ceil(2 * math.pi / step)))
        step = 2 * math.pi / steps

        points: list[tuple[float, float]] = []
        for i in range(steps + 1):
            theta = i * step
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)
            points.append((x, y))

        # Upstream appends the last point a second time if the polygon
        # isn't visually closed; do the same.
        size = len(points)
        close_test_limit = 0.05
        if size >= 2 and math.hypot(
            points[-1][0] - points[0][0], points[-1][1] - points[0][1]
        ) > close_test_limit:
            points.append(points[-1])
        return points

    def remove_zero_length_segments(
        self, polygon: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Mirrors upstream's private ``removeZeroLengthSegments``
        (CloudyBorder.java:954)."""
        np = len(polygon)
        if np <= 2:
            return polygon
        toler = 0.50
        # Upstream skips repeated points but keeps the first / last
        # vertices (so polygon closure is preserved).
        result: list[tuple[float, float]] = [polygon[0]]
        pt_prev = polygon[0]
        for i in range(1, np):
            pt = polygon[i]
            if (
                abs(pt[0] - pt_prev[0]) < toler
                and abs(pt[1] - pt_prev[1]) < toler
            ):
                pt_prev = pt
                continue
            result.append(pt)
            pt_prev = pt
        return result

    def draw_basic_ellipse(
        self, left: float, bottom: float, right: float, top: float
    ) -> None:
        """Mirrors upstream's private ``drawBasicEllipse``
        (CloudyBorder.java:1000)."""
        rx = abs(right - left) / 2
        ry = abs(top - bottom) / 2
        cx = (left + right) / 2
        cy = (bottom + top) / 2
        self.get_arc(0.0, 2 * math.pi, rx, ry, cx, cy, None, True)

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
