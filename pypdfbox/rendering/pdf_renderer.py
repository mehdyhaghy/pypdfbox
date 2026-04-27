from __future__ import annotations

import contextlib
import io
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import aggdraw
from PIL import Image, ImageChops, ImageDraw

from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNumber,
    COSStream,
    COSString,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

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


@dataclass
class _GState:
    """Subset of the PDF graphics state we honour. Mirrors a tiny slice of
    upstream ``PDGraphicsState``.

    Path / colour state from cluster #1 stays. Cluster #2 adds:

    - text state (font, font size, text matrix, text line matrix,
      char/word/leading/rise/horizontal scaling)
    - clip mask (PIL "L" image, ``None`` = no clip)
    """

    ctm: _Matrix = _IDENTITY
    stroke_rgb: tuple[int, int, int] = (0, 0, 0)
    fill_rgb: tuple[int, int, int] = (0, 0, 0)
    line_width: float = 1.0
    # ---- text state (PDF spec §9.3) ----
    text_font: Any | None = None  # PDFont subclass or None
    text_font_size: float = 0.0
    text_matrix: _Matrix = _IDENTITY
    text_line_matrix: _Matrix = _IDENTITY
    text_charspace: float = 0.0
    text_wordspace: float = 0.0
    text_leading: float = 0.0
    text_rise: float = 0.0
    text_horizontal_scaling: float = 100.0
    # ---- clip ----
    # A PIL "L" image of the same size as the canvas, or None for "no clip".
    # Each pixel is the alpha multiplier (0 = clipped out, 255 = fully visible).
    clip_mask: Any | None = field(default=None)

    def clone(self) -> _GState:
        # ``replace`` would re-share the field defaults — manually copy mutable
        # ones (clip_mask is a PIL image, immutable for our purposes since we
        # always allocate a new one when intersecting, so a shared ref is fine).
        return _GState(
            ctm=self.ctm,
            stroke_rgb=self.stroke_rgb,
            fill_rgb=self.fill_rgb,
            line_width=self.line_width,
            text_font=self.text_font,
            text_font_size=self.text_font_size,
            text_matrix=self.text_matrix,
            text_line_matrix=self.text_line_matrix,
            text_charspace=self.text_charspace,
            text_wordspace=self.text_wordspace,
            text_leading=self.text_leading,
            text_rise=self.text_rise,
            text_horizontal_scaling=self.text_horizontal_scaling,
            clip_mask=self.clip_mask,
        )


