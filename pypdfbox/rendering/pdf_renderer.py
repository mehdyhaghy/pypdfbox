from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any

import aggdraw
from PIL import Image

from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import (
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSNumber,
    COSStream,
)

if TYPE_CHECKING:
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.pdmodel.pd_document import PDDocument

_log = logging.getLogger(__name__)

# 6-tuple affine matrix used in both PDF (CTM) and PIL (settransform) form.
# We carry CTM as a tuple ``(a, b, c, d, e, f)`` representing the PDF matrix
# ``[a b 0; c d 0; e f 1]`` so a point ``(x, y)`` maps to
# ``(a*x + c*y + e, b*x + d*y + f)``. Matrix multiplication ``m1 * m2`` is
# defined as "apply m2 first, then m1" (same convention as PDFBox's
# ``Matrix.multiply``).
_Matrix = tuple[float, float, float, float, float, float]
_IDENTITY: _Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _matmul(m1: _Matrix, m2: _Matrix) -> _Matrix:
    """Return ``m2 * m1`` in PDF convention (concatenate ``m1`` *into*
    ``m2``: a `cm` operator post-multiplies the current CTM by its operand
    so that user-space ``[x y 1] * m1 * existing_ctm`` is the page-space
    point). This matches PDFBox's ``Matrix.multiply(other, this)``."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _to_pil_affine(m: _Matrix) -> tuple[float, float, float, float, float, float]:
    """Convert a PDF CTM ``(a, b, c, d, e, f)`` to PIL/aggdraw's
    ``(a, b, c, d, e, f)`` row-vector form where ``x' = a*x + b*y + c``,
    ``y' = d*x + e*y + f``. The two representations transpose the 2x2
    rotation/scale block and reorder the translation pair."""
    a, b, c, d, e, f = m
    return (a, c, e, b, d, f)


class _GraphicsState:
    """Subset of the PDF graphics state we honour. Mirrors a tiny slice of
    upstream ``PDGraphicsState`` — CTM, stroke/fill colour, line width.
    Everything else (clip, dash, miter, blend, soft mask) is intentionally
    skipped in v1 (see ``CHANGES.md``)."""

    __slots__ = ("ctm", "stroke_rgb", "fill_rgb", "line_width")

    def __init__(self) -> None:
        self.ctm: _Matrix = _IDENTITY
        self.stroke_rgb: tuple[int, int, int] = (0, 0, 0)
        self.fill_rgb: tuple[int, int, int] = (0, 0, 0)
        self.line_width: float = 1.0

    def clone(self) -> _GraphicsState:
        clone = _GraphicsState()
        clone.ctm = self.ctm
        clone.stroke_rgb = self.stroke_rgb
        clone.fill_rgb = self.fill_rgb
        clone.line_width = self.line_width
        return clone


def _to_float(value: COSBase | None) -> float:
    if isinstance(value, COSNumber):
        return value.float_value()
    if isinstance(value, (COSInteger, COSFloat)):
        return float(value.value)
    return 0.0


def _clamp_byte(v: float) -> int:
    if v <= 0.0:
        return 0
    if v >= 1.0:
        return 255
    return int(round(v * 255.0))


def _rgb_bytes(r: float, g: float, b: float) -> tuple[int, int, int]:
    return (_clamp_byte(r), _clamp_byte(g), _clamp_byte(b))


def _cmyk_to_rgb_bytes(c: float, m: float, y: float, k: float) -> tuple[int, int, int]:
    r = (1.0 - c) * (1.0 - k)
    g = (1.0 - m) * (1.0 - k)
    b = (1.0 - y) * (1.0 - k)
    return _rgb_bytes(r, g, b)


class PDFRenderer(PDFStreamEngine):
    """
    Render PDF pages to ``PIL.Image`` via aggdraw (anti-aliased AGG-backed
    path rasteriser). Mirrors ``org.apache.pdfbox.rendering.PDFRenderer`` —
    upstream uses Java2D + ``PageDrawer``; we fold the page-drawing logic
    into a single subclass of :class:`PDFStreamEngine` and delegate to
    aggdraw for stroking, filling, and CTM-aware affine transforms.

    Operator coverage (rendering cluster #1 lite):

    - Path: ``m``, ``l``, ``c``, ``v``, ``y``, ``re``, ``h``
    - Painting: ``S``, ``s``, ``f``/``F``, ``f*``, ``B``, ``B*``, ``b``,
      ``b*``, ``n``
    - Graphics state: ``q``/``Q`` push/pop CTM + colour + line width
    - Transform: ``cm`` concatenates a 6-float matrix into the CTM
    - Colour: ``RG``/``rg``/``K``/``k``/``G``/``g`` (DeviceRGB / DeviceCMYK
      / DeviceGray)
    - Line state: ``w`` line width
    - Image XObject ``Do`` for ``/Subtype /Image`` (decoded via ``PDStream``
      → ``PIL.Image`` and pasted through CTM-derived affine transform)

    Deferred (silent skip in v1; tracked in ``CHANGES.md``):

    - Text operators (``BT``/``ET``/``Tj``/``TJ``/``'``/``"``) draw a faint
      placeholder rectangle covering the rendered bbox; real glyph drawing
      requires the font cluster.
    - Shadings, patterns, transparency groups, soft masks, blend modes,
      line dash/cap/join, clipping paths, form XObjects.
    """

    def __init__(self, document: PDDocument) -> None:
        super().__init__()
        self._document = document
        # Per-render mutable state (set in render_image_with_dpi):
        self._image: Image.Image | None = None
        self._draw: aggdraw.Draw | None = None
        self._scale: float = 1.0
        self._page_height_px: float = 0.0
        self._device_ctm: _Matrix = _IDENTITY
        # Graphics-state stack — top-of-stack at index -1.
        self._gs_stack: list[_GraphicsState] = []
        # Current path as a list of subpaths; each subpath is a list of
        # segments. A segment is a tuple ``("M", x, y)``, ``("L", x, y)``,
        # or ``("C", x1, y1, x2, y2, x, y)``. Paths are built in user space
        # (i.e. NOT yet transformed) — the transform is applied at draw
        # time via aggdraw's ``settransform``.
        self._subpaths: list[list[tuple]] = []
        self._current_subpath: list[tuple] | None = None
        self._current_point: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------------
    # public API (mirrors PDFRenderer.java)
    # ------------------------------------------------------------------

    def render_image(self, page_index: int, scale: float = 1.0) -> Image.Image:
        """Render at 72 DPI base * ``scale``. Mirrors upstream
        ``PDFRenderer.renderImage(int, float)``."""
        return self.render_image_with_dpi(page_index, dpi=72.0 * scale)

    def render_image_with_dpi(
        self, page_index: int, dpi: float = 72.0
    ) -> Image.Image:
        """Render the page at the given DPI. Mirrors upstream
        ``PDFRenderer.renderImageWithDPI``."""
        page = self._document.get_pages()[page_index]
        media_box = page.get_media_box()
        # PDF user-space units are 1/72 inch. Pixel dims = pts * dpi / 72.
        scale = float(dpi) / 72.0
        width_pt = media_box.get_width()
        height_pt = media_box.get_height()
        width_px = max(1, int(round(width_pt * scale)))
        height_px = max(1, int(round(height_pt * scale)))

        image = Image.new("RGB", (width_px, height_px), (255, 255, 255))

        # Reset per-render state. ``self._draw`` is the *current* aggdraw
        # wrapper around ``self._image``; it may be replaced mid-render
        # whenever we paste-mutate the underlying PIL image directly
        # (see ``_paste_image`` / ``_fill_even_odd_via_pil``). Keeping a
        # local copy of the original would be a footgun — flushing it at
        # teardown would clobber the freshly-pasted pixels with aggdraw's
        # stale internal buffer.
        self._image = image
        self._draw = aggdraw.Draw(image)
        self._draw.setantialias(True)
        self._scale = scale
        self._page_height_px = float(height_px)

        # Device CTM: PDF y-axis points up with origin at lower-left, PIL
        # y-axis points down with origin at top-left. Combine the y-flip
        # with the DPI scale + media-box origin offset:
        #   device = [scale 0; 0 -scale] * [1 0; 0 1; -mb.x -mb.y] +
        #            [0 height_px]
        # Implemented as a single PDF-style 6-tuple.
        mb_x = media_box.get_lower_left_x()
        mb_y = media_box.get_lower_left_y()
        self._device_ctm = (
            scale,
            0.0,
            0.0,
            -scale,
            -mb_x * scale,
            mb_y * scale + height_px,
        )

        # Fresh graphics-state stack with one identity entry.
        self._gs_stack = [_GraphicsState()]
        self._subpaths = []
        self._current_subpath = None
        self._current_point = (0.0, 0.0)

        try:
            self.process_page(page)
        finally:
            # Flush whatever aggdraw wrapper is currently bound — it may
            # have been replaced mid-render by ``_paste_image`` or
            # ``_fill_even_odd_via_pil`` after we reached back into the
            # underlying PIL buffer. Flushing the *current* draw commits
            # any pending strokes since the last replace; the local
            # ``draw`` from the start may already be stale.
            current = self._draw
            if current is not None:
                current.flush()
            self._draw = None
            self._image = None

        return image

    # ------------------------------------------------------------------
    # graphics-state helpers
    # ------------------------------------------------------------------

    @property
    def _gs(self) -> _GraphicsState:
        return self._gs_stack[-1]

    def _push_gs(self) -> None:
        self._gs_stack.append(self._gs.clone())

    def _pop_gs(self) -> None:
        if len(self._gs_stack) > 1:
            self._gs_stack.pop()

    def _full_ctm(self) -> _Matrix:
        """User-space → device-pixel transform: page CTM stacked onto the
        device CTM that applies dpi scale + y-axis flip."""
        return _matmul(self._gs.ctm, self._device_ctm)

    # ------------------------------------------------------------------
    # operator dispatch override — handle EVERY operator inline rather
    # than going through the registered processor map. The engine's
    # default ``unsupported_operator`` is a silent no-op which is fine for
    # ops we don't model; we override ``process_operator`` so we don't
    # have to carry 30+ tiny ``OperatorProcessor`` subclasses for the
    # rendering cluster.
    # ------------------------------------------------------------------

    def process_operator(
        self,
        operator: Operator | str,
        operands: list[COSBase] | None,
    ) -> None:
        if operands is None:
            operands = []
        # Coerce string → engine-native Operator only when needed for
        # name extraction; we never re-dispatch here.
        from pypdfbox.contentstream.operator import (  # noqa: PLC0415
            Operator as _Op,
        )

        op = operator if isinstance(operator, _Op) else _Op.get_operator(operator)
        name = op.get_name()
        handler = _DISPATCH.get(name)
        if handler is None:
            # Unmodelled — silently skip (matches engine default).
            return
        try:
            handler(self, op, operands)
        except (OSError, ValueError, TypeError, IndexError) as exc:
            # Defensive — log and continue rather than aborting the page
            # render on a single malformed operator (mirrors PDFBox's
            # ``operatorException`` triage for the rendering path).
            _log.debug("rendering: dropping operator %s: %s", name, exc)

    # ------------------------------------------------------------------
    # operator handlers — each returns nothing; updates self state /
    # draws into the current aggdraw canvas as a side effect.
    # ------------------------------------------------------------------

    def _op_save(self, _op: Any, _operands: list[COSBase]) -> None:
        self._push_gs()

    def _op_restore(self, _op: Any, _operands: list[COSBase]) -> None:
        self._pop_gs()

    def _op_concat_matrix(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            return
        m = tuple(_to_float(operands[i]) for i in range(6))
        # cm post-multiplies the current CTM. PDF spec §8.4.4: "Modify
        # the current transformation matrix (CTM) by concatenating the
        # specified matrix" — new_ctm = matrix * old_ctm.
        self._gs.ctm = _matmul(m, self._gs.ctm)

    # ---- colour ----

    def _op_set_stroke_rgb(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 3:
            return
        r, g, b = (_to_float(operands[i]) for i in range(3))
        self._gs.stroke_rgb = _rgb_bytes(r, g, b)

    def _op_set_fill_rgb(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 3:
            return
        r, g, b = (_to_float(operands[i]) for i in range(3))
        self._gs.fill_rgb = _rgb_bytes(r, g, b)

    def _op_set_stroke_gray(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        g = _to_float(operands[0])
        self._gs.stroke_rgb = _rgb_bytes(g, g, g)

    def _op_set_fill_gray(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        g = _to_float(operands[0])
        self._gs.fill_rgb = _rgb_bytes(g, g, g)

    def _op_set_stroke_cmyk(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 4:
            return
        c, m, y, k = (_to_float(operands[i]) for i in range(4))
        self._gs.stroke_rgb = _cmyk_to_rgb_bytes(c, m, y, k)

    def _op_set_fill_cmyk(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 4:
            return
        c, m, y, k = (_to_float(operands[i]) for i in range(4))
        self._gs.fill_rgb = _cmyk_to_rgb_bytes(c, m, y, k)

    # ---- line state ----

    def _op_line_width(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        self._gs.line_width = max(0.0, _to_float(operands[0]))

    # ---- path construction ----

    def _start_subpath(self, x: float, y: float) -> None:
        self._current_subpath = [("M", x, y)]
        self._subpaths.append(self._current_subpath)
        self._current_point = (x, y)

    def _op_move_to(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            return
        x, y = _to_float(operands[0]), _to_float(operands[1])
        self._start_subpath(x, y)

    def _op_line_to(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            return
        if self._current_subpath is None:
            return
        x, y = _to_float(operands[0]), _to_float(operands[1])
        self._current_subpath.append(("L", x, y))
        self._current_point = (x, y)

    def _op_curve_to(self, _op: Any, operands: list[COSBase]) -> None:
        # c x1 y1 x2 y2 x3 y3
        if len(operands) < 6 or self._current_subpath is None:
            return
        vals = [_to_float(operands[i]) for i in range(6)]
        x1, y1, x2, y2, x3, y3 = vals
        self._current_subpath.append(("C", x1, y1, x2, y2, x3, y3))
        self._current_point = (x3, y3)

    def _op_curve_to_v(self, _op: Any, operands: list[COSBase]) -> None:
        # v x2 y2 x3 y3 — first control point = current point
        if len(operands) < 4 or self._current_subpath is None:
            return
        x0, y0 = self._current_point
        x2, y2 = _to_float(operands[0]), _to_float(operands[1])
        x3, y3 = _to_float(operands[2]), _to_float(operands[3])
        self._current_subpath.append(("C", x0, y0, x2, y2, x3, y3))
        self._current_point = (x3, y3)

    def _op_curve_to_y(self, _op: Any, operands: list[COSBase]) -> None:
        # y x1 y1 x3 y3 — second control point = end point
        if len(operands) < 4 or self._current_subpath is None:
            return
        x1, y1 = _to_float(operands[0]), _to_float(operands[1])
        x3, y3 = _to_float(operands[2]), _to_float(operands[3])
        self._current_subpath.append(("C", x1, y1, x3, y3, x3, y3))
        self._current_point = (x3, y3)

    def _op_rect(self, _op: Any, operands: list[COSBase]) -> None:
        # re x y w h — degenerate as four lines + close. Always starts a
        # NEW subpath even if a current point exists (PDF spec §8.5.2.1).
        if len(operands) < 4:
            return
        x, y, w, h = (_to_float(operands[i]) for i in range(4))
        self._start_subpath(x, y)
        self._current_subpath.append(("L", x + w, y))
        self._current_subpath.append(("L", x + w, y + h))
        self._current_subpath.append(("L", x, y + h))
        self._current_subpath.append(("Z",))
        self._current_point = (x, y)

    def _op_close_path(self, _op: Any, _operands: list[COSBase]) -> None:
        if self._current_subpath is None:
            return
        self._current_subpath.append(("Z",))
        # current point goes back to the subpath's first moveto target
        first = self._current_subpath[0]
        if first[0] == "M":
            self._current_point = (first[1], first[2])

    # ---- painting ----

    def _op_stroke(self, _op: Any, _operands: list[COSBase]) -> None:
        self._paint(stroke=True, fill=False, even_odd=False)

    def _op_close_and_stroke(self, _op: Any, _operands: list[COSBase]) -> None:
        self._close_open_subpath()
        self._paint(stroke=True, fill=False, even_odd=False)

    def _op_fill(self, _op: Any, _operands: list[COSBase]) -> None:
        self._paint(stroke=False, fill=True, even_odd=False)

    def _op_fill_even_odd(self, _op: Any, _operands: list[COSBase]) -> None:
        self._paint(stroke=False, fill=True, even_odd=True)

    def _op_fill_then_stroke(self, _op: Any, _operands: list[COSBase]) -> None:
        self._paint(stroke=True, fill=True, even_odd=False)

    def _op_fill_then_stroke_even_odd(
        self, _op: Any, _operands: list[COSBase]
    ) -> None:
        self._paint(stroke=True, fill=True, even_odd=True)

    def _op_close_fill_then_stroke(
        self, _op: Any, _operands: list[COSBase]
    ) -> None:
        self._close_open_subpath()
        self._paint(stroke=True, fill=True, even_odd=False)

    def _op_close_fill_then_stroke_even_odd(
        self, _op: Any, _operands: list[COSBase]
    ) -> None:
        self._close_open_subpath()
        self._paint(stroke=True, fill=True, even_odd=True)

    def _op_end_path(self, _op: Any, _operands: list[COSBase]) -> None:
        # n — discard the path without painting.
        self._reset_path()

    def _close_open_subpath(self) -> None:
        if self._current_subpath is None:
            return
        if not self._current_subpath:
            return
        if self._current_subpath[-1][0] != "Z":
            self._current_subpath.append(("Z",))

    def _reset_path(self) -> None:
        self._subpaths = []
        self._current_subpath = None

    def _paint(self, *, stroke: bool, fill: bool, even_odd: bool) -> None:
        """Paint the current path with the requested mode and reset it.

        aggdraw's path fill rule is non-zero. For even-odd fills we fall
        back to flattening Beziers and using PIL's :class:`ImageDraw` with
        an XOR mask (PIL polygons fill even-odd by default).
        """
        if not self._subpaths:
            return
        if self._draw is None or self._image is None:
            return

        if fill and even_odd:
            self._fill_even_odd_via_pil()
            stroke_only = stroke
            fill = False
            if stroke_only:
                self._stroke_via_aggdraw()
            self._reset_path()
            return

        if stroke or fill:
            self._draw_via_aggdraw(stroke=stroke, fill=fill)
        self._reset_path()

    def _draw_via_aggdraw(self, *, stroke: bool, fill: bool) -> None:
        assert self._draw is not None
        path = aggdraw.Path()
        any_segments = False
        for subpath in self._subpaths:
            for seg in subpath:
                tag = seg[0]
                if tag == "M":
                    path.moveto(seg[1], seg[2])
                    any_segments = True
                elif tag == "L":
                    path.lineto(seg[1], seg[2])
                    any_segments = True
                elif tag == "C":
                    path.curveto(
                        seg[1], seg[2], seg[3], seg[4], seg[5], seg[6]
                    )
                    any_segments = True
                elif tag == "Z":
                    path.close()
        if not any_segments:
            return
        self._draw.settransform(_to_pil_affine(self._full_ctm()))
        try:
            pen: aggdraw.Pen | None = None
            brush: aggdraw.Brush | None = None
            if stroke:
                # Convert PDF user-space line width to device-pixel width
                # so thin strokes don't disappear at sub-pixel widths.
                # Use a representative scale factor (sqrt(|det(CTM)|)).
                scale = self._approx_scale(self._full_ctm())
                width_px = max(1.0, self._gs.line_width * scale)
                pen = aggdraw.Pen(self._gs.stroke_rgb, width=width_px)
            if fill:
                brush = aggdraw.Brush(self._gs.fill_rgb)
            self._draw.path(path, pen, brush)
        finally:
            # aggdraw resets the transform when settransform is called
            # with no args (the documented "omitted" form).
            self._draw.settransform()

    def _stroke_via_aggdraw(self) -> None:
        self._draw_via_aggdraw(stroke=True, fill=False)

    @staticmethod
    def _approx_scale(m: _Matrix) -> float:
        a, b, c, d, _e, _f = m
        det = abs(a * d - b * c)
        return det**0.5 if det > 0 else 1.0

    def _fill_even_odd_via_pil(self) -> None:
        """Render an even-odd filled path by flattening Beziers and using
        PIL's :class:`ImageDraw`. PIL polygons honour the even-odd rule
        when subpaths overlap; the resulting non-AA mask is then alpha-
        composited onto the aggdraw canvas to preserve the surrounding
        anti-aliased content. v1: mask is binary (no edge AA on the
        even-odd specifically) — a documented limitation.
        """
        from PIL import ImageDraw  # noqa: PLC0415

        assert self._image is not None
        assert self._draw is not None
        # Commit any pending aggdraw operations before reading back the
        # underlying PIL image.
        self._draw.flush()

        ctm = self._full_ctm()
        # Build a binary mask containing every closed subpath. Even-odd
        # winding emerges by XOR-merging each subpath's individual mask
        # via ``ImageChops.logical_xor`` (which requires 1-bit ``"1"``
        # mode images). Where overlapping subpaths share a pixel, the
        # XOR cancels them out — exactly the even-odd "hole" effect.
        from PIL import ImageChops  # noqa: PLC0415

        width_px, height_px = self._image.size
        accumulator = Image.new("1", (width_px, height_px), 0)
        for subpath in self._subpaths:
            polygon = self._flatten_subpath_to_device(subpath, ctm)
            if len(polygon) < 3:
                continue
            sub_mask = Image.new("1", (width_px, height_px), 0)
            sdraw = ImageDraw.Draw(sub_mask)
            sdraw.polygon(polygon, fill=1, outline=1)
            accumulator = ImageChops.logical_xor(accumulator, sub_mask)

        # Promote to L for paste mask (PIL paste accepts L or 1; explicit
        # convert keeps the type predictable for downstream observers).
        mask = accumulator.convert("L")

        # Composite: paste fill_rgb wherever mask != 0.
        fill_layer = Image.new("RGB", (width_px, height_px), self._gs.fill_rgb)
        self._image.paste(fill_layer, (0, 0), mask)

        # The aggdraw Draw object holds onto the PIL buffer it was created
        # with — refresh by creating a new wrapper so subsequent operators
        # see the freshly composited pixels.
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _flatten_subpath_to_device(
        self, subpath: list[tuple], ctm: _Matrix
    ) -> list[tuple[float, float]]:
        """Flatten a single subpath to a polygon in device pixels. Beziers
        are sampled with 16 steps (good enough for v1 even-odd hole
        renders; real flatness control lands with the curve-flatten
        cluster)."""
        a, b, c, d, e, f = ctm
        out: list[tuple[float, float]] = []
        last = (0.0, 0.0)
        for seg in subpath:
            tag = seg[0]
            if tag == "M":
                pt = self._apply((seg[1], seg[2]), (a, b, c, d, e, f))
                out.append(pt)
                last = (seg[1], seg[2])
            elif tag == "L":
                pt = self._apply((seg[1], seg[2]), (a, b, c, d, e, f))
                out.append(pt)
                last = (seg[1], seg[2])
            elif tag == "C":
                x0, y0 = last
                x1, y1, x2, y2, x3, y3 = seg[1:7]
                steps = 16
                for i in range(1, steps + 1):
                    t = i / steps
                    bx, by = _bezier_point(x0, y0, x1, y1, x2, y2, x3, y3, t)
                    out.append(self._apply((bx, by), (a, b, c, d, e, f)))
                last = (x3, y3)
            # "Z" — closing edge handled implicitly by polygon
        return out

    @staticmethod
    def _apply(
        pt: tuple[float, float], m: _Matrix
    ) -> tuple[float, float]:
        x, y = pt
        a, b, c, d, e, f = m
        return (a * x + c * y + e, b * x + d * y + f)

    # ---- image XObject ----

    def _op_do(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands or not isinstance(operands[0], COSName):
            return
        if self._draw is None or self._image is None:
            return
        name: COSName = operands[0]
        resources = self._resources
        if resources is None:
            return
        try:
            xobject = resources.get_x_object(name)
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: cannot resolve XObject %s: %s", name.name, exc)
            return
        if xobject is None:
            return
        # Only image XObjects are handled in v1; form XObjects are deferred.
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        if not isinstance(xobject, PDImageXObject):
            return
        try:
            pil_image = self._decode_image_xobject(xobject)
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: cannot decode image: %s", exc)
            return
        if pil_image is None:
            return
        self._paste_image(pil_image)

    def _decode_image_xobject(self, image: Any) -> Image.Image | None:
        """Decode a :class:`PDImageXObject` into a PIL image. v1 supports:

        - JPEG images (``/Filter /DCTDecode``) — opened via PIL directly
          off the still-encoded bytes (PDStream stops the filter chain at
          DCTDecode automatically).
        - Raw 8-bit-per-component DeviceRGB / DeviceGray rasters — built
          from the fully-decoded byte body.

        Anything else (CCITT, JBIG2, JPX lossless, indexed, masks) is left
        to later clusters; we return ``None`` and the caller skips the
        paste."""
        cos = image.get_cos_object()
        if not isinstance(cos, COSStream):
            return None
        filters = cos.get_filter_list()
        filter_names = {f.name for f in filters}
        width = image.get_width()
        height = image.get_height()
        if width <= 0 or height <= 0:
            return None

        # JPEG — let PIL open the still-encoded bytes directly. We stop
        # the filter chain at DCTDecode so the JPEG payload arrives
        # verbatim (PDStream's stop_filters semantics — see CHANGES.md
        # for the COSStream filter pipeline.)
        if "DCTDecode" in filter_names:
            with image.create_input_stream(stop_filters=["DCTDecode"]) as src:
                data = src.read()
            return Image.open(io.BytesIO(data)).convert("RGB")
        if "JPXDecode" in filter_names:
            with image.create_input_stream(stop_filters=["JPXDecode"]) as src:
                data = src.read()
            return Image.open(io.BytesIO(data)).convert("RGB")

        # Raw raster path: 8 bpc DeviceRGB or DeviceGray only.
        bpc = image.get_bits_per_component()
        if bpc not in (8, -1):  # -1 means absent → assume 8
            return None
        cs_name = image.get_color_space()
        cs = cs_name.name if cs_name is not None else None
        with image.create_input_stream() as src:
            data = src.read()
        if cs == "DeviceRGB" or (cs is None and len(data) >= width * height * 3):
            return Image.frombytes("RGB", (width, height), data[: width * height * 3])
        if cs == "DeviceGray":
            return Image.frombytes("L", (width, height), data[: width * height]).convert(
                "RGB"
            )
        return None

    def _paste_image(self, pil_image: Image.Image) -> None:
        """Paste ``pil_image`` onto the canvas honouring the current CTM.

        Per PDF spec §8.9.5, the image XObject occupies the unit square
        [0,1]×[0,1] in user space; the ``cm`` operator that precedes ``Do``
        scales it into the desired bounding box.
        """
        assert self._image is not None
        assert self._draw is not None
        # Need to commit any pending aggdraw drawing before pasting.
        self._draw.flush()

        ctm = self._full_ctm()
        # The four corners of the unit square mapped to device space:
        corners = [
            self._apply((0.0, 0.0), ctm),
            self._apply((1.0, 0.0), ctm),
            self._apply((1.0, 1.0), ctm),
            self._apply((0.0, 1.0), ctm),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        x0 = int(round(min(xs)))
        y0 = int(round(min(ys)))
        x1 = int(round(max(xs)))
        y1 = int(round(max(ys)))
        target_w = max(1, x1 - x0)
        target_h = max(1, y1 - y0)
        # PDF images live in a flipped-y unit square (origin top-left in
        # image space, bottom-left in user space). The CTM y-flip baked
        # into device CTM already inverts it back, but we still need to
        # vertically mirror the source so the visible result matches
        # PDFBox's renderer.
        resized = pil_image.resize((target_w, target_h), Image.BILINEAR)
        flipped = resized.transpose(Image.FLIP_TOP_BOTTOM)
        self._image.paste(flipped, (x0, y0))

        # Re-attach the aggdraw wrapper so further drawing sees the new
        # pixels.
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)


def _bezier_point(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
    t: float,
) -> tuple[float, float]:
    """De Casteljau evaluation of a cubic Bezier at parameter ``t``."""
    u = 1.0 - t
    b0 = u * u * u
    b1 = 3 * u * u * t
    b2 = 3 * u * t * t
    b3 = t * t * t
    x = b0 * x0 + b1 * x1 + b2 * x2 + b3 * x3
    y = b0 * y0 + b1 * y1 + b2 * y2 + b3 * y3
    return (x, y)


# Operator-name → bound-method-name dispatch. Built after the class so we
# can reference unbound methods directly. Only operators we actively model
# appear here; everything else is silently dropped by ``process_operator``.
_DISPATCH: dict[str, Any] = {
    # graphics state
    "q": PDFRenderer._op_save,
    "Q": PDFRenderer._op_restore,
    "cm": PDFRenderer._op_concat_matrix,
    "w": PDFRenderer._op_line_width,
    # colour
    "RG": PDFRenderer._op_set_stroke_rgb,
    "rg": PDFRenderer._op_set_fill_rgb,
    "G": PDFRenderer._op_set_stroke_gray,
    "g": PDFRenderer._op_set_fill_gray,
    "K": PDFRenderer._op_set_stroke_cmyk,
    "k": PDFRenderer._op_set_fill_cmyk,
    # path construction
    "m": PDFRenderer._op_move_to,
    "l": PDFRenderer._op_line_to,
    "c": PDFRenderer._op_curve_to,
    "v": PDFRenderer._op_curve_to_v,
    "y": PDFRenderer._op_curve_to_y,
    "re": PDFRenderer._op_rect,
    "h": PDFRenderer._op_close_path,
    # painting
    "S": PDFRenderer._op_stroke,
    "s": PDFRenderer._op_close_and_stroke,
    "f": PDFRenderer._op_fill,
    "F": PDFRenderer._op_fill,  # PDF 1.0 alias
    "f*": PDFRenderer._op_fill_even_odd,
    "B": PDFRenderer._op_fill_then_stroke,
    "B*": PDFRenderer._op_fill_then_stroke_even_odd,
    "b": PDFRenderer._op_close_fill_then_stroke,
    "b*": PDFRenderer._op_close_fill_then_stroke_even_odd,
    "n": PDFRenderer._op_end_path,
    # image XObject
    "Do": PDFRenderer._op_do,
}


__all__ = ["PDFRenderer"]