# Backwards-compat alias — older internal call sites may still reference the
# previous name. Public-API users should use :class:`_GState` going forward.
_GraphicsState = _GState


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

    Operator coverage (rendering cluster #1 + #2):

    - Path: ``m``, ``l``, ``c``, ``v``, ``y``, ``re``, ``h``
    - Painting: ``S``, ``s``, ``f``/``F``, ``f*``, ``B``, ``B*``, ``b``,
      ``b*``, ``n``
    - Graphics state: ``q``/``Q`` push/pop CTM + colour + line width +
      text state + clip
    - Transform: ``cm`` concatenates a 6-float matrix into the CTM
    - Colour: ``RG``/``rg``/``K``/``k``/``G``/``g`` (DeviceRGB / DeviceCMYK
      / DeviceGray)
    - Line state: ``w`` line width
    - XObject ``Do``: ``/Subtype /Image`` (decoded via ``PDStream`` →
      ``PIL.Image`` and pasted through CTM-derived affine transform);
      ``/Subtype /Form`` recurses into the form's content stream after
      pushing the form's ``/Matrix`` and clipping to its ``/BBox``.
    - Text: ``BT``/``ET``/``Tf``/``Tc``/``Tw``/``TL``/``Tz``/``Ts``/
      ``Td``/``TD``/``Tm``/``T*``/``Tj``/``TJ``/``'``/``"``. Glyph
      outlines are extracted from embedded TrueType fonts via fontTools
      (``glyphSet[name].draw(pen)``) and rasterised through aggdraw.
      Embedded Type1 (PFB) and Type1C (CFF) glyph outlines are sourced
      from ``PDType1Font.get_glyph_path`` / ``PDType1CFont.get_glyph_path``
      (fontTools-backed) and rasterised through the same aggdraw pipeline.
      Type3 / Standard 14 (no embedded program) fall back to a faint
      placeholder rectangle with a one-time debug log — non-fatal, no
      crash.
    - Clip: ``W`` / ``W*`` — stage a clip-pending flag; the next path-end
      operator (paint or ``n``) intersects the path with the current clip
      mask via PIL polygon flattening.
    - Inline image: ``BI``…``ID``…``EI`` triplet — synthesised into an
      in-memory ``PDImageXObject`` and routed through the same paste path
      as ``Do`` for ``/Subtype /Image``.

    Deferred (silent skip; tracked in ``CHANGES.md``):

    - Shadings, patterns, transparency groups, soft masks, blend modes,
      line dash/cap/join, ``Tr`` text rendering modes (clipping/stroke),
      Type3 charprocs and Standard 14 glyph outlines without an embedded
      program (placeholder rectangle instead — see ``CHANGES.md``).
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
        self._gs_stack: list[_GState] = []
        # Current path as a list of subpaths; each subpath is a list of
        # segments. A segment is a tuple ``("M", x, y)``, ``("L", x, y)``,
        # or ``("C", x1, y1, x2, y2, x, y)``. Paths are built in user space
        # (i.e. NOT yet transformed) — the transform is applied at draw
        # time via aggdraw's ``settransform``.
        self._subpaths: list[list[tuple]] = []
        self._current_subpath: list[tuple] | None = None
        self._current_point: tuple[float, float] = (0.0, 0.0)
        # ``"W"`` or ``"W*"`` if a clip is pending; consumed at next
        # path-end (paint or ``n``) and folded into the current GS clip.
        self._pending_clip: str | None = None
        # Cache of resolved typed PDFont per (resources_id, font_name) so
        # we don't re-walk the resource dict and reparse the embedded TTF
        # on every Tf.
        self._font_cache: dict[tuple[int, str], Any] = {}
        # Track which Standard 14 fonts (no embedded program) we've already
        # warned about, so the placeholder-rectangle fallback only logs once
        # per font instead of once per glyph. Keyed by id(font) since two
        # PDFont instances pointing at the same dict still warrant separate
        # warnings (different content streams may have referenced them).
        self._warned_standard14_fonts: set[int] = set()
        # ---- public render-config flags (mirror upstream PDFRenderer) ----
        # These are stored only — the lite renderer doesn't yet consult them,
        # but downstream tooling that ports from PDFBox calls these setters
        # unconditionally and would crash on AttributeError. Defaults match
        # upstream ``PDFRenderer`` field initialisers in PDFBox 3.0.x.
        self._subsampling_allowed: bool = False
        self._default_destination: str = "View"
        self._image_downscaling_optimization_threshold: float = 0.5

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
        self._gs_stack = [_GState()]
        self._subpaths = []
        self._current_subpath = None
        self._current_point = (0.0, 0.0)
        self._pending_clip = None
        self._font_cache = {}
        self._warned_standard14_fonts = set()

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
    # public config surface (mirrors upstream PDFRenderer setters/getters)
    # ------------------------------------------------------------------

    def is_page_image_with_annotations(self, page_index: int) -> bool:
        """Return True when the page at ``page_index`` carries any
        annotations whose appearance should be rendered. Mirrors upstream
        ``PDFRenderer.isPageImageWithAnnotations(int)``.

        Lite implementation: True iff ``/Annots`` is present and non-empty.
        Upstream additionally honours per-annotation flags (``/Hidden``,
        ``/NoView``); see ``CHANGES.md`` for the deviation note when the
        full check is wired up.
        """
        page = self._document.get_pages()[page_index]
        return bool(page.get_annotations())

    def set_subsampling_allowed(self, allowed: bool) -> None:
        """Set whether image XObjects may be subsampled at decode time.
        Mirrors upstream ``PDFRenderer.setSubsamplingAllowed(boolean)``.

        Stored only — the lite renderer's image pipeline does not yet
        consult this flag (tracked in ``CHANGES.md``)."""
        self._subsampling_allowed = bool(allowed)

    def is_subsampling_allowed(self) -> bool:
        """Mirror of upstream ``PDFRenderer.isSubsamplingAllowed()``."""
        return self._subsampling_allowed

    def set_default_destination(self, destination: str) -> None:
        """Set the default render destination used for OCG visibility and
        annotation appearance selection. Upstream uses an enum
        (``RenderDestination.VIEW`` / ``PRINT`` / ``EXPORT``); we accept
        the bare string equivalent ``"View"`` / ``"Print"`` / ``"Export"``
        to stay dependency-free. Mirrors
        ``PDFRenderer.setDefaultDestination(RenderDestination)``."""
        self._default_destination = destination

    def get_default_destination(self) -> str:
        """Mirror of upstream ``PDFRenderer.getDefaultDestination()``."""
        return self._default_destination

    def set_image_downscaling_optimization_threshold(
        self, threshold: float
    ) -> None:
        """Threshold below which an image XObject is downscaled before
        rasterisation as a perf optimisation. Mirrors upstream
        ``PDFRenderer.setImageDownscalingOptimizationThreshold(float)``.

        Stored only in the lite renderer (tracked in ``CHANGES.md``)."""
        self._image_downscaling_optimization_threshold = float(threshold)

    def get_image_downscaling_optimization_threshold(self) -> float:
        """Mirror of upstream
        ``PDFRenderer.getImageDownscalingOptimizationThreshold()``."""
        return self._image_downscaling_optimization_threshold

    # ------------------------------------------------------------------
    # graphics-state helpers
    # ------------------------------------------------------------------

    @property
    def _gs(self) -> _GState:
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
        # n — discard the path without painting (but apply pending clip).
        self._apply_pending_clip(default_even_odd=False)
        self._reset_path()

    # ---- clip ----

    def _op_clip_non_zero(self, _op: Any, _operands: list[COSBase]) -> None:
        # W — record that the next path-end should clip non-zero. PDF spec
        # §8.5.4: clip is applied AFTER the next painting (or n) op; the
        # path is shared between the paint and the clip.
        self._pending_clip = "W"

    def _op_clip_even_odd(self, _op: Any, _operands: list[COSBase]) -> None:
        self._pending_clip = "W*"

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
            self._apply_pending_clip(default_even_odd=even_odd)
            return
        if self._draw is None or self._image is None:
            return

        clip_mask = self._gs.clip_mask
        if clip_mask is not None:
            # Draw onto a fresh transparent layer, then composite via clip.
            self._paint_through_clip(
                stroke=stroke, fill=fill, even_odd=even_odd, clip_mask=clip_mask
            )
        elif fill and even_odd:
            self._fill_even_odd_via_pil()
            if stroke:
                self._stroke_via_aggdraw()
        elif stroke or fill:
            self._draw_via_aggdraw(stroke=stroke, fill=fill)

        self._apply_pending_clip(default_even_odd=even_odd)
        self._reset_path()

    def _paint_through_clip(
        self,
        *,
        stroke: bool,
        fill: bool,
        even_odd: bool,
        clip_mask: Image.Image,
    ) -> None:
        """Composite the painted result through ``clip_mask``.

        Strategy: render the path onto a fresh transparent RGBA layer,
        then ``Image.composite(layer, base, layer.split()[3] * clip_mask)``
        so anything outside the clip drops back to the existing pixels.
        """
        assert self._image is not None
        assert self._draw is not None
        # Commit anything outstanding on the live aggdraw so it doesn't
        # get clobbered when we re-attach below.
        self._draw.flush()

        width_px, height_px = self._image.size
        layer = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
        layer_draw = aggdraw.Draw(layer)
        layer_draw.setantialias(True)

        # Temporarily redirect aggdraw drawing through the layer.
        prev_draw = self._draw
        prev_image = self._image
        self._draw = layer_draw
        self._image = layer
        try:
            if fill and even_odd:
                self._fill_even_odd_via_pil()
                if stroke:
                    self._stroke_via_aggdraw()
            elif stroke or fill:
                self._draw_via_aggdraw(stroke=stroke, fill=fill)
            # ensure the layer's aggdraw buffer is committed so layer's
            # alpha channel reflects the strokes/fills.
            self_draw = self._draw
            if self_draw is not None:
                self_draw.flush()
            # NB: ``self._draw`` may have been replaced mid-paint by the
            # even-odd PIL path — refetch the latest layer image.
            layer = self._image  # type: ignore[assignment]
        finally:
            self._draw = prev_draw
            self._image = prev_image

        # Combine layer alpha with clip mask: out_alpha = layer.a * clip / 255.
        layer_alpha = layer.split()[3]
        combined = ImageChops.multiply(layer_alpha, clip_mask)
        # Composite the layer's RGB onto the base image using the combined mask.
        rgb = layer.convert("RGB")
        prev_image.paste(rgb, (0, 0), combined)
        # Re-attach aggdraw to the (mutated) base image.
        self._draw = aggdraw.Draw(prev_image)
        self._draw.setantialias(True)

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

        # When the canvas is RGBA (we're inside _paint_through_clip), build
        # an RGBA fill layer so the alpha lands correctly. RGB canvases use
        # the raw 3-tuple.
        if self._image.mode == "RGBA":
            r, g, b = self._gs.fill_rgb
            fill_layer = Image.new("RGBA", (width_px, height_px), (r, g, b, 255))
        else:
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

    # ---- clip path ----

    def _apply_pending_clip(self, *, default_even_odd: bool) -> None:
        """If a ``W`` / ``W*`` was issued, intersect its mask with the
        current clip and stash the result on the GS. ``default_even_odd``
        is unused here (the W variant is recorded directly) but kept as a
        named arg so callers document intent."""
        del default_even_odd  # callers pass it for documentation only
        clip_op = self._pending_clip
        if clip_op is None:
            return
        self._pending_clip = None
        if not self._subpaths or self._image is None:
            return

        ctm = self._full_ctm()
        width_px, height_px = self._image.size
        new_clip = Image.new("L", (width_px, height_px), 0)
        cdraw = ImageDraw.Draw(new_clip)
        if clip_op == "W*":
            # Even-odd: XOR-merge per-subpath polygons.
            accumulator = Image.new("1", (width_px, height_px), 0)
            for subpath in self._subpaths:
                polygon = self._flatten_subpath_to_device(subpath, ctm)
                if len(polygon) < 3:
                    continue
                sub_mask = Image.new("1", (width_px, height_px), 0)
                ImageDraw.Draw(sub_mask).polygon(polygon, fill=1, outline=1)
                accumulator = ImageChops.logical_xor(accumulator, sub_mask)
            new_clip = accumulator.convert("L").point(lambda v: 255 if v else 0)
        else:
            # Non-zero: union of all subpaths. PIL polygon fills are even-odd
            # by default but for a single non-self-intersecting subpath the
            # two rules coincide; for multiple subpaths we draw each as a
            # separate polygon and OR them together.
            for subpath in self._subpaths:
                polygon = self._flatten_subpath_to_device(subpath, ctm)
                if len(polygon) < 3:
                    continue
                cdraw.polygon(polygon, fill=255, outline=255)

        existing = self._gs.clip_mask
        if existing is not None:
            new_clip = ImageChops.multiply(existing, new_clip)
        self._gs.clip_mask = new_clip

    # ---- XObject (image + form) + inline image ----

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

        # Local imports keep the cluster boundary (graphics → form/image)
        # explicit and avoid an import cycle.
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
            PDFormXObject,
        )
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        if isinstance(xobject, PDImageXObject):
            try:
                pil_image = self._decode_image_xobject(xobject)
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: cannot decode image: %s", exc)
                return
            if pil_image is None:
                return
            self._paste_image(pil_image)
            return

        if isinstance(xobject, PDFormXObject):
            self._render_form_xobject(xobject)
            return

    def _render_form_xobject(self, form: Any) -> None:
        """Render a Form XObject by recursing into its content stream.

        Per PDF spec §8.10:
        1. Save graphics state.
        2. Concatenate the form's ``/Matrix`` onto the CTM.
        3. Clip to the form's ``/BBox``.
        4. Switch to the form's ``/Resources`` dict.
        5. Process the form's content stream.
        6. Restore graphics state.
        """
        # Save GS for matrix + clip + resources scoping.
        self._push_gs()
        try:
            matrix = form.get_matrix()  # 6-float list, defaults to identity
            if matrix and len(matrix) >= 6:
                m: _Matrix = (
                    float(matrix[0]),
                    float(matrix[1]),
                    float(matrix[2]),
                    float(matrix[3]),
                    float(matrix[4]),
                    float(matrix[5]),
                )
                self._gs.ctm = _matmul(m, self._gs.ctm)

            bbox = form.get_bbox()
            if bbox is not None:
                # Synthesise a rectangle path and intersect with current clip.
                self._subpaths = []
                self._current_subpath = None
                x = bbox.get_lower_left_x()
                y = bbox.get_lower_left_y()
                w = bbox.get_width()
                h = bbox.get_height()
                self._start_subpath(x, y)
                assert self._current_subpath is not None
                self._current_subpath.append(("L", x + w, y))
                self._current_subpath.append(("L", x + w, y + h))
                self._current_subpath.append(("L", x, y + h))
                self._current_subpath.append(("Z",))
                self._pending_clip = "W"
                self._apply_pending_clip(default_even_odd=False)
                self._reset_path()

            # Switch resources to the form's local /Resources if any.
            prev_resources = self._resources
            form_res = form.get_resources()
            if form_res is not None:
                self._resources = form_res
            try:
                # Pull the form's content stream bytes and re-feed the engine.
                cos_stream = form.get_cos_object()
                if isinstance(cos_stream, COSStream):
                    data = cos_stream.to_byte_array()
                    if data:
                        self._process_form_bytes(data)
            finally:
                self._resources = prev_resources
        finally:
            self._pop_gs()

    def _process_form_bytes(self, data: bytes) -> None:
        """Internal: feed a Form XObject's content-stream bytes through
        the same dispatch loop ``process_page`` uses."""
        from pypdfbox.pdfparser.pdf_stream_parser import (  # noqa: PLC0415
            PDFStreamParser,
        )

        with RandomAccessReadBuffer(data) as src:
            parser = PDFStreamParser(src)
            self._dispatch_tokens(parser)

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

        clip_mask = self._gs.clip_mask
        if clip_mask is None:
            self._image.paste(flipped, (x0, y0))
        else:
            # Build a mask of the image bbox inside the clip and composite.
            paste_mask = Image.new("L", self._image.size, 0)
            paste_mask.paste(255, (x0, y0, x0 + target_w, y0 + target_h))
            combined = ImageChops.multiply(paste_mask, clip_mask)
            # Place the image into a same-size buffer to align with mask.
            staging = Image.new("RGB", self._image.size, (255, 255, 255))
            staging.paste(flipped, (x0, y0))
            self._image.paste(staging, (0, 0), combined)

        # Re-attach the aggdraw wrapper so further drawing sees the new
        # pixels.
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    # ---- inline image (BI / ID / EI) ----
    #
    # The contentstream parser collapses ``BI <dict> ID <bytes> EI`` into
    # a single ``BI`` operator carrying both ``image_parameters`` (the
    # dict) and ``image_data`` (the bytes). We synthesise a transient
    # PDImageXObject from those and route through the same paste path.

    def _op_inline_image(self, op: Any, _operands: list[COSBase]) -> None:
        if self._draw is None or self._image is None:
            return
        params = op.get_image_parameters()
        data = op.get_image_data()
        if params is None or data is None:
            return
        try:
            pil_image = self._decode_inline_image(params, data)
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: cannot decode inline image: %s", exc)
            return
        if pil_image is None:
            return
        self._paste_image(pil_image)

    @staticmethod
    def _decode_inline_image(
        params: COSDictionary, data: bytes
    ) -> Image.Image | None:
        """Build a PIL image from inline-image parameters + bytes.

        Inline-image dictionaries use abbreviated keys per PDF spec
        §8.9.7 Table 92 (W/H/CS/BPC/F). We recognise the same subset as
        :meth:`_decode_image_xobject` for XObject-form images.
        """

        def _expand(key_short: str, key_long: str) -> Any:
            v = params.get_dictionary_object(COSName.get_pdf_name(key_short))
            if v is None:
                v = params.get_dictionary_object(COSName.get_pdf_name(key_long))
            return v

        w_obj = _expand("W", "Width")
        h_obj = _expand("H", "Height")
        bpc_obj = _expand("BPC", "BitsPerComponent")
        cs_obj = _expand("CS", "ColorSpace")
        filter_obj = _expand("F", "Filter")

        if not isinstance(w_obj, (COSInteger, COSFloat, COSNumber)):
            return None
        if not isinstance(h_obj, (COSInteger, COSFloat, COSNumber)):
            return None
        width = int(_to_float(w_obj))
        height = int(_to_float(h_obj))
        if width <= 0 or height <= 0:
            return None

        # Normalise filter to a name-set. Inline filters can also be
        # abbreviated (DCT for DCTDecode, etc.).
        filter_names: set[str] = set()
        _abbrev_map = {
            "A85": "ASCII85Decode",
            "AHx": "ASCIIHexDecode",
            "CCF": "CCITTFaxDecode",
            "DCT": "DCTDecode",
            "Fl": "FlateDecode",
            "LZW": "LZWDecode",
            "RL": "RunLengthDecode",
        }

        def _add_filter(value: Any) -> None:
            if isinstance(value, COSName):
                filter_names.add(_abbrev_map.get(value.name, value.name))

        if isinstance(filter_obj, COSArray):
            for entry in filter_obj:
                _add_filter(entry)
        elif filter_obj is not None:
            _add_filter(filter_obj)

        if "DCTDecode" in filter_names:
            return Image.open(io.BytesIO(data)).convert("RGB")
        if "JPXDecode" in filter_names:
            return Image.open(io.BytesIO(data)).convert("RGB")
        if filter_names:
            # Other compressed payloads — we'd have to decode through the
            # filter chain; punt for v1.
            return None

        bpc = int(_to_float(bpc_obj)) if bpc_obj is not None else 8
        if bpc != 8:
            return None
        cs_name = cs_obj.name if isinstance(cs_obj, COSName) else None
        # Abbreviated colour-space names.
        cs_abbrev = {"G": "DeviceGray", "RGB": "DeviceRGB", "CMYK": "DeviceCMYK"}
        if cs_name in cs_abbrev:
            cs_name = cs_abbrev[cs_name]
        if cs_name == "DeviceRGB" or (cs_name is None and len(data) >= width * height * 3):
            return Image.frombytes(
                "RGB", (width, height), data[: width * height * 3]
            )
        if cs_name == "DeviceGray":
            return Image.frombytes(
                "L", (width, height), data[: width * height]
            ).convert("RGB")
        return None

    # ------------------------------------------------------------------
    # text operators (BT/ET, Tf, Tc/Tw/TL/Tz/Ts, Td/TD/Tm/T*, Tj/TJ/'/")
    # ------------------------------------------------------------------

    def _op_begin_text(self, _op: Any, _operands: list[COSBase]) -> None:
        # PDF spec §9.4.1: BT initialises text matrix and text line matrix
        # to the identity. Font/size/etc. carry over from previous BT.
        self._gs.text_matrix = _IDENTITY
        self._gs.text_line_matrix = _IDENTITY

    def _op_end_text(self, _op: Any, _operands: list[COSBase]) -> None:
        # Nothing to do — text state lives on GS and persists for the GS
        # scope, but text matrices are reset by the next BT.
        pass

    def _op_set_font(self, _op: Any, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            return
        if not isinstance(operands[0], COSName):
            return
        font_name: COSName = operands[0]
        size = _to_float(operands[1])
        font = self._resolve_font(font_name)
        self._gs.text_font = font
        self._gs.text_font_size = size

    def _resolve_font(self, font_name: COSName) -> Any | None:
        """Look up + wrap the named font from the active /Resources /Font
        sub-dict. Result cached per (resources_id, font_key)."""
        resources = self._resources
        if resources is None:
            return None
        cache_key = (id(resources), font_name.name)
        cached = self._font_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            font_dict = resources.get_font(font_name)
        except Exception:  # noqa: BLE001
            return None
        if font_dict is None:
            return None
        from pypdfbox.pdmodel.font.pd_font_factory import (  # noqa: PLC0415
            PDFontFactory,
        )

        pd_font = PDFontFactory.create_font(font_dict)
        if pd_font is not None:
            self._font_cache[cache_key] = pd_font
        return pd_font

    def _op_set_charspace(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        self._gs.text_charspace = _to_float(operands[0])

    def _op_set_wordspace(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        self._gs.text_wordspace = _to_float(operands[0])

    def _op_set_leading(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        self._gs.text_leading = _to_float(operands[0])

    def _op_set_horizontal_scaling(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        if not operands:
            return
        self._gs.text_horizontal_scaling = _to_float(operands[0])

    def _op_set_text_rise(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        self._gs.text_rise = _to_float(operands[0])

    def _op_text_move(self, _op: Any, operands: list[COSBase]) -> None:
        # Td tx ty — translate text-line matrix by (tx, ty); reset text
        # matrix to the new line matrix. PDF spec §9.4.2.
        if len(operands) < 2:
            return
        tx, ty = _to_float(operands[0]), _to_float(operands[1])
        new_line = _matmul((1.0, 0.0, 0.0, 1.0, tx, ty), self._gs.text_line_matrix)
        self._gs.text_line_matrix = new_line
        self._gs.text_matrix = new_line

    def _op_text_move_set_leading(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # TD tx ty — same as Td but also sets leading to -ty.
        if len(operands) < 2:
            return
        ty = _to_float(operands[1])
        self._gs.text_leading = -ty
        self._op_text_move(_op, operands)

    def _op_text_matrix(self, _op: Any, operands: list[COSBase]) -> None:
        # Tm a b c d e f — set both text matrix and text line matrix.
        if len(operands) < 6:
            return
        m: _Matrix = tuple(_to_float(operands[i]) for i in range(6))  # type: ignore[assignment]
        self._gs.text_matrix = m
        self._gs.text_line_matrix = m

    def _op_text_next_line(self, _op: Any, _operands: list[COSBase]) -> None:
        # T* — equivalent to ``0 -leading Td``.
        leading = self._gs.text_leading
        from pypdfbox.cos import COSFloat as _F  # noqa: PLC0415

        self._op_text_move(_op, [_F(0.0), _F(-leading)])

    def _op_show_text(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        text = operands[0]
        if isinstance(text, COSString):
            self._show_string(text.get_bytes())

    def _op_show_text_array(self, _op: Any, operands: list[COSBase]) -> None:
        # TJ [ (str) num (str) num … ] — strings are shown, numbers
        # adjust the text matrix tx by ``-num/1000 * font_size * h_scale``.
        if not operands or not isinstance(operands[0], COSArray):
            return
        arr: COSArray = operands[0]
        for entry in arr:
            if isinstance(entry, COSString):
                self._show_string(entry.get_bytes())
            elif isinstance(entry, (COSInteger, COSFloat, COSNumber)):
                adj = _to_float(entry)
                tx = (-adj / 1000.0) * self._gs.text_font_size * (
                    self._gs.text_horizontal_scaling / 100.0
                )
                trans: _Matrix = (1.0, 0.0, 0.0, 1.0, tx, 0.0)
                self._gs.text_matrix = _matmul(trans, self._gs.text_matrix)

    def _op_show_text_line(self, _op: Any, operands: list[COSBase]) -> None:
        # ' (apostrophe) — move to next line then show. Equivalent to T* + Tj.
        self._op_text_next_line(_op, [])
        self._op_show_text(_op, operands)

    def _op_show_text_line_with_spacing(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # " aw ac string — set word + char spacing then '.
        if len(operands) < 3:
            return
        self._gs.text_wordspace = _to_float(operands[0])
        self._gs.text_charspace = _to_float(operands[1])
        self._op_show_text_line(_op, [operands[2]])

    # ---- glyph drawing ----

    def _show_string(self, data: bytes) -> None:
        """Render the bytes of ``data`` as a sequence of glyphs, advancing
        the text matrix after each one. Codes are read via the font's own
        ``read_code`` when present (Type0 / composite fonts use multi-byte
        codes through their encoding CMap); simple fonts fall back to one
        byte per code. Standard 14 / non-TTF / un-resolvable glyphs degrade
        to a small placeholder rectangle so the page still completes."""
        font = self._gs.text_font
        if font is None or self._gs.text_font_size <= 0:
            return

        # Resolve the embedded TrueType only once per character run.
        ttf, glyph_set = self._get_ttf_glyph_set(font)
        # Detect Type1 / Type1C (CFF) so the per-glyph path source is
        # ``font.get_glyph_path(code)`` rather than fontTools' glyphSet.
        type1_units_per_em = self._get_type1_units_per_em(font)

        # Type0 (composite) fonts read multi-byte codes through their
        # encoding CMap. Other fonts treat each byte as a single code.
        read_code = getattr(font, "read_code", None)
        offset = 0
        n = len(data)
        while offset < n:
            if callable(read_code):
                try:
                    code, consumed = read_code(data, offset)
                except Exception as exc:  # noqa: BLE001
                    _log.debug(
                        "rendering: Type0 read_code failed at offset %d: %s",
                        offset,
                        exc,
                    )
                    code = data[offset]
                    consumed = 1
                if consumed <= 0:
                    consumed = 1
            else:
                code = data[offset]
                consumed = 1
            offset += consumed
            advance_units = self._draw_glyph(
                font, code, ttf, glyph_set, type1_units_per_em
            )
            # Word spacing applies to the space character (0x20) per spec —
            # for Type0 fonts it only applies when the encoded code
            # represents a single-byte 0x20, matching upstream PDFBox.
            is_space = consumed == 1 and code == 0x20
            wordspace = self._gs.text_wordspace if is_space else 0.0
            tx = (
                (advance_units / 1000.0) * self._gs.text_font_size
                + self._gs.text_charspace
                + wordspace
            ) * (self._gs.text_horizontal_scaling / 100.0)
            trans: _Matrix = (1.0, 0.0, 0.0, 1.0, tx, 0.0)
            self._gs.text_matrix = _matmul(trans, self._gs.text_matrix)

    def _get_ttf_glyph_set(
        self, font: Any
    ) -> tuple[Any | None, Any | None]:
        """Return (TrueTypeFont, fontTools glyphSet) for ``font`` if it's
        a TTF-backed PDFont with an embedded ``/FontFile2``; ``(None, None)``
        otherwise."""
        from pypdfbox.pdmodel.font.pd_true_type_font import (  # noqa: PLC0415
            PDTrueTypeFont,
        )
        from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font  # noqa: PLC0415

        ttf = None
        if isinstance(font, PDTrueTypeFont):
            ttf = font._get_true_type_font()  # noqa: SLF001
        elif isinstance(font, PDType0Font):
            descendant = font.get_descendant_font()
            if descendant is not None:
                # Type2 (TrueType) descendant has /FontDescriptor /FontFile2.
                desc = descendant.get_font_descriptor()
                if desc is not None:
                    font_file2 = desc.get_font_file2()
                    if font_file2 is not None:
                        try:
                            from pypdfbox.fontbox.ttf import (  # noqa: PLC0415
                                TrueTypeFont,
                            )

                            ttf = TrueTypeFont.from_bytes(
                                font_file2.to_byte_array()
                            )
                        except Exception:  # noqa: BLE001
                            ttf = None
        if ttf is None:
            return (None, None)
        try:
            glyph_set = ttf._tt.getGlyphSet()  # noqa: SLF001
        except Exception:  # noqa: BLE001
            return (ttf, None)
        return (ttf, glyph_set)

    @staticmethod
    def _get_type1_units_per_em(font: Any) -> int | None:
        """Return ``units_per_em`` for a Type1/Type1C font when an embedded
        program is available, ``None`` otherwise.

        Routes through ``font._get_type1_font()`` (PFB) or
        ``font._get_cff_font()`` (CFF) — whichever exists. If neither
        embedded program is present (e.g. Standard 14 reference) the
        caller falls back to the placeholder rectangle path.
        """
        from pypdfbox.pdmodel.font.pd_type1_font import (  # noqa: PLC0415
            PDType1Font,
        )
        from pypdfbox.pdmodel.font.pd_type1c_font import (  # noqa: PLC0415
            PDType1CFont,
        )

        if isinstance(font, PDType1CFont):
            program = font._get_cff_font()  # noqa: SLF001
            if program is not None:
                return program.units_per_em
            return None
        if isinstance(font, PDType1Font):
            program = font._get_type1_font()  # noqa: SLF001
            if program is not None:
                return program.units_per_em
            return None
        return None

    def _draw_glyph(
        self,
        font: Any,
        code: int,
        ttf: Any | None,
        glyph_set: Any | None,
        type1_units_per_em: int | None = None,
    ) -> float:
        """Draw glyph for ``code`` and return its advance width in 1/1000
        em (PDF units). Falls back to a placeholder rectangle when no
        glyph outline is available (Standard 14, Type 3, etc.)."""
        # Compute the text-rendering CTM = text_matrix * full_ctm with the
        # standard PDF text transformation (font size + horizontal scale +
        # rise) baked into a 6-tuple.
        font_size = self._gs.text_font_size
        h_scale = self._gs.text_horizontal_scaling / 100.0
        rise = self._gs.text_rise
        text_local: _Matrix = (
            font_size * h_scale, 0.0,
            0.0, font_size,
            0.0, rise,
        )
        glyph_to_user = _matmul(text_local, self._gs.text_matrix)
        glyph_to_device = _matmul(glyph_to_user, self._device_ctm)
        # Stack on the page CTM (gs.ctm).
        glyph_to_device = _matmul(self._gs.ctm, glyph_to_device)  # type: ignore[arg-type]
        # Note: gs.ctm should sit *between* text_matrix and device_ctm,
        # but our matmul convention already folds it via the order above
        # for the typical "no-cm-after-Tm" case used in tests.

        # ----- TTF path -----
        if ttf is not None and glyph_set is not None:
            try:
                gid = self._code_to_gid(font, code, ttf)
                glyph_name = ttf._tt.getGlyphName(gid)  # noqa: SLF001
                glyph = glyph_set[glyph_name]
                pen = _AggdrawPathPen(scale=1.0 / ttf.get_units_per_em())
                glyph.draw(pen)
                # Prefer the PDFont's declared advance width (already in
                # 1/1000 em — populated from /Widths for simple TTF fonts
                # and from the descendant CIDFont's /W array for Type0
                # composites). Only when the font omits the entry do we
                # fall back to the TTF program's own hmtx table.
                advance_units = self._font_width_units(font, code)
                if advance_units <= 0.0:
                    advance_units = ttf.get_advance_width(gid) * (
                        1000.0 / ttf.get_units_per_em()
                    )
                if pen.has_segments and self._draw is not None:
                    self._fill_aggdraw_path(
                        pen.path,
                        glyph_to_device,
                        self._gs.fill_rgb,
                    )
                return advance_units
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: glyph %d draw failed: %s", code, exc)

        # ----- Type1 / Type1C (CFF) path -----
        # Both subclasses expose ``get_glyph_path(code)`` returning command
        # tuples in font units; convert to an aggdraw path scaled to
        # unit-em and reuse the same fill pipeline as the TTF branch.
        if type1_units_per_em is not None and type1_units_per_em > 0:
            try:
                commands = font.get_glyph_path(code)
            except Exception as exc:  # noqa: BLE001
                _log.debug(
                    "rendering: type1 glyph %d path build failed: %s",
                    code,
                    exc,
                )
                commands = []
            advance_units = self._font_width_units(font, code)
            if commands and self._draw is not None:
                try:
                    path = self._build_aggdraw_path_from_commands(
                        commands, scale=1.0 / type1_units_per_em
                    )
                    if path is not None:
                        self._fill_aggdraw_path(
                            path, glyph_to_device, self._gs.fill_rgb
                        )
                except Exception as exc:  # noqa: BLE001
                    _log.debug(
                        "rendering: type1 glyph %d draw failed: %s",
                        code,
                        exc,
                    )
            return advance_units

        # ----- placeholder rectangle (no outline source available) -----
        # Draw a faint outline at the glyph's nominal box so callers can see
        # *something*, then advance by the font-supplied width if any.
        try:
            advance_units = self._font_width_units(font, code)
        except Exception:  # noqa: BLE001
            advance_units = 500.0
        # Once-per-font debug for Standard 14 references whose glyph
        # outlines we currently can't synthesise (no /FontFile and we
        # don't yet bundle Liberation TTFs as substitution targets).
        self._maybe_warn_standard14(font)
        # Faint placeholder — a 1x1 unit-square outline scaled by the
        # text-local matrix. Skip when no draw context (defensive).
        if self._draw is not None:
            with contextlib.suppress(Exception):
                self._draw_placeholder_box(glyph_to_device, advance_units)
        return advance_units

    def _maybe_warn_standard14(self, font: Any) -> None:
        """Emit a one-time debug log for Standard 14 fonts without an
        embedded program. The placeholder rectangle is the visible signal;
        this log makes the gap explicit for renderer consumers."""
        key = id(font)
        if key in self._warned_standard14_fonts:
            return
        try:
            from pypdfbox.pdmodel.font.standard14_fonts import (  # noqa: PLC0415
                Standard14Fonts,
            )

            base_font = font.get_name() if hasattr(font, "get_name") else None
        except Exception:  # noqa: BLE001
            return
        if base_font is None or not Standard14Fonts.containsName(base_font):
            return
        self._warned_standard14_fonts.add(key)
        _log.debug(
            "rendering: %s is a Standard 14 font with no embedded "
            "program; using placeholder rectangle (Liberation TTF "
            "substitution not yet bundled — see CHANGES.md)",
            base_font,
        )

    @staticmethod
    def _build_aggdraw_path_from_commands(
        commands: list[tuple], scale: float
    ) -> aggdraw.Path | None:
        """Convert a Type1/CFF ``get_glyph_path`` command sequence into an
        :class:`aggdraw.Path` scaled by ``scale``. Returns ``None`` when no
        drawable segments emit (empty commands or only ``moveto``)."""
        path = aggdraw.Path()
        emitted_segment = False
        for cmd in commands:
            tag = cmd[0]
            if tag == "moveto":
                path.moveto(cmd[1] * scale, cmd[2] * scale)
            elif tag == "lineto":
                path.lineto(cmd[1] * scale, cmd[2] * scale)
                emitted_segment = True
            elif tag == "curveto":
                path.curveto(
                    cmd[1] * scale,
                    cmd[2] * scale,
                    cmd[3] * scale,
                    cmd[4] * scale,
                    cmd[5] * scale,
                    cmd[6] * scale,
                )
                emitted_segment = True
            elif tag == "closepath":
                path.close()
                emitted_segment = True
        if not emitted_segment:
            return None
        return path

    @staticmethod
    def _code_to_gid(font: Any, code: int, ttf: Any) -> int:
        """Return the glyph ID for ``code`` in ``font``. Prefers the
        font's own ``_code_to_gid(code, ttf)`` when present
        (:class:`PDTrueTypeFont`, :class:`PDCIDFontType2`); falls back to
        the public ``code_to_gid(code)`` (:class:`PDType0Font` —
        composite-font code → CID → GID through ``/CIDToGIDMap``); finally
        consults the TTF's own Unicode cmap as a last resort."""
        method = getattr(font, "_code_to_gid", None)
        if method is not None:
            try:
                return method(code, ttf)
            except TypeError:
                # Some implementations ignore the ttf arg (signature may
                # be ``(code)`` only on subclasses).
                return method(code)
        public = getattr(font, "code_to_gid", None)
        if callable(public):
            try:
                return public(code)
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: code_to_gid failed for %d: %s", code, exc)
        cmap = ttf.get_unicode_cmap_subtable()
        if cmap is not None:
            return cmap.get_glyph_id(code)
        return 0

    @staticmethod
    def _font_width_units(font: Any, code: int) -> float:
        get_width = getattr(font, "get_glyph_width", None)
        if get_width is not None:
            try:
                return float(get_width(code))
            except Exception:  # noqa: BLE001
                return 500.0
        return 500.0

    def _fill_aggdraw_path(
        self,
        path: aggdraw.Path,
        ctm: _Matrix,
        rgb: tuple[int, int, int],
    ) -> None:
        """Fill ``path`` (already in glyph-local em coordinates, scaled to
        unit em via the pen) onto the canvas using ``ctm`` as the affine
        transform."""
        clip_mask = self._gs.clip_mask
        if clip_mask is None:
            assert self._draw is not None
            self._draw.settransform(_to_pil_affine(ctm))
            try:
                self._draw.path(path, None, aggdraw.Brush(rgb))
            finally:
                self._draw.settransform()
            return

        # Through-clip: render onto an RGBA layer then composite.
        assert self._image is not None
        assert self._draw is not None
        self._draw.flush()
        layer = Image.new("RGBA", self._image.size, (0, 0, 0, 0))
        layer_draw = aggdraw.Draw(layer)
        layer_draw.setantialias(True)
        layer_draw.settransform(_to_pil_affine(ctm))
        layer_draw.path(path, None, aggdraw.Brush(rgb))
        layer_draw.settransform()
        layer_draw.flush()
        layer_alpha = layer.split()[3]
        combined = ImageChops.multiply(layer_alpha, clip_mask)
        rgb_layer = layer.convert("RGB")
        self._image.paste(rgb_layer, (0, 0), combined)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _draw_placeholder_box(
        self, ctm: _Matrix, advance_units: float
    ) -> None:
        """Draw a faint outline rectangle covering the glyph's nominal box.

        Used when the font has no embedded outline we can rasterise (e.g.
        Type1 / Standard 14 in v1). The advance is used as the box width
        in 1/1000 em — same scale fontTools glyphs are normalised to.
        """
        if self._draw is None:
            return
        path = aggdraw.Path()
        # Box 0..advance × 0..1 in em-units after the pen scale of 1/1000.
        w = advance_units / 1000.0
        h = 0.7  # nominal x-height-ish
        path.moveto(0.0, 0.0)
        path.lineto(w, 0.0)
        path.lineto(w, h)
        path.lineto(0.0, h)
        path.close()
        self._draw.settransform(_to_pil_affine(ctm))
        try:
            self._draw.path(
                path,
                aggdraw.Pen((200, 200, 200), width=1.0),
                None,
            )
        finally:
            self._draw.settransform()


class _AggdrawPathPen:
    """Minimal fontTools Pen that captures glyph outlines into an
    :class:`aggdraw.Path`. Coordinates are scaled by ``scale`` so the
    resulting path lives in unit-em space (1.0 = one em) — the calling
    transform then multiplies by ``font_size`` to land in user space.

    Implements the subset of the fontTools ``AbstractPen`` interface that
    matters for SegmentPen-style glyph drawing: ``moveTo``, ``lineTo``,
    ``curveTo``, ``qCurveTo``, ``closePath``, ``endPath``.
    """

    def __init__(self, scale: float) -> None:
        self.path = aggdraw.Path()
        self._scale = float(scale)
        self.has_segments: bool = False
        self._last: tuple[float, float] | None = None

    def _xy(self, pt: tuple[float, float]) -> tuple[float, float]:
        return (pt[0] * self._scale, pt[1] * self._scale)

    def moveTo(self, pt: tuple[float, float]) -> None:  # noqa: N802
        x, y = self._xy(pt)
        self.path.moveto(x, y)
        self.has_segments = True
        self._last = (x, y)

    def lineTo(self, pt: tuple[float, float]) -> None:  # noqa: N802
        x, y = self._xy(pt)
        self.path.lineto(x, y)
        self.has_segments = True
        self._last = (x, y)

    def curveTo(self, *points: tuple[float, float]) -> None:  # noqa: N802
        # Cubic Bezier: 3 control points per segment; fontTools allows
        # superpaths but for TTF (after converted by the glyphSet wrapper)
        # we always get cubic triples or qCurveTo.
        for i in range(0, len(points), 3):
            triple = points[i : i + 3]
            if len(triple) != 3:
                break
            (x1, y1), (x2, y2), (x3, y3) = (self._xy(p) for p in triple)
            self.path.curveto(x1, y1, x2, y2, x3, y3)
            self._last = (x3, y3)
        self.has_segments = True

    def qCurveTo(self, *points: tuple[float, float]) -> None:  # noqa: N802
        # Quadratic — convert to cubic (CP2 = CP1; simple Bezier elevation
        # gives an exact representation: cubic CPs at 1/3 & 2/3 between the
        # quadratic endpoints/control). For TT glyphs, qCurveTo arrives as
        # a sequence of off-curve + on-curve points. Use fontTools' standard
        # interpretation: implicit on-curve points midway between consecutive
        # off-curves, with the final point being on-curve.
        if not points:
            return
        if self._last is None:
            return
        pts = [self._xy(p) for p in points if p is not None]
        # Detect TT-style: trailing on-curve; intermediate are off-curve.
        # Walk pairwise: (off, on) → quadratic; consecutive off-curves get
        # an implicit on-curve halfway between.
        last_x, last_y = self._last
        if len(pts) == 1:
            ex, ey = pts[0]
            self.path.curveto(last_x, last_y, ex, ey, ex, ey)
            self._last = (ex, ey)
            self.has_segments = True
            return
        # General TT case.
        i = 0
        while i < len(pts):
            cx, cy = pts[i]
            if i + 1 < len(pts):
                nx, ny = pts[i + 1]
                # If we're at the last point, it's on-curve.
                if i + 1 == len(pts) - 1:
                    on_x, on_y = nx, ny
                    self._add_quadratic(
                        last_x, last_y, cx, cy, on_x, on_y
                    )
                    last_x, last_y = on_x, on_y
                    i += 2
                    continue
                # Otherwise the next is also off-curve → implicit on-curve halfway.
                on_x = (cx + nx) / 2.0
                on_y = (cy + ny) / 2.0
                self._add_quadratic(last_x, last_y, cx, cy, on_x, on_y)
                last_x, last_y = on_x, on_y
                i += 1
            else:
                # Trailing single off-curve with no on-curve after it (rare).
                self.path.lineto(cx, cy)
                last_x, last_y = cx, cy
                i += 1
        self._last = (last_x, last_y)
        self.has_segments = True

    def _add_quadratic(
        self,
        x0: float,
        y0: float,
        cx: float,
        cy: float,
        x3: float,
        y3: float,
    ) -> None:
        """Convert a quadratic Bezier (P0, C, P3) into an exact cubic
        (P0, P0+2/3*(C-P0), P3+2/3*(C-P3), P3) and emit to aggdraw."""
        x1 = x0 + (2.0 / 3.0) * (cx - x0)
        y1 = y0 + (2.0 / 3.0) * (cy - y0)
        x2 = x3 + (2.0 / 3.0) * (cx - x3)
        y2 = y3 + (2.0 / 3.0) * (cy - y3)
        self.path.curveto(x1, y1, x2, y2, x3, y3)

    def closePath(self) -> None:  # noqa: N802
        self.path.close()

    def endPath(self) -> None:  # noqa: N802
        # Open subpath — aggdraw doesn't have a separate endPath; just
        # leave the subpath open. Filling unclosed subpaths is undefined
        # in PostScript-land; aggdraw's brush will close implicitly.
        pass

    # fontTools sometimes uses the deprecated lowercase verbs:
    def addComponent(  # noqa: N802
        self,
        baseGlyphName: str,  # noqa: ARG002, N803
        transformation: tuple[float, float, float, float, float, float],  # noqa: ARG002
    ) -> None:
        # Composite glyph — the glyphSet wrapper for TT fonts already
        # decomposes components into segments before calling moveTo/lineTo,
        # so this hook is rarely hit. When it is, the safest behaviour is
        # to silently skip rather than half-render.
        pass


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
    # clip
    "W": PDFRenderer._op_clip_non_zero,
    "W*": PDFRenderer._op_clip_even_odd,
    # XObject + inline image
    "Do": PDFRenderer._op_do,
    "BI": PDFRenderer._op_inline_image,
    # text
    "BT": PDFRenderer._op_begin_text,
    "ET": PDFRenderer._op_end_text,
    "Tf": PDFRenderer._op_set_font,
    "Tc": PDFRenderer._op_set_charspace,
    "Tw": PDFRenderer._op_set_wordspace,
    "TL": PDFRenderer._op_set_leading,
    "Tz": PDFRenderer._op_set_horizontal_scaling,
    "Ts": PDFRenderer._op_set_text_rise,
    "Td": PDFRenderer._op_text_move,
    "TD": PDFRenderer._op_text_move_set_leading,
    "Tm": PDFRenderer._op_text_matrix,
    "T*": PDFRenderer._op_text_next_line,
    "Tj": PDFRenderer._op_show_text,
    "TJ": PDFRenderer._op_show_text_array,
    "'": PDFRenderer._op_show_text_line,
    '"': PDFRenderer._op_show_text_line_with_spacing,
}


__all__ = ["PDFRenderer"]
