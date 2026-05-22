from __future__ import annotations

import contextlib
import io
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

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
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.image_type import ImageType
from pypdfbox.rendering.render_destination import RenderDestination

if TYPE_CHECKING:
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

_log = logging.getLogger(__name__)

# 6-tuple affine matrix used in both PDF (CTM) and PIL (settransform) form.
# We carry CTM as a tuple ``(a, b, c, d, e, f)`` representing the PDF matrix
# ``[a b 0; c d 0; e f 1]`` so a point ``(x, y)`` maps to
# ``(a*x + c*y + e, b*x + d*y + f)``. Matrix multiplication ``m1 * m2`` is
# defined as "apply m2 first, then m1" (same convention as PDFBox's
# ``Matrix.multiply``).
_Matrix = tuple[float, float, float, float, float, float]
_PathSegment = tuple[Any, ...]
_RGBFloat = tuple[float, float, float]
_IDENTITY: _Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _require_positive_finite(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


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
    # ---- stroke-state parameters (PDF 32000-1 §8.4.3 / Table 52) ----
    # Spec defaults: line cap = 0 (butt), line join = 0 (miter), miter
    # limit = 10.0, dash pattern = solid line. Wired by the ``w`` / ``gs``
    # operators (the dedicated ``J`` / ``j`` / ``M`` / ``d`` ops are
    # currently routed through ``gs`` for the ExtGState parity path —
    # the in-stream operators register as no-ops in the lite renderer).
    line_cap: int = 0
    line_join: int = 0
    miter_limit: float = 10.0
    # ``(dash_array_tuple, phase)`` — ``None`` means "solid line"
    # (spec default).  An empty dash array also means "solid line"
    # per PDF 32000-1 §8.4.3.6.
    dash_pattern: tuple[tuple[float, ...], float] | None = None
    # ---- rendering intent (PDF 32000-1 §8.6.5.8) ----
    # The renderer doesn't honour ICC rendering intent (skia / PIL don't
    # carry an ICC-aware pipeline at the rasterisation level), but we
    # record it for any downstream consumer that walks the GS for
    # bookkeeping (e.g. tests that pin the parsed ExtGState shape).
    rendering_intent: str | None = None
    # ---- pattern / shading paints (non-stroking + stroking) ----
    # When non-None, the corresponding paint is sourced from a
    # ``PDAbstractPattern`` (tiling or shading) instead of the solid RGB
    # above. The solid ``*_rgb`` is left untouched as a fallback for paths
    # that don't yet support the requested pattern type.
    fill_pattern: Any | None = None
    stroke_pattern: Any | None = None
    # ---- uncolored tiling pattern tint (PDF 32000-1 §8.7.3.3) ----
    # When the active fill / stroke pattern is a Type 2 uncolored tiling
    # pattern, the leading components of ``scn`` / ``SCN`` carry the
    # **tint colour** the pattern paints with. The renderer reads these
    # back at tile-render time and pre-seeds the recursive ``_GState``
    # with the matching ``*_rgb`` so any uncolored op inside the cell
    # (which doesn't carry its own colour) paints in the tint. ``None``
    # means "no tint vector available" (the pattern is Type 1, or the
    # components were absent / unconvertible).
    fill_pattern_tint: tuple[int, int, int] | None = None
    stroke_pattern_tint: tuple[int, int, int] | None = None
    # ---- active colour space (PDF 32000-1 §8.6) ----
    # Tracks the colour space last set by ``cs`` / ``CS`` so the next
    # ``scn`` / ``SCN`` can run its component vector through the right
    # ``to_rgb`` transform. ``None`` means the renderer falls back to the
    # spec default (DeviceGray) until a ``cs`` / ``CS`` runs.
    fill_color_space: Any | None = None
    stroke_color_space: Any | None = None
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
    # ---- text rendering mode (PDF 32000-1 §9.3.6) ----
    # Set by the ``Tr`` operator; 0..7 per Table 106. Default 0 = fill.
    # Modes 4-7 also add the glyph paths to the clipping path at ET.
    text_rendering_mode: int = 0
    # ---- clip ----
    # A PIL "L" image of the same size as the canvas, or None for "no clip".
    # Each pixel is the alpha multiplier (0 = clipped out, 255 = fully visible).
    clip_mask: Any | None = field(default=None)
    # ---- blend mode (PDF 32000-1 §11.3.5) ----
    # Active /BM from ExtGState (set via the ``gs`` operator). ``None`` means
    # the spec-default ``Normal`` (plain alpha-over). Only the separable
    # blend modes (§11.3.5.1) are honoured by the lite renderer; the
    # non-separable HSL family (§11.3.5.2) falls back to ``Normal`` with a
    # one-time debug log inside ``_blend``.
    blend_mode: Any | None = None
    # ---- soft mask from ExtGState /SMask (PDF 32000-1 §11.6.5.3) ----
    # When non-None, an ``PDSoftMask`` is active: the next compositing
    # step (transparency group, image paste, shading paint) computes a
    # mask alpha by rendering the soft-mask group XObject (/G), reading
    # its alpha (subtype /Alpha) or its luminance (subtype /Luminosity),
    # optionally applying the /TR transfer function, and multiplying that
    # into the source alpha. ``None`` means "no soft mask" (the literal
    # /None mask name from the gs operator also resets to None).
    soft_mask: Any | None = None
    # ---- alpha constants (CA / ca) ----
    # Stroke + non-stroke alpha multipliers in [0, 1] from ExtGState. 1.0
    # means "fully opaque" (the spec default). Honoured at compositing
    # time inside the soft-mask path; otherwise the lite renderer's solid
    # paints are unaffected (a future cluster wires CA/ca into stroke /
    # fill brushes directly).
    stroke_alpha: float = 1.0
    fill_alpha: float = 1.0
    # ---- ExtGState flags / tolerances (PDF 32000-1 §8.4.5 Table 58) ----
    # ``alpha_is_shape`` (``/AIS``) selects whether ``CA`` / ``ca``
    # multiply the source colour's alpha or its shape; the lite renderer
    # carries the flag but the SMask compositing path already honours
    # the result via the source alpha channel.
    alpha_is_shape: bool = False
    # ``text_knockout`` (``/TK``) defaults to True per spec — controls
    # whether glyphs in a text-showing operator knock each other out at
    # composite time. Carried for parity; the lite renderer paints
    # glyphs sequentially and does not currently fork the composite path
    # on this flag.
    text_knockout: bool = True
    # ``flatness`` (``/FL``) — curve-flattening tolerance for the
    # rasteriser. Skia uses adaptive subdivision; the field is carried
    # for parity but not consulted by the lite renderer.
    flatness: float = 1.0
    # ``smoothness`` (``/SM``) — gradient smoothness tolerance. Not
    # consulted by the renderer (skia handles gradient sampling).
    smoothness: float = 0.0
    # ``stroke_adjustment`` (``/SA``) — automatic stroke adjustment for
    # narrow strokes at low resolution. Carried for parity; skia's
    # native ``StrokeWidth`` already prevents sub-pixel disappearance.
    stroke_adjustment: bool = False

    def clone(self) -> _GState:
        # ``replace`` would re-share the field defaults — manually copy mutable
        # ones (clip_mask is a PIL image, immutable for our purposes since we
        # always allocate a new one when intersecting, so a shared ref is fine).
        return _GState(
            ctm=self.ctm,
            stroke_rgb=self.stroke_rgb,
            fill_rgb=self.fill_rgb,
            line_width=self.line_width,
            line_cap=self.line_cap,
            line_join=self.line_join,
            miter_limit=self.miter_limit,
            dash_pattern=self.dash_pattern,
            rendering_intent=self.rendering_intent,
            fill_pattern=self.fill_pattern,
            stroke_pattern=self.stroke_pattern,
            fill_pattern_tint=self.fill_pattern_tint,
            stroke_pattern_tint=self.stroke_pattern_tint,
            fill_color_space=self.fill_color_space,
            stroke_color_space=self.stroke_color_space,
            text_font=self.text_font,
            text_font_size=self.text_font_size,
            text_matrix=self.text_matrix,
            text_line_matrix=self.text_line_matrix,
            text_charspace=self.text_charspace,
            text_wordspace=self.text_wordspace,
            text_leading=self.text_leading,
            text_rise=self.text_rise,
            text_horizontal_scaling=self.text_horizontal_scaling,
            text_rendering_mode=self.text_rendering_mode,
            clip_mask=self.clip_mask,
            blend_mode=self.blend_mode,
            soft_mask=self.soft_mask,
            stroke_alpha=self.stroke_alpha,
            fill_alpha=self.fill_alpha,
            alpha_is_shape=self.alpha_is_shape,
            text_knockout=self.text_knockout,
            flatness=self.flatness,
            smoothness=self.smoothness,
            stroke_adjustment=self.stroke_adjustment,
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


def _coerce_color_components(
    operands: list[COSBase],
) -> tuple[float, ...] | None:
    """Convert ``scn`` / ``SCN`` operand list to a tuple of floats. Returns
    ``None`` when the operand list isn't a pure-numeric vector (e.g. when
    a trailing ``COSName`` indicates a pattern dispatch)."""
    out: list[float] = []
    for op in operands:
        if isinstance(op, COSName):
            return None
        if hasattr(op, "float_value"):
            out.append(float(op.float_value()))
            continue
        if hasattr(op, "int_value"):
            out.append(float(op.int_value()))
            continue
        try:
            out.append(float(op))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    return tuple(out) if out else None


def _resolve_builtin_color_spaces() -> dict[str, Any]:
    """Lazy load the singleton built-in color-space wrappers."""
    # Lazy import — pulls the full colour module on first use only.
    from pypdfbox.pdmodel.graphics.color import (  # noqa: PLC0415
        PDDeviceCMYK,
        PDDeviceGray,
        PDDeviceRGB,
        PDPattern,
    )

    return {
        "DeviceGray": PDDeviceGray.INSTANCE,
        "G": PDDeviceGray.INSTANCE,
        "DeviceRGB": PDDeviceRGB.INSTANCE,
        "RGB": PDDeviceRGB.INSTANCE,
        "DeviceCMYK": PDDeviceCMYK.INSTANCE,
        "CMYK": PDDeviceCMYK.INSTANCE,
        "Pattern": PDPattern(),
    }


_BUILTIN_DEVICE_COLOR_SPACES: dict[str, Any] = _resolve_builtin_color_spaces()


def _decode_inline_image_static(
    params: Any, data: Any
) -> Any:
    """Resource-less inline image decoder — covers the pre-1385 device
    CS surface (DeviceGray / DeviceRGB / DeviceCMYK / their abbreviated
    aliases + DCT / JPX filters). Used by the backwards-compat
    ``PDFRenderer._decode_inline_image(params, data)`` static-call
    form. The bound-method form on :class:`PDFRenderer` adds Indexed /
    ICCBased / Separation / DeviceN resolution via ``self._resources``.
    """
    import io as _io  # noqa: PLC0415

    from PIL import Image as _Image  # noqa: PLC0415

    if not isinstance(params, COSDictionary):
        return None

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
        return _Image.open(_io.BytesIO(data)).convert("RGB")
    if "JPXDecode" in filter_names:
        return _Image.open(_io.BytesIO(data)).convert("RGB")
    if filter_names:
        return None

    bpc = int(_to_float(bpc_obj)) if bpc_obj is not None else 8
    if bpc != 8:
        return None
    cs_name = cs_obj.name if isinstance(cs_obj, COSName) else None
    cs_abbrev = {"G": "DeviceGray", "RGB": "DeviceRGB", "CMYK": "DeviceCMYK"}
    if cs_name in cs_abbrev:
        cs_name = cs_abbrev[cs_name]
    if cs_name == "DeviceRGB" or (
        cs_name is None and len(data) >= width * height * 3
    ):
        return _Image.frombytes(
            "RGB", (width, height), data[: width * height * 3]
        )
    if cs_name == "DeviceGray":
        return _Image.frombytes(
            "L", (width, height), data[: width * height]
        ).convert("RGB")
    # DeviceCMYK + Indexed + ICCBased + Separation + DeviceN go through
    # the bound-method form on :class:`PDFRenderer` (which has access to
    # ``self._resources``). The static-call form is the pre-1385 surface
    # and rejects them by design.
    return None


def _cubic_bezier_pt(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """Evaluate the cubic Bezier ``p0 → p1 → p2 → p3`` at ``t ∈ [0, 1]``.
    Used by Coons / tensor patch boundary curves (Wave 1375)."""
    one_minus_t = 1.0 - t
    b0 = one_minus_t * one_minus_t * one_minus_t
    b1 = 3.0 * one_minus_t * one_minus_t * t
    b2 = 3.0 * one_minus_t * t * t
    b3 = t * t * t
    return (
        b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
        b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1],
    )


def _cubic_bernstein(t: float) -> tuple[float, float, float, float]:
    """Return the 4 cubic-Bernstein basis weights at ``t``.

    ``B_{i,3}(t) = C(3, i) * t^i * (1-t)^(3-i)`` for ``i = 0..3``. Used by
    the tensor-product Bezier patch evaluator (Wave 1375)."""
    one_minus_t = 1.0 - t
    return (
        one_minus_t * one_minus_t * one_minus_t,
        3.0 * one_minus_t * one_minus_t * t,
        3.0 * one_minus_t * t * t,
        t * t * t,
    )


# Maximum subdivision level per parametric axis. Upstream's Coons/Tensor
# patch ``calcLevel`` returns values in ``[1, 4]`` (yielding ``2^level``
# = 2..16 cells per axis); we use the same upper bound (level=4, N=16)
# matching upstream's hard-coded init value. Cap is enforced in case a
# future tuning bumps the init value — guards against pathological inputs.
_PATCH_MAX_LEVEL: int = 4


def _transform_point(
    point: tuple[float, float],
    ctm: tuple[float, float, float, float, float, float],
) -> tuple[float, float]:
    """Apply a 6-float CTM (row-vector form ``(a, b, c, d, e, f)``) to a
    point. ``(x', y') = (a*x + c*y + e, b*x + d*y + f)``. Used by
    :func:`_calc_patch_level` to measure edge lengths in device space."""
    a, b, c_, d, e, f = ctm
    return (a * point[0] + c_ * point[1] + e, b * point[0] + d * point[1] + f)


def _edge_is_line(edge: list[tuple[float, float]]) -> bool:
    """Port of upstream ``Patch.isEdgeALine``: returns ``True`` when the
    four cubic-Bezier control points ``edge[0..3]`` deviate from the
    straight chord ``edge[0] -> edge[3]`` by less than either the chord's
    x-span or y-span. This is the same numerical criterion the Java
    implementation uses.

    For the Bezier control polygon ``(p0, p1, p2, p3)``, the edge-equation
    value of point ``q`` against the chord ``p0 -> p3`` is
    ``(p3.y - p0.y) * (q.x - p0.x) - (p3.x - p0.x) * (q.y - p0.y)`` —
    twice the signed area of the triangle ``(p0, p3, q)``. The chord
    deviation in x is bounded by ``|p3.x - p0.x|`` and in y by
    ``|p3.y - p0.y|``; if BOTH inner control points stay within that
    band, the cubic is effectively a straight line.
    """
    p0, p1, p2, p3 = edge[0], edge[1], edge[2], edge[3]
    dx = p3[0] - p0[0]
    dy = p3[1] - p0[1]
    ctl1 = abs(dy * (p1[0] - p0[0]) - dx * (p1[1] - p0[1]))
    ctl2 = abs(dy * (p2[0] - p0[0]) - dx * (p2[1] - p0[1]))
    abs_dx = abs(dx)
    abs_dy = abs(dy)
    return (ctl1 <= abs_dx and ctl2 <= abs_dx) or (
        ctl1 <= abs_dy and ctl2 <= abs_dy
    )


def _edge_length(
    p0: tuple[float, float], p1: tuple[float, float]
) -> float:
    """Euclidean distance between two points. Port of
    ``Patch.getLen``."""
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def _level_from_length(length_u_1: float, length_u_2: float) -> int:
    """Map a pair of opposite-edge lengths (in device pixels) to a
    subdivision level using upstream's hard-coded thresholds (see
    ``CoonsPatch.calcLevel`` / ``TensorPatch.calcLevel``):

    * either edge > 800 px → level 4 (16 cells)
    * either edge > 400 px → level 3 (8 cells)
    * either edge > 200 px → level 2 (4 cells)
    * else                  → level 1 (2 cells)
    """
    longest = max(length_u_1, length_u_2)
    if longest > 800.0:
        return 4
    if longest > 400.0:
        return 3
    if longest > 200.0:
        return 2
    return 1


def _calc_patch_level(
    points: list[tuple[float, float]],
    ctm: tuple[float, float, float, float, float, float],
) -> tuple[int, int]:
    """Port of upstream ``CoonsPatch.calcLevel`` / ``TensorPatch.calcLevel``:
    pick the per-axis subdivision count ``(n_u, n_v)`` adaptively from the
    patch's control-polygon geometry. Returns the cell counts (not the
    levels) so callers can index a ``(n_v + 1) × (n_u + 1)`` grid.

    Algorithm:

    1. Identify the four boundary curves: ``c1``/``c2`` (the u-parametric
       boundaries at v=0 and v=1) and ``d1``/``d2`` (the v-parametric
       boundaries at u=0 and u=1).
    2. The default per-axis level is :data:`_PATCH_MAX_LEVEL` (= 4 →
       16 cells). Each axis is reduced only when BOTH opposite boundary
       curves are effectively straight (``_edge_is_line``).
    3. Reduce based on the device-space chord length of the straight
       edges using the thresholds in :func:`_level_from_length`.
    4. Tensor patches additionally check that none of the 4 interior
       control points falls outside the patch — if any does, the high
       level is retained (the patch is curvy regardless of edge
       straightness).

    ``points`` is the patch's user-space control polygon: 12 points for
    Coons (type 6), 16 points for tensor (type 7). ``ctm`` is the full
    user-space → device-space transform (so chord lengths are measured
    in pixels, matching upstream).

    Returns the pair ``(n_u, n_v)`` where each is ``2 ** level`` capped
    at ``2 ** _PATCH_MAX_LEVEL``.
    """
    n = len(points)
    if n == 12:
        # Coons: 4 boundary curves, see reshapeControlPoints upstream.
        # c1 = bottom (p0..p3), c2 = top (reversed, p9..p6),
        # d1 = left (p0,p11,p10,p9), d2 = right (p3..p6).
        c1 = [points[0], points[1], points[2], points[3]]
        c2 = [points[9], points[8], points[7], points[6]]
        d1 = [points[0], points[11], points[10], points[9]]
        d2 = [points[3], points[4], points[5], points[6]]
        interior_points: list[tuple[float, float]] = []
    elif n == 16:
        # Tensor: 4×4 grid, see TensorPatch.reshapeControlPoints upstream.
        # Boundary curves c1 = column 0, c2 = column 3, d1 = row 0,
        # d2 = row 3. Interior control points are grid[1..2][1..2].
        # Grid layout matches the renderer's tensor evaluator:
        #   row 0: p0, p1, p2, p3
        #   row 1: p11, p12, p13, p4
        #   row 2: p10, p15, p14, p5
        #   row 3: p9, p8, p7, p6
        c1 = [points[0], points[11], points[10], points[9]]
        c2 = [points[3], points[4], points[5], points[6]]
        d1 = [points[0], points[1], points[2], points[3]]
        d2 = [points[9], points[8], points[7], points[6]]
        interior_points = [
            points[12], points[13], points[15], points[14],
        ]
    else:  # pragma: no cover - guarded by caller
        return (
            2 ** _PATCH_MAX_LEVEL,
            2 ** _PATCH_MAX_LEVEL,
        )

    level_u = _PATCH_MAX_LEVEL
    level_v = _PATCH_MAX_LEVEL

    # u-axis: parametrised by edges d1 and d2 (top and bottom run across u).
    # Following upstream: edges c1 / c2 are tested first (these are the
    # axis-parallel boundaries — for Coons they are the u-curves directly;
    # for tensor they are the column edges). Reduce the corresponding axis
    # only when BOTH opposite edges are straight lines AND no interior CP
    # has bowed out of the patch.
    if _edge_is_line(c1) and _edge_is_line(c2):
        # For tensor patches, also check interior points are not on the
        # same side of both column boundaries (i.e. inside the patch).
        interior_ok = True
        if interior_points:
            for ip in interior_points:
                if _is_on_same_side(ip, c1[0], c2[0], c1[3], c2[3]):
                    interior_ok = False
                    break
        if interior_ok:
            # Measure device-space chord lengths of c1 / c2.
            len_c1 = _edge_length(
                _transform_point(c1[0], ctm),
                _transform_point(c1[3], ctm),
            )
            len_c2 = _edge_length(
                _transform_point(c2[0], ctm),
                _transform_point(c2[3], ctm),
            )
            level_u = _level_from_length(len_c1, len_c2)

    if _edge_is_line(d1) and _edge_is_line(d2):
        interior_ok = True
        if interior_points:
            for ip in interior_points:
                if _is_on_same_side(ip, d1[0], d1[3], d2[0], d2[3]):
                    interior_ok = False
                    break
        if interior_ok:
            len_d1 = _edge_length(
                _transform_point(d1[0], ctm),
                _transform_point(d1[3], ctm),
            )
            len_d2 = _edge_length(
                _transform_point(d2[0], ctm),
                _transform_point(d2[3], ctm),
            )
            level_v = _level_from_length(len_d1, len_d2)

    level_u = min(level_u, _PATCH_MAX_LEVEL)
    level_v = min(level_v, _PATCH_MAX_LEVEL)
    return (2 ** level_u, 2 ** level_v)


def _is_on_same_side(
    point: tuple[float, float],
    e1_a: tuple[float, float],
    e1_b: tuple[float, float],
    e2_a: tuple[float, float],
    e2_b: tuple[float, float],
) -> bool:
    """Return ``True`` when ``point`` is on the same side of both edges
    ``(e1_a, e1_b)`` and ``(e2_a, e2_b)`` — i.e. outside the strip
    bounded by them. Port of ``TensorPatch.isOnSameSideCC`` /
    ``isOnSameSideDD``.

    The Java code multiplies the two edge-equation values; a positive
    product means same side. We follow that convention exactly so the
    sign semantics match upstream.
    """
    v1 = _edge_equation_value(point, e1_a, e1_b)
    v2 = _edge_equation_value(point, e2_a, e2_b)
    return v1 * v2 > 0.0


def _edge_equation_value(
    p: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Port of ``Patch.edgeEquationValue`` — twice the signed area of the
    triangle ``(p1, p2, p)``. Used to test on-which-side a point falls."""
    return (p2[1] - p1[1]) * (p[0] - p1[0]) - (p2[0] - p1[0]) * (p[1] - p1[1])


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
      Type 3 fonts (PDF 32000-1 §9.6.5) execute each glyph's /CharProcs
      content stream through the same dispatch loop as a Form XObject,
      scaled by /FontMatrix into text space — see
      :meth:`_show_type3_string` / :meth:`_render_type3_charproc` for
      the routing. ``d0`` (uncoloured glyph advance) and ``d1``
      (coloured-glyph advance + bbox clip) are honoured. Standard 14
      (no embedded program) fall back to a faint placeholder rectangle
      with a one-time debug log — non-fatal, no crash.
    - Clip: ``W`` / ``W*`` — stage a clip-pending flag; the next path-end
      operator (paint or ``n``) intersects the path with the current clip
      mask via PIL polygon flattening.
    - Inline image: ``BI``…``ID``…``EI`` triplet — synthesised into an
      in-memory ``PDImageXObject`` and routed through the same paste path
      as ``Do`` for ``/Subtype /Image``.

    Deferred (silent skip; tracked in ``CHANGES.md``):

    - Shadings, patterns, transparency groups, soft masks, blend modes,
      line dash/cap/join, ``Tr`` text rendering modes (clipping/stroke),
      and Standard 14 glyph outlines without an embedded program
      (placeholder rectangle instead — see ``CHANGES.md``). Type 3
      charprocs are NOT deferred — they paint through the engine's
      Form-XObject dispatch (see :meth:`_render_type3_charproc`).
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
        self._subpaths: list[list[_PathSegment]] = []
        self._current_subpath: list[_PathSegment] | None = None
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
        # Cache of resolved fallback FontBoxFont programs (Standard 14 /
        # system substitutes) for fonts whose own program isn't embedded.
        # Keyed by ``id(font)``; ``None`` means "we tried and the mapper
        # had nothing", so we don't re-walk the mapper per-glyph. Filled
        # by ``_resolve_font_program`` (PDF 32000-1 §9.8 / §9.10).
        self._font_program_cache: dict[int, Any | None] = {}
        # Type 3 charproc per-glyph metric overrides. ``d0`` sets
        # ``_type3_d0_wx`` (uncoloured glyph — advance only); ``d1`` sets
        # ``_type3_d1_wx`` plus installs a bbox clip (coloured glyph). The
        # values are read after charproc dispatch by ``_show_type3_string``
        # to override the ``/Widths`` value for the just-rendered glyph,
        # matching upstream PDFBox's ``Type3Glyph2D`` width-override
        # behaviour (PDF 32000-1 §9.6.5.3). Reset to ``None`` before each
        # charproc invocation.
        self._type3_d0_wx: float | None = None
        self._type3_d1_wx: float | None = None
        # Type 3 glyph cache — (id(font), glyph_name, font_size_q,
        # ctm_scale_q, fill_rgb, stroke_rgb) -> rendered glyph image +
        # bounding box. Allows multi-glyph runs to skip re-dispatching the
        # charproc when the same glyph is shown again at the same size
        # and colour. Quantisation buckets size + ctm-scale to integer 100ths
        # so floating-point jitter doesn't bust the cache.
        self._type3_glyph_cache: dict[
            tuple[int, str, int, int, tuple[float, ...], tuple[float, ...]],
            int,
        ] = {}
        # ---- text-rendering clipping accumulator (wave 1385) ----
        # Modes 4..7 of the ``Tr`` operator (PDF 32000-1 §9.3.6) add each
        # painted glyph's outline to the current clipping path. Per spec
        # the clip is committed AT the matching ``ET`` (not at each glyph),
        # so the union of all glyph paths in the BT/ET block becomes a
        # single intersection with the current GS clip. Each entry is a
        # raw ``skia.Path`` whose coordinates already live in device-pixel
        # space (after the per-glyph PDF→PIL affine has been applied).
        self._text_clip_paths: list[Any] = []
        # ---- public render-config flags (mirror upstream PDFRenderer) ----
        # These are stored only — the lite renderer doesn't yet consult them,
        # but downstream tooling that ports from PDFBox calls these setters
        # unconditionally and would crash on AttributeError. Defaults match
        # upstream ``PDFRenderer`` field initialisers in PDFBox 3.0.x.
        self._subsampling_allowed: bool = False
        self._default_destination: str = "View"
        # Active destination resolved per render_image call — annotation
        # visibility consults this for the four-arg renderImage overload
        # without mutating ``_default_destination``.
        self._active_destination: Any = None
        self._image_downscaling_optimization_threshold: float = 0.5
        # ---- transparency-group state (PDF spec §11.4.7) ----
        # When ``_knockout_active`` is True we restore ``_knockout_snapshot``
        # over the active group canvas before each top-level painting
        # operator, mirroring the spec's "each child object replaces (rather
        # than composites with) prior contents at the group level" rule.
        # ``_knockout_form_depth`` counts nested form-XObject Do invocations
        # so the snapshot reset only fires for *top-level* group children,
        # not for paints inside nested forms.
        self._knockout_active: bool = False
        self._knockout_snapshot: Image.Image | None = None
        self._knockout_form_depth: int = 0
        # ---- soft-mask depth (wave 1384) ----
        # When > 0 we're rendering INTO a transparency-group canvas (or the
        # soft-mask group itself); the active ExtGState ``/SMask`` is applied
        # at group-composite time, so per-paint SMask application must be
        # suppressed here to avoid double-masking. Mirrors upstream's behaviour
        # where ``applySoftMaskToPaint`` is bypassed during the group's own
        # recursive render — the group's paints accumulate raw, then the mask
        # is multiplied at the very end.
        self._transparency_group_depth: int = 0
        # ---- Form XObject recursion cap (wave 1385) ----
        # Mirrors upstream ``DrawObject.java`` (line 84-89) which caps the
        # ``Do`` Form-XObject recursion depth at 50 to prevent malicious or
        # malformed PDFs from blowing the rasteriser's call stack. The
        # counter is bumped in ``_op_do`` only for Form-XObject invocations
        # (not images); upstream's cap has the same scope.
        self._form_x_object_depth: int = 0
        self._form_x_object_depth_limit: int = 50
        # ---- annotation filter (mirrors upstream ``AnnotationFilter``) ----
        # Upstream's default filter accepts every annotation
        # (``annotation -> true``); we model the filter as a plain
        # ``Callable[[PDAnnotation], bool]``. Stored only — the lite
        # renderer's annotation pipeline (when wired) will consult it.
        self._annotation_filter: Any = lambda _annotation: True
        # ---- last rendered page image (mirrors package-private
        # upstream ``getPageImage()``). Captured at the end of
        # ``render_image_with_dpi`` so callers (e.g. tests, custom
        # post-processors) can read it back without re-rendering.
        self._page_image: Image.Image | None = None
        # ---- rendering hints (mirrors upstream Java2D ``RenderingHints``).
        # The lite renderer doesn't consult Java2D hints, but downstream
        # tooling that mirrors PDFBox call sites passes a hint dict
        # through unconditionally; storing it keeps that path
        # AttributeError-free.
        self._rendering_hints: Any | None = None

    # ------------------------------------------------------------------
    # public API (mirrors PDFRenderer.java)
    # ------------------------------------------------------------------

    def render_image(
        self,
        page_index: int,
        scale: float = 1.0,
        image_type: ImageType | None = None,
        destination: str | RenderDestination | None = None,
    ) -> Image.Image:
        """Render at 72 DPI base * ``scale``. Mirrors upstream
        ``PDFRenderer.renderImage(int, float, ImageType)`` and the
        four-arg ``renderImage(int, float, ImageType, RenderDestination)``
        overload (plus the one-/two-arg variants).

        ``image_type`` selects the Pillow mode of the returned image
        (RGB, RGBA, L, "1"). When ``None`` the lite renderer keeps its
        historical white-RGB canvas behaviour.

        ``destination`` mirrors upstream's ``RenderDestination`` argument
        that drives OCG visibility and annotation appearance selection.
        ``None`` (the default) defers to the renderer-level default set
        via :meth:`set_default_destination`. A bare string
        (``"View"`` / ``"Print"`` / ``"Export"``) is accepted alongside
        the :class:`RenderDestination` enum value for parity with the
        renderer-level setter.
        """
        scale = _require_positive_finite(scale, "scale")
        return self.render_image_with_dpi(
            page_index,
            dpi=72.0 * scale,
            image_type=image_type,
            destination=destination,
        )

    def render_image_with_dpi(
        self,
        page_index: int,
        dpi: float = 72.0,
        image_type: ImageType | None = None,
        destination: str | RenderDestination | None = None,
    ) -> Image.Image:
        """Render the page at the given DPI. Mirrors upstream
        ``PDFRenderer.renderImageWithDPI``.

        ``image_type`` mirrors the upstream three-arg overload
        ``renderImageWithDPI(int, float, ImageType)``. It selects the
        Pillow mode of the returned image (RGB, RGBA, L, "1"). When
        ``None`` (the default), the lite renderer keeps its historical
        white-RGB canvas behaviour.

        ``destination`` mirrors the four-arg ``renderImage(int, float,
        ImageType, RenderDestination)`` overload — it threads through to
        the :class:`PageDrawerParameters` constructed for this render so
        OCG visibility and annotation appearance selection see the
        caller's choice without mutating the renderer-level default.
        ``None`` defers to that default. Accepts either a
        :class:`RenderDestination` enum value or the bare string
        equivalent.

        Upstream allocates a ``BufferedImage`` and constructs a
        ``PageDrawer`` via :meth:`create_page_drawer`, then calls
        ``pageDrawer.drawPage(graphics, pageSize)``. We follow the same
        flow: the actual rasterisation lives in
        :meth:`PageDrawer.draw_page`, which delegates back to
        :meth:`_render_page_into` so the heavy PIL/aggdraw state stays on
        the renderer for now.
        """
        # Imported lazily — both modules import each other, and the
        # circular import only resolves once both classes are bound.
        from pypdfbox.rendering.page_drawer import (  # noqa: PLC0415
            PageDrawer,
        )
        from pypdfbox.rendering.page_drawer_parameters import (  # noqa: PLC0415
            PageDrawerParameters,
        )

        dpi = _require_positive_finite(dpi, "dpi")
        page = self._get_page_for_render(page_index)
        media_box = page.get_media_box()
        # PDF user-space units are 1/72 inch. Pixel dims = pts * dpi / 72.
        scale = float(dpi) / 72.0
        width_pt = media_box.get_width()
        height_pt = media_box.get_height()
        width_px = max(1, int(round(width_pt * scale)))
        height_px = max(1, int(round(height_pt * scale)))

        # aggdraw can only rasterise onto an RGB canvas, so we always
        # render into RGB and convert at teardown when the caller asked
        # for a different image type. ARGB/RGBA is the one mode where
        # we want a transparent-canvas start to match upstream's
        # ``new Color(0, 0, 0, 0)`` clearRect; the conversion at the
        # end preserves alpha by paint-checking the white background.
        image = Image.new("RGB", (width_px, height_px), (255, 255, 255))

        # Bundle the renderer-level options into a PageDrawerParameters
        # (mirrors upstream PDFRenderer.renderImageWithDPI which builds
        # parameters → createPageDrawer → drawPage). When the caller
        # provided an explicit ``destination`` we honour that for this
        # render only — without mutating ``_default_destination``,
        # matching upstream's four-arg
        # ``renderImage(int, float, ImageType, RenderDestination)``
        # which threads ``destination`` straight into PageDrawerParameters.
        if destination is None:
            resolved_destination = RenderDestination(self._default_destination)
        elif isinstance(destination, RenderDestination):
            resolved_destination = destination
        else:
            resolved_destination = RenderDestination(destination)
        parameters = PageDrawerParameters(
            renderer=self,
            page=page,
            subsampling_allowed=self._subsampling_allowed,
            destination=resolved_destination,
            rendering_hints=self._rendering_hints,
            image_downscaling_optimization_threshold=(
                self._image_downscaling_optimization_threshold
            ),
        )
        # Ask the customisation hook for a page drawer. The lite
        # renderer's default implementation stamps the annotation filter
        # onto the parameters and (since wave 1288) returns a real
        # ``PageDrawer`` instance — subclasses can override to plug in
        # their own drawer.
        page_drawer = self.create_page_drawer(parameters)
        if page_drawer is None or page_drawer is self:
            # Subclass override returned ``self`` (legacy lite-renderer
            # behaviour) — fall back to a fresh ``PageDrawer`` so the
            # delegation path is always exercised.
            page_drawer = PageDrawer(parameters)
        # Record the active scale on the renderer up-front so any helper
        # consulted before ``_render_page_into`` runs sees the right
        # value (e.g. resolving the device CTM during constructor work).
        self._scale = scale
        self._page_height_px = float(height_px)
        # Stash the resolved destination so annotation visibility checks
        # in ``_annotation_should_skip`` see the per-call override
        # without mutating ``_default_destination`` (mirrors upstream's
        # four-arg ``renderImage(int, float, ImageType, RenderDestination)``
        # which threads ``destination`` straight into PageDrawer).
        previous_active_destination = getattr(self, "_active_destination", None)
        self._active_destination = resolved_destination
        try:
            page_drawer.draw_page(image, media_box)
        finally:
            self._active_destination = previous_active_destination

        # Convert to the caller-requested image type if needed.
        # Pillow handles every direction (RGB → L / "1" / RGBA / etc.)
        # via ``Image.convert``; for ARGB we tag the formerly-white
        # background as fully transparent so it composes correctly,
        # mirroring upstream's transparent-canvas + final blit
        # behaviour.
        if image_type is not None and image_type is not ImageType.RGB:
            target_mode = image_type.pil_mode
            if target_mode == "RGBA":
                rgba = image.convert("RGBA")
                # Make any pixel that's still pure white fully
                # transparent so the alpha channel matches what
                # upstream's transparent-canvas render produced.
                pixels = cast(Any, rgba.load())
                w, h = rgba.size
                for y in range(h):
                    for x in range(w):
                        r, g, b, _a = pixels[x, y]
                        if r == 255 and g == 255 and b == 255:
                            pixels[x, y] = (r, g, b, 0)
                image = rgba
            else:
                image = image.convert(target_mode)
        # Cache the freshly-rendered page so callers can recover it via
        # ``get_page_image()`` (mirrors upstream package-private accessor).
        self._page_image = image
        return image

    def _render_page_into(
        self,
        page: PDPage,
        image: Image.Image,
        page_size: Any,
        scale: float,
    ) -> None:
        """Drive the content-stream walk that paints ``page`` into
        ``image`` at ``scale``. Invoked from
        :meth:`PageDrawer.draw_page`; broken out so the PageDrawer
        delegate stays tiny while the heavyweight PIL/aggdraw state
        keeps living on the renderer.

        ``page_size`` mirrors upstream's PDRectangle argument and
        anchors the device CTM origin/flip. It's currently expected to
        be the page's media box (the only shape ``render_image_with_dpi``
        forwards), but a downstream caller can pass any rectangle to
        re-anchor the y-axis flip (e.g. for crop-box rendering or
        ``renderPageToGraphics``-style overlays).
        """
        width_px, height_px = image.size

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
        mb_x = page_size.get_lower_left_x()
        mb_y = page_size.get_lower_left_y()
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
        self._font_program_cache = {}

        try:
            self.process_page(page)
            # After the page content stream is processed, walk the page
            # annotations and paint each one's appearance on top.
            # Mirrors upstream ``PageDrawer.drawPage`` which loops
            # ``page.getAnnotations(annotationFilter)`` and calls
            # ``showAnnotation`` per entry. The filter is consulted
            # inside ``get_annotations`` (matching upstream's
            # ``getAnnotations(AnnotationFilter)`` overload); per-annotation
            # visibility flags (Hidden / NoView / Print=false) are checked
            # inside ``_render_annotation`` mirroring upstream's
            # ``shouldSkipAnnotation``.
            try:
                annotations = page.get_annotations(self._annotation_filter)
            except Exception as exc:  # noqa: BLE001 — defensive
                _log.debug("annotation iteration failed: %s", exc)
                annotations = []
            for annotation in annotations:
                try:
                    self._render_annotation(annotation)
                except Exception as exc:  # noqa: BLE001 — log-and-continue
                    subtype = None
                    with contextlib.suppress(Exception):
                        subtype = annotation.get_subtype()
                    _log.debug(
                        "annotation render failed (subtype=%r): %s",
                        subtype,
                        exc,
                    )
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

    def _get_page_for_render(self, page_index: int) -> PDPage:
        if page_index < 0 or page_index >= self._document.get_number_of_pages():
            raise IndexError(f"page index out of range: {page_index}")
        return self._document.get_pages()[page_index]

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

    def set_default_destination(
        self, destination: str | RenderDestination
    ) -> None:
        """Set the default render destination used for OCG visibility and
        annotation appearance selection. Upstream uses an enum
        (``RenderDestination.VIEW`` / ``PRINT`` / ``EXPORT``); we accept
        either the :class:`RenderDestination` enum value or the bare
        string equivalent ``"View"`` / ``"Print"`` / ``"Export"``.
        Mirrors ``PDFRenderer.setDefaultDestination(RenderDestination)``."""
        if isinstance(destination, RenderDestination):
            self._default_destination = destination.value
        else:
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

    def get_annotations_filter(self) -> Any:
        """Return the active annotation filter callable. Mirrors upstream
        ``PDFRenderer.getAnnotationsFilter()``.

        The default (set in ``__init__``) accepts every annotation —
        i.e. ``annotation -> True``."""
        return self._annotation_filter

    def set_annotations_filter(self, annotations_filter: Any) -> None:
        """Replace the annotation filter. Mirrors upstream
        ``PDFRenderer.setAnnotationsFilter(AnnotationFilter)``.

        ``annotations_filter`` is a callable
        ``(PDAnnotation) -> bool`` that returns True for annotations
        that should be rendered. Stored only — the lite renderer's
        annotation pipeline (when wired) will consult it."""
        self._annotation_filter = annotations_filter

    def get_rendering_hints(self) -> Any | None:
        """Return the rendering hints, or ``None`` if none are set.
        Mirrors upstream ``PDFRenderer.getRenderingHints()``.

        The lite renderer doesn't consult Java2D ``RenderingHints``;
        the value is stored only so downstream tooling that mirrors
        PDFBox call sites can round-trip it."""
        return self._rendering_hints

    def set_rendering_hints(self, rendering_hints: Any | None) -> None:
        """Set the rendering hints. Mirrors upstream
        ``PDFRenderer.setRenderingHints(RenderingHints)``.

        Pass ``None`` to defer the choice to the renderer (upstream
        picks bicubic/quality at render time based on the destination).
        Stored only in the lite renderer."""
        self._rendering_hints = rendering_hints

    def get_page_image(self) -> Image.Image | None:
        """Return the most recently rendered page image, or ``None`` if
        no page has been rendered yet. Mirrors upstream package-private
        ``PDFRenderer.getPageImage()`` — exposed publicly here so tests
        and custom post-processors can read back the last frame without
        re-rendering."""
        return self._page_image

    def get_document(self) -> PDDocument:
        """Return the document being rendered. Mirrors upstream's
        protected ``document`` field (accessed by ``PageDrawer`` via
        ``getRenderer().document``).

        Exposed as a regular accessor so subclasses overriding the
        rendering pipeline don't have to reach into ``_document``."""
        return self._document

    def is_group_enabled(self, group: Any) -> bool:
        """Indicate whether an optional content group is enabled.
        Mirrors upstream ``PDFRenderer.isGroupEnabled(PDOptionalContentGroup)``.

        Returns True when the document has no ``/OCProperties`` (i.e.
        no OCG configuration) or when the OCProperties config marks the
        group as enabled. ``group`` is a ``PDOptionalContentGroup``."""
        oc_properties = self._document.get_document_catalog().get_oc_properties()
        if oc_properties is None:
            return True
        return bool(oc_properties.is_group_enabled(group))

    # ------------------------------------------------------------------
    # rendering-pipeline hooks (mirror upstream private/protected methods)
    # ------------------------------------------------------------------

    def has_blend_mode(self, page: PDPage) -> bool:
        """Return True when any ``/ExtGState`` on the page declares a
        non-Normal blend mode. Mirrors upstream
        ``PDFRenderer.hasBlendMode(PDPage)`` (Java 559–582).

        Used by the upstream renderer to flip an RGB target to ARGB so
        top-level blends composite against a transparent backdrop
        (PDFBOX-4095). The lite renderer already handles blend
        compositing inline; this accessor is provided so subclasses /
        downstream tooling can mirror upstream's branch."""
        from pypdfbox.pdmodel.graphics.blend_mode import (  # noqa: PLC0415
            BlendMode,
        )

        resources = page.get_resources()
        if resources is None:
            return False
        try:
            names = resources.get_ext_g_state_names()
        except Exception:  # noqa: BLE001
            return False
        normal = BlendMode.NORMAL
        for name in names:
            try:
                ext_gstate = resources.get_ext_gstate(name)
            except Exception:  # noqa: BLE001
                continue
            # extGState null can happen if the key exists but has no value
            # (see PDFBOX-3950-23EGDHXSBBYQLKYOKGZUOVYVNE675PRD.pdf).
            if ext_gstate is None:
                continue
            blend_mode = ext_gstate.get_blend_mode()
            if blend_mode is not None and blend_mode is not normal:
                return True
        return False

    def is_bitonal(self, graphics: Any) -> bool:
        """Return True when the target graphics device is 1-bit-deep.
        Mirrors upstream ``PDFRenderer.isBitonal(Graphics2D)`` (Java
        510–528).

        Upstream walks ``Graphics2D.getDeviceConfiguration().getDevice()
        .getDisplayMode().getBitDepth() == 1``. We don't have AWT, so
        this lite mirror duck-types: a target reporting ``mode == "1"``
        (a Pillow 1-bit ``Image``) or exposing a ``get_bit_depth()`` /
        ``bit_depth`` of 1 is bitonal. Anything else (including
        ``None``) is treated as non-bitonal — same as upstream when
        any link in the chain is null."""
        if graphics is None:
            return False
        # Pillow Image / ImageDraw.Draw — both surface ``mode``.
        mode = getattr(graphics, "mode", None)
        if mode is None:
            image = getattr(graphics, "image", None)
            if image is not None:
                mode = getattr(image, "mode", None)
        if mode == "1":
            return True
        # Generic duck-type for anything mimicking AWT's GraphicsDevice.
        get_bit_depth = getattr(graphics, "get_bit_depth", None)
        if callable(get_bit_depth):
            try:
                return int(get_bit_depth()) == 1
            except Exception:  # noqa: BLE001
                return False
        bit_depth = getattr(graphics, "bit_depth", None)
        if isinstance(bit_depth, int):
            return bit_depth == 1
        return False

    def create_default_rendering_hints(self, graphics: Any) -> dict[str, str]:
        """Return the default rendering-hint dict used when the caller
        didn't provide one. Mirrors upstream
        ``PDFRenderer.createDefaultRenderingHints(Graphics2D)`` (Java
        530–542).

        Upstream returns an AWT ``RenderingHints`` keyed by AWT
        constants (``KEY_INTERPOLATION``, ``KEY_RENDERING``,
        ``KEY_ANTIALIASING``). The lite renderer doesn't consult AWT
        hints, so we emit a dict keyed by the upstream string names —
        good enough for parity tests and downstream tooling that just
        wants to round-trip the value."""
        bitonal = self.is_bitonal(graphics)
        return {
            "KEY_INTERPOLATION": (
                "VALUE_INTERPOLATION_NEAREST_NEIGHBOR"
                if bitonal
                else "VALUE_INTERPOLATION_BICUBIC"
            ),
            "KEY_RENDERING": "VALUE_RENDER_QUALITY",
            "KEY_ANTIALIASING": (
                "VALUE_ANTIALIAS_OFF" if bitonal else "VALUE_ANTIALIAS_ON"
            ),
        }

    def create_page_drawer(self, parameters: Any) -> Any:
        """Return a page-drawer for the given parameters. Mirrors
        upstream ``PDFRenderer.createPageDrawer(PageDrawerParameters)``
        (Java 552–557) — overridable by subclasses that want to plug in
        a custom drawer.

        Returns a fresh :class:`PageDrawer` bound to ``parameters``
        when a real :class:`PageDrawerParameters` is supplied. Falls
        back to ``self`` for the legacy "no parameters" call shape so
        existing callers that pre-date the wave-1288 split keep
        working. The renderer's currently-active annotation filter is
        stamped onto the returned drawer (and onto the parameters
        themselves when they expose ``set_annotation_filter``) so the
        drawer matches the value the caller would have read via
        :meth:`get_annotations_filter`."""
        from pypdfbox.rendering.page_drawer import (  # noqa: PLC0415
            PageDrawer,
        )

        # Mirror upstream's filter inheritance: a fresh PageDrawer
        # adopts the renderer's filter unless the subclass replaces it.
        if parameters is not None and hasattr(parameters, "set_annotation_filter"):
            with contextlib.suppress(Exception):
                parameters.set_annotation_filter(self._annotation_filter)
        if parameters is None or not hasattr(parameters, "get_page"):
            # Legacy call shape (predates the PageDrawer split). Keep
            # behaviour stable for callers that mirror upstream's
            # subclass-only override pattern without supplying real
            # parameters.
            return self
        try:
            drawer = PageDrawer(parameters)
        except (TypeError, AttributeError):
            return self
        drawer.set_annotation_filter(self._annotation_filter)
        return drawer

    def transform(
        self,
        graphics: Any,
        rotation_angle: int,
        crop_box: Any,
        scale_x: float,
        scale_y: float,
    ) -> _Matrix:
        """Apply the page rotation + scaling transform to ``graphics``
        and return the equivalent 6-tuple PDF matrix. Mirrors upstream
        ``PDFRenderer.transform`` (Java 481–508): scale, then translate
        + rotate so the page's lower-left lands at (0, 0) post-rotation.

        Upstream operates on ``java.awt.Graphics2D``. We duck-type:
        when ``graphics`` exposes ``scale`` / ``translate`` / ``rotate``
        methods (as e.g. ``aggdraw.Draw`` does for some affine ops, or
        a downstream subclass might) they're called with the matching
        arguments; otherwise we just compute the matrix and return it.
        Returning the matrix lets test code assert the exact transform
        without poking at Java2D state."""
        # Always build the matrix so the caller has the equivalent CTM.
        translate_x = 0.0
        translate_y = 0.0
        if rotation_angle == 90:
            translate_x = float(crop_box.get_height())
        elif rotation_angle == 270:
            translate_y = float(crop_box.get_width())
        elif rotation_angle == 180:
            translate_x = float(crop_box.get_width())
            translate_y = float(crop_box.get_height())

        matrix: _Matrix = (float(scale_x), 0.0, 0.0, float(scale_y), 0.0, 0.0)
        if rotation_angle:
            radians = math.radians(rotation_angle)
            cos_r = math.cos(radians)
            sin_r = math.sin(radians)
            translate: _Matrix = (1.0, 0.0, 0.0, 1.0, translate_x, translate_y)
            rotate: _Matrix = (cos_r, sin_r, -sin_r, cos_r, 0.0, 0.0)
            # PDF post-multiplication: device = scale ∘ translate ∘ rotate
            matrix = _matmul(_matmul(rotate, translate), matrix)

        # Best-effort: if the caller passed a graphics target with an
        # AWT-style imperative API, replay scale/translate/rotate on it.
        scale_fn = getattr(graphics, "scale", None)
        if callable(scale_fn):
            with contextlib.suppress(Exception):
                scale_fn(scale_x, scale_y)
        if rotation_angle:
            translate_fn = getattr(graphics, "translate", None)
            if callable(translate_fn):
                with contextlib.suppress(Exception):
                    translate_fn(translate_x, translate_y)
            rotate_fn = getattr(graphics, "rotate", None)
            if callable(rotate_fn):
                with contextlib.suppress(Exception):
                    rotate_fn(math.radians(rotation_angle))
        return matrix

    def render_page_to_graphics(
        self,
        page_index: int,
        graphics: Any,
        scale_x: float = 1.0,
        scale_y: float | None = None,
        destination: Any | None = None,
    ) -> None:
        """Render a page onto an existing graphics target. Mirrors
        upstream ``PDFRenderer.renderPageToGraphics`` (Java 383–467) —
        the four overloads collapse into one call with optional
        ``scale_y`` (defaults to ``scale_x``) and optional
        ``destination`` (defaults to
        ``self.get_default_destination()`` or
        :attr:`RenderDestination.VIEW`).

        Upstream draws into a Java2D ``Graphics2D``. The lite renderer
        accepts a ``PIL.Image.Image`` instead: we render the page to a
        fresh image at the requested scale and paste it into the target
        at (0, 0). Callers that need a different blit point should
        crop / paste themselves. ``destination`` is stored only — the
        lite renderer doesn't yet branch on VIEW/PRINT/EXPORT (tracked
        in ``CHANGES.md``)."""
        if scale_y is None:
            scale_y = scale_x
        scale_x = _require_positive_finite(scale_x, "scale_x")
        scale_y = _require_positive_finite(scale_y, "scale_y")
        # Resolve destination — only stored, but track it so subclasses
        # that override can read self._default_destination consistently
        # with upstream's behaviour (see Java 449–451).
        if destination is None:
            destination = self._default_destination or RenderDestination.VIEW
        # Render at the maximum of the two axes so we don't lose detail,
        # then let the caller's target absorb anisotropic scaling via
        # PIL's resize. Upstream lets Java2D handle anisotropic scale
        # natively; we approximate by rendering once and resampling.
        scale = max(scale_x, scale_y)
        rendered = self.render_image(page_index, scale=scale)
        if scale_x != scale_y:
            page = self._get_page_for_render(page_index)
            crop_box = page.get_crop_box()
            target_w = max(1, int(round(crop_box.get_width() * scale_x)))
            target_h = max(1, int(round(crop_box.get_height() * scale_y)))
            rendered = rendered.resize((target_w, target_h), Image.BICUBIC)
        if isinstance(graphics, Image.Image):
            graphics.paste(rendered, (0, 0))
            return
        # Anything else — e.g. an aggdraw.Draw or a custom target — try
        # the duck-typed ``draw_image`` / ``paste`` API; fall back to a
        # silent no-op so a downstream caller's custom hook can pick up
        # the rendered image via ``get_page_image()``.
        for attr in ("paste", "draw_image", "drawImage"):  # noqa: N802
            fn = getattr(graphics, attr, None)
            if callable(fn):
                try:
                    fn(rendered, (0, 0))
                except TypeError:
                    with contextlib.suppress(Exception):
                        fn(rendered, 0, 0)
                return

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
        # Knockout-group reset: before each top-level painting operator
        # inside a /K=true transparency group, restore the group canvas to
        # the snapshot taken at group entry. PDF spec §11.4.7.3.
        if (
            self._knockout_active
            and self._knockout_form_depth == 0
            and name in _KNOCKOUT_PAINT_OPS
        ):
            self._restore_knockout_snapshot()
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
        m: _Matrix = (
            _to_float(operands[0]),
            _to_float(operands[1]),
            _to_float(operands[2]),
            _to_float(operands[3]),
            _to_float(operands[4]),
            _to_float(operands[5]),
        )
        # cm post-multiplies the current CTM. PDF spec §8.4.4: "Modify
        # the current transformation matrix (CTM) by concatenating the
        # specified matrix" — new_ctm = matrix * old_ctm.
        self._gs.ctm = _matmul(m, self._gs.ctm)

    # ---- colour ----

    def _op_set_stroke_rgb(self, _op: Any, operands: list[COSBase]) -> None:
        # RG — PDF 32000-1 §8.6.5.3. Sets the stroking colour space to
        # DeviceRGB AND clears any active pattern. Mirrors upstream
        # SetStrokingDeviceRGBColor.process which constructs a new PDColor
        # over DeviceRGB.
        if len(operands) < 3:
            return
        r, g, b = (_to_float(operands[i]) for i in range(3))
        self._gs.stroke_rgb = _rgb_bytes(r, g, b)
        self._gs.stroke_color_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceRGB"]
        self._gs.stroke_pattern = None

    def _op_set_fill_rgb(self, _op: Any, operands: list[COSBase]) -> None:
        # rg — same as RG for the non-stroking colour.
        if len(operands) < 3:
            return
        r, g, b = (_to_float(operands[i]) for i in range(3))
        self._gs.fill_rgb = _rgb_bytes(r, g, b)
        self._gs.fill_color_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceRGB"]
        self._gs.fill_pattern = None

    def _op_set_stroke_gray(self, _op: Any, operands: list[COSBase]) -> None:
        # G — PDF 32000-1 §8.6.5.2. Sets stroking colour space to
        # DeviceGray; clears pattern.
        if not operands:
            return
        g = _to_float(operands[0])
        self._gs.stroke_rgb = _rgb_bytes(g, g, g)
        self._gs.stroke_color_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceGray"]
        self._gs.stroke_pattern = None

    def _op_set_fill_gray(self, _op: Any, operands: list[COSBase]) -> None:
        # g — same as G for the non-stroking colour.
        if not operands:
            return
        g = _to_float(operands[0])
        self._gs.fill_rgb = _rgb_bytes(g, g, g)
        self._gs.fill_color_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceGray"]
        self._gs.fill_pattern = None

    def _op_set_stroke_cmyk(self, _op: Any, operands: list[COSBase]) -> None:
        # K — PDF 32000-1 §8.6.5.4. Sets stroking colour space to
        # DeviceCMYK; clears pattern.
        if len(operands) < 4:
            return
        c, m, y, k = (_to_float(operands[i]) for i in range(4))
        self._gs.stroke_rgb = _cmyk_to_rgb_bytes(c, m, y, k)
        self._gs.stroke_color_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceCMYK"]
        self._gs.stroke_pattern = None

    def _op_set_fill_cmyk(self, _op: Any, operands: list[COSBase]) -> None:
        # k — same as K for the non-stroking colour.
        if len(operands) < 4:
            return
        c, m, y, k = (_to_float(operands[i]) for i in range(4))
        self._gs.fill_rgb = _cmyk_to_rgb_bytes(c, m, y, k)
        self._gs.fill_color_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceCMYK"]
        self._gs.fill_pattern = None

    # ---- pattern / shading colour selection (cs / CS / scn / SCN) ----

    def _op_set_stroke_color_space(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # CS — selects the stroking colour space. Stores the resolved PD
        # wrapper on ``stroke_color_space`` so a subsequent ``SCN`` can run
        # its component vector through the right ``to_rgb`` transform.
        # /Pattern is special-cased — no transform applies, the components
        # carry an underlying-tint payload that the pattern paints itself.
        #
        # PDF 32000-1 §8.6.5.1 + upstream
        # ``SetStrokingColorSpace.process`` reset the current colour to
        # the colour space's initial colour (typically black for
        # RGB/Gray/CMYK, [0.0] for indexed). Honour that here so a
        # ``CS … S`` without an intervening ``SCN`` paints in the
        # colour space's initial colour instead of the previous value.
        self._gs.stroke_pattern_tint = None
        if not operands or not isinstance(operands[0], COSName):
            self._gs.stroke_pattern = None
            self._gs.stroke_color_space = None
            return
        name: COSName = operands[0]
        if name.name == "Pattern":
            self._gs.stroke_color_space = None
            return
        self._gs.stroke_pattern = None
        cs = self._resolve_color_space(name)
        self._gs.stroke_color_space = cs
        rgb = self._initial_color_rgb(cs)
        if rgb is not None:
            self._gs.stroke_rgb = rgb

    def _op_set_fill_color_space(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # cs — non-stroking colour space. Mirrors ``_op_set_stroke_color_space``.
        self._gs.fill_pattern_tint = None
        if not operands or not isinstance(operands[0], COSName):
            self._gs.fill_pattern = None
            self._gs.fill_color_space = None
            return
        name = operands[0]
        if name.name == "Pattern":
            self._gs.fill_color_space = None
            return
        self._gs.fill_pattern = None
        cs = self._resolve_color_space(name)
        self._gs.fill_color_space = cs
        rgb = self._initial_color_rgb(cs)
        if rgb is not None:
            self._gs.fill_rgb = rgb

    def _initial_color_rgb(
        self, colour_space: Any | None
    ) -> tuple[int, int, int] | None:
        """Return the 8-bit RGB triple for ``colour_space``'s initial
        colour (per PDF 32000-1 §8.6.4 / upstream
        ``PDColorSpace.getInitialColor``). Returns ``None`` when the
        colour space is missing or the conversion fails."""
        if colour_space is None:
            return None
        get_initial_color = getattr(colour_space, "get_initial_color", None)
        if not callable(get_initial_color):
            return None
        try:
            initial = get_initial_color()
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: get_initial_color on %s failed: %s",
                type(colour_space).__name__,
                exc,
            )
            return None
        if initial is None:
            return None
        components = getattr(initial, "_components", None)
        if components is None:
            components = getattr(initial, "components", None)
        if not components:
            return None
        return self._color_components_to_rgb(tuple(components), colour_space)

    def _resolve_color_space(self, name: COSName) -> Any | None:
        """Return the ``PDColorSpace`` named in /Resources/ColorSpace or
        one of the built-in singletons (DeviceGray / DeviceRGB / DeviceCMYK
        / Pattern). Returns ``None`` if the name doesn't resolve."""
        # Built-in device + pattern names — mirrors upstream
        # PDColorSpace.create(name, …) name-dispatch.
        builtin = _BUILTIN_DEVICE_COLOR_SPACES.get(name.name)
        if builtin is not None:
            return builtin
        resources = self._resources
        if resources is None:
            return None
        try:
            return resources.get_color_space(name)
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: cannot resolve colour space %s: %s", name.name, exc
            )
            return None

    def _op_set_stroke_color_n(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # SCN — last operand is a /PatternName when the current colour space
        # is /Pattern; otherwise all operands are colour components in the
        # current stroking colour space. Wire both forms.
        #
        # Uncolored tiling patterns (PaintType=2, PDF 32000-1 §8.7.3.3):
        # the *leading* N components are the tint colour the pattern paints
        # with. The pattern's content stream operates against this tint,
        # which is converted to RGB via the underlying ("alternate") colour
        # space carried on the Pattern CS. Mirrors upstream
        # ``TilingPaintFactory.create`` building a tint ``PDColor`` over
        # the Pattern's underlying CS.
        pattern = self._resolve_pattern_operand(operands)
        if pattern is not None:
            self._gs.stroke_pattern = pattern
            self._gs.stroke_pattern_tint = self._extract_pattern_tint_rgb(
                operands, self._gs.stroke_color_space
            )
            return
        self._gs.stroke_pattern = None
        self._gs.stroke_pattern_tint = None
        components = _coerce_color_components(operands)
        if components is None:
            return
        rgb = self._color_components_to_rgb(
            components, self._gs.stroke_color_space
        )
        if rgb is not None:
            self._gs.stroke_rgb = rgb

    def _op_set_fill_color_n(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # scn — non-stroking equivalent of SCN.
        pattern = self._resolve_pattern_operand(operands)
        if pattern is not None:
            self._gs.fill_pattern = pattern
            self._gs.fill_pattern_tint = self._extract_pattern_tint_rgb(
                operands, self._gs.fill_color_space
            )
            return
        self._gs.fill_pattern = None
        self._gs.fill_pattern_tint = None
        components = _coerce_color_components(operands)
        if components is None:
            return
        rgb = self._color_components_to_rgb(
            components, self._gs.fill_color_space
        )
        if rgb is not None:
            self._gs.fill_rgb = rgb

    def _extract_pattern_tint_rgb(
        self,
        operands: list[COSBase],
        pattern_color_space: Any | None,
    ) -> tuple[int, int, int] | None:
        """Pull the leading-N tint components out of an ``scn`` / ``SCN``
        call that selected a pattern, and resolve them to an RGB triple
        via the Pattern CS's underlying ("alternate") colour space.
        Returns ``None`` when no tint components are present (Type 1
        colored tiling, or shading) — the pattern then paints its own
        colours.
        """
        if not operands:
            return None
        # The pattern name is the trailing operand; everything before is
        # numeric (PDNumber) — those are the tint components.
        components: list[float] = []
        for op in operands[:-1]:
            if isinstance(op, COSName):
                return None
            if hasattr(op, "float_value"):
                components.append(float(op.float_value()))
                continue
            if hasattr(op, "int_value"):
                components.append(float(op.int_value()))
                continue
            try:
                components.append(float(op))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
        if not components:
            return None
        # Locate the underlying colour space — for the array form
        # ``[/Pattern <CS>]`` PDPattern carries it on ``_underlying``.
        underlying = None
        if pattern_color_space is not None:
            get_underlying = getattr(
                pattern_color_space, "get_underlying_color_space", None
            )
            if callable(get_underlying):
                underlying = get_underlying()
        return self._color_components_to_rgb(tuple(components), underlying)

    def _color_components_to_rgb(
        self,
        components: tuple[float, ...],
        colour_space: Any | None,
    ) -> tuple[int, int, int] | None:
        """Run *components* through *colour_space*'s ``to_rgb``, returning
        an 8-bit ``(r, g, b)`` tuple. Defaults to DeviceGray for the n=1
        case and DeviceRGB for n=3 when no space is active. Returns
        ``None`` if conversion fails."""
        if colour_space is None:
            # Spec default: a fresh content stream's initial colour space
            # is DeviceGray. Use it for 1-component vectors; fall back to
            # DeviceRGB for 3-component, DeviceCMYK for 4.
            colour_space = _BUILTIN_DEVICE_COLOR_SPACES.get(
                {1: "DeviceGray", 3: "DeviceRGB", 4: "DeviceCMYK"}.get(
                    len(components), ""
                )
            )
            if colour_space is None:
                return None
        try:
            rgb_floats = colour_space.to_rgb(components)
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: colour-space %s to_rgb failed for %s: %s",
                type(colour_space).__name__,
                components,
                exc,
            )
            return None
        if (
            rgb_floats is None
            or not isinstance(rgb_floats, (tuple, list))
            or len(rgb_floats) < 3
        ):
            return None
        return _rgb_bytes(rgb_floats[0], rgb_floats[1], rgb_floats[2])

    def _resolve_pattern_operand(
        self, operands: list[COSBase]
    ) -> Any | None:
        """Look up a ``/Pattern`` resource named by the trailing operand of
        a ``scn`` / ``SCN`` call. Returns ``None`` when the operand isn't a
        name, the resource is missing, or the pattern can't be wrapped."""
        if not operands:
            return None
        last = operands[-1]
        if not isinstance(last, COSName):
            return None
        resources = self._resources
        if resources is None:
            return None
        try:
            return resources.get_pattern(last)
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: cannot resolve pattern %s: %s", last.name, exc
            )
            return None

    # ---- shading-fill operator (sh) ----

    def _op_shading_fill(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        # sh /Name — paint the named shading over the current clipping
        # region. The shading is fetched from the current /Resources
        # /Shading sub-dict.
        if not operands or not isinstance(operands[0], COSName):
            return
        if self._draw is None or self._image is None:
            return
        name: COSName = operands[0]
        resources = self._resources
        if resources is None:
            return
        try:
            shading = resources.get_shading(name)
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: cannot resolve shading %s: %s", name.name, exc
            )
            return
        if shading is None:
            return
        self._paint_shading(shading, region_mask=None)

    # ---- line state ----

    def _op_line_width(self, _op: Any, operands: list[COSBase]) -> None:
        if not operands:
            return
        self._gs.line_width = max(0.0, _to_float(operands[0]))

    # ---- ExtGState (gs operator — PDF spec §8.4.5 / §11.3.5) ----

    def _op_set_graphics_state_parameters(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        """``gs`` — apply the named ExtGState dictionary's parameters.

        Mirrors the entries enumerated in
        :meth:`PDExtendedGraphicsState.copy_into_graphics_state`
        (upstream ``copyIntoGraphicsState``):

        * ``/LW`` line width, ``/LC`` cap, ``/LJ`` join, ``/ML`` miter limit,
          ``/D`` dash pattern, ``/RI`` rendering intent — stroke-state plumb-
          through (PDF 32000-1 §8.4.3 + §8.6.5.8).
        * ``/Font [font size]`` — text font + size pair (§9.3.1).
        * ``/BM`` blend mode (§11.3.5), ``/SMask`` soft mask (§11.6.5.3),
          ``/CA`` stroke alpha + ``/ca`` non-stroke alpha (§11.6.4.4),
          ``/AIS`` alpha-is-shape (§11.6.4.3).
        * ``/FL`` flatness tolerance, ``/SM`` smoothness tolerance,
          ``/SA`` stroke adjustment, ``/TK`` text knockout — carried on
          the GS for parity-test bookkeeping; the lite renderer doesn't
          consult them at paint time.

        Deferred (don't affect skia-rendered output but the GS fields are
        carried elsewhere): ``/OP``/``/op``/``/OPM`` (overprint — affects
        colour separations we don't model), ``/BG``/``/BG2``/``/UCR``/``/UCR2``
        (CMYK device-gamut mapping), ``/TR``/``/TR2`` (output-device transfer
        function), ``/HT`` (halftone)."""
        if not operands or not isinstance(operands[0], COSName):
            return
        if self._resources is None:
            return
        name = operands[0]
        try:
            ext_gstate = self._resources.get_ext_gstate(name)
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: cannot resolve ExtGState %s: %s", name.name, exc
            )
            return
        if ext_gstate is None:
            return
        try:
            bm = ext_gstate.get_blend_mode()
        except Exception:  # noqa: BLE001
            bm = None
        # ``Normal`` (or unset) → leave blend_mode as None for the cheap
        # alpha-over hot path; only stash the wrapper for non-Normal modes.
        from pypdfbox.pdmodel.graphics.blend_mode import (  # noqa: PLC0415
            BlendMode,
        )

        if bm is None or bm is BlendMode.NORMAL:
            self._gs.blend_mode = None
        else:
            self._gs.blend_mode = bm

        # ---- /SMask (soft mask) — §11.6.5.3 ----
        # ``/None`` resets to "no soft mask"; a dict wraps as PDSoftMask
        # and is honoured at compositing time. Anything malformed is
        # logged at debug and treated as ``/None``.
        try:
            smask_typed = ext_gstate.get_soft_mask_typed()
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: cannot resolve ExtGState /SMask on %s: %s",
                name.name, exc,
            )
            smask_typed = None
        self._gs.soft_mask = smask_typed

        # ---- /CA (stroke alpha) and /ca (non-stroke alpha) ----
        try:
            ca = ext_gstate.get_stroking_alpha_constant()
        except Exception:  # noqa: BLE001
            ca = None
        if ca is not None:
            self._gs.stroke_alpha = max(0.0, min(1.0, float(ca)))
        try:
            ca_ns = ext_gstate.get_non_stroking_alpha_constant()
        except Exception:  # noqa: BLE001
            ca_ns = None
        if ca_ns is not None:
            self._gs.fill_alpha = max(0.0, min(1.0, float(ca_ns)))

        # ---- /LW (line width) — §8.4.3.2 ----
        try:
            lw = ext_gstate.get_line_width()
        except Exception:  # noqa: BLE001
            lw = None
        if lw is not None:
            self._gs.line_width = max(0.0, float(lw))

        # ---- /LC (line cap) — §8.4.3.3 ----
        try:
            lc = ext_gstate.get_line_cap_style()
        except Exception:  # noqa: BLE001
            lc = None
        if lc is not None:
            cap = int(lc)
            if cap < 0:
                cap = 0
            elif cap > 2:
                cap = 2
            self._gs.line_cap = cap

        # ---- /LJ (line join) — §8.4.3.4 ----
        try:
            lj = ext_gstate.get_line_join_style()
        except Exception:  # noqa: BLE001
            lj = None
        if lj is not None:
            join = int(lj)
            if join < 0:
                join = 0
            elif join > 2:
                join = 2
            self._gs.line_join = join

        # ---- /ML (miter limit) — §8.4.3.5 ----
        try:
            ml = ext_gstate.get_miter_limit()
        except Exception:  # noqa: BLE001
            ml = None
        if ml is not None:
            try:
                miter = float(ml)
            except (TypeError, ValueError):
                miter = None
            if miter is not None and miter > 0.0:
                self._gs.miter_limit = miter

        # ---- /D (line dash pattern) — §8.4.3.6 ----
        try:
            dash = ext_gstate.get_line_dash_pattern()
        except Exception:  # noqa: BLE001
            dash = None
        if dash is not None:
            try:
                arr = tuple(float(x) for x in dash.get_dash_array())
                phase = float(dash.get_phase())
            except Exception:  # noqa: BLE001
                arr = None
            else:
                # Empty dash array means "solid" per spec — store as None
                # so downstream code can short-circuit cleanly.
                self._gs.dash_pattern = (
                    None if not arr else (arr, phase)
                )

        # ---- /RI (rendering intent) — §8.6.5.8 ----
        try:
            ri = ext_gstate.get_rendering_intent()
        except Exception:  # noqa: BLE001
            ri = None
        if ri is not None:
            self._gs.rendering_intent = str(ri)

        # ---- /Font [font size] — §9.3.1 ----
        try:
            font_setting = ext_gstate.get_font_setting()
        except Exception:  # noqa: BLE001
            font_setting = None
        if font_setting is not None:
            try:
                font_obj = font_setting.get_font()
                font_size = font_setting.get_font_size()
            except Exception:  # noqa: BLE001
                font_obj = None
                font_size = None
            if font_obj is not None:
                self._gs.text_font = font_obj
            if font_size is not None and font_size > 0.0:
                self._gs.text_font_size = float(font_size)

        # ---- /AIS (alpha-is-shape) — §11.6.4.3 ----
        with contextlib.suppress(Exception):
            self._gs.alpha_is_shape = bool(ext_gstate.get_alpha_source_flag())

        # ---- /TK (text knockout) — §9.3.8 ----
        with contextlib.suppress(Exception):
            self._gs.text_knockout = bool(ext_gstate.get_text_knockout_flag())

        # ---- /FL (flatness tolerance) — §10.6.2 ----
        try:
            fl = ext_gstate.get_flatness()
        except Exception:  # noqa: BLE001
            fl = None
        if fl is not None:
            with contextlib.suppress(TypeError, ValueError):
                self._gs.flatness = float(fl)

        # ---- /SM (smoothness tolerance) — §10.6.3 ----
        try:
            sm = ext_gstate.get_smoothness()
        except Exception:  # noqa: BLE001
            sm = None
        if sm is not None:
            with contextlib.suppress(TypeError, ValueError):
                self._gs.smoothness = float(sm)

        # ---- /SA (stroke adjustment) — §10.6.5 ----
        with contextlib.suppress(Exception):
            self._gs.stroke_adjustment = bool(
                ext_gstate.get_stroke_adjustment()
            )

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
        assert self._current_subpath is not None
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

        # Pattern / shading fill — handled separately so the path mask is
        # filled with tile/gradient pixels rather than a solid colour. The
        # stroke (if any) still goes through aggdraw with the solid stroke
        # colour after the pattern fill commits.
        if fill and self._gs.fill_pattern is not None:
            self._paint_pattern_fill(even_odd=even_odd)
            if stroke:
                clip_mask = self._gs.clip_mask
                if clip_mask is not None:
                    # Re-feed through the clip path for the stroke.
                    self._paint_through_clip(
                        stroke=True, fill=False, even_odd=False,
                        clip_mask=clip_mask,
                    )
                else:
                    self._stroke_via_aggdraw()
            self._apply_pending_clip(default_even_odd=even_odd)
            self._reset_path()
            return

        clip_mask = self._gs.clip_mask
        # Wave 1384 — when an ExtGState /SMask is active and we're NOT
        # already inside a transparency group (where the mask applies at
        # composite time), each direct fill/stroke must be modulated by
        # the mask alpha plane. Mirrors upstream's ``applySoftMaskToPaint``
        # invoked from ``getNonStrokingPaint`` / ``getStrokingPaint`` in
        # PageDrawer.java.
        active_soft_mask = (
            self._gs.soft_mask if self._transparency_group_depth == 0 else None
        )
        if clip_mask is not None or active_soft_mask is not None:
            # Draw onto a fresh transparent layer, then composite via clip
            # and/or soft mask.
            self._paint_through_clip(
                stroke=stroke,
                fill=fill,
                even_odd=even_odd,
                clip_mask=clip_mask,
                soft_mask=active_soft_mask,
            )
        elif stroke or fill:
            # Wave 1330B — skia's PathFillType.kEvenOdd is honoured natively
            # by drawPath, so even-odd fills no longer need the
            # PIL-flatten-and-mask detour.  The legacy
            # ``_fill_even_odd_via_pil`` helper is preserved for parity
            # tests that pin the old behaviour pixel-for-pixel.
            self._draw_via_aggdraw(stroke=stroke, fill=fill, even_odd=even_odd)

        self._apply_pending_clip(default_even_odd=even_odd)
        self._reset_path()

    def _paint_through_clip(
        self,
        *,
        stroke: bool,
        fill: bool,
        even_odd: bool,
        clip_mask: Image.Image | None,
        soft_mask: Any | None = None,
    ) -> None:
        """Composite the painted result through ``clip_mask`` / ``soft_mask``.

        Strategy: render the path onto a fresh transparent RGBA layer,
        then ``Image.composite(layer, base, layer.split()[3] * clip_mask
        * soft_mask_alpha)`` so anything outside the clip drops back to
        the existing pixels and the soft mask further modulates alpha.

        Wave 1384 — accepts an active ExtGState ``/SMask`` (``soft_mask``)
        and multiplies the rendered soft-mask alpha plane into the layer
        alpha. Mirrors upstream's ``applySoftMaskToPaint`` (PageDrawer.java
        line 606) which wraps the paint inside a ``SoftMask`` AWT paint.
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
            if stroke or fill:
                # Wave 1330B — even-odd fills go through the native
                # skia path (PathFillType.kEvenOdd) inside the shim.
                self._draw_via_aggdraw(
                    stroke=stroke, fill=fill, even_odd=even_odd,
                )
            # ensure the layer's aggdraw buffer is committed so layer's
            # alpha channel reflects the strokes/fills.
            self_draw = self._draw
            if self_draw is not None:
                self_draw.flush()
            # NB: ``self._draw`` may have been replaced mid-paint by the
            # even-odd PIL path — refetch the latest layer image.
            painted_layer = self._image
            assert painted_layer is not None
            layer = painted_layer
        finally:
            self._draw = prev_draw
            self._image = prev_image

        # Combine layer alpha with clip mask + soft mask:
        # out_alpha = layer.a * clip * smask_alpha / 255**k.
        layer_alpha = layer.split()[3]
        combined = layer_alpha
        if clip_mask is not None:
            combined = ImageChops.multiply(combined, clip_mask)
        if soft_mask is not None:
            try:
                mask_alpha = self._render_soft_mask_alpha(
                    soft_mask, (width_px, height_px)
                )
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: soft-mask paint failed: %s", exc)
                mask_alpha = None
            if mask_alpha is not None:
                combined = ImageChops.multiply(combined, mask_alpha)
        # Composite the layer's RGB onto the base image using the combined mask.
        rgb = layer.convert("RGB")
        prev_image.paste(rgb, (0, 0), combined)
        # Re-attach aggdraw to the (mutated) base image.
        self._draw = aggdraw.Draw(prev_image)
        self._draw.setantialias(True)

    def _draw_via_aggdraw(
        self, *, stroke: bool, fill: bool, even_odd: bool = False,
    ) -> None:
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
        # Compute the CTM once — used both for settransform and for the
        # stroke-width scale factor.  (Wave 1330B trim — was previously
        # recomputed twice per draw call.)
        full_ctm = self._full_ctm()
        self._draw.settransform(_to_pil_affine(full_ctm))
        try:
            pen: aggdraw.Pen | None = None
            brush: aggdraw.Brush | None = None
            if stroke:
                # Convert PDF user-space line width to device-pixel width
                # so thin strokes don't disappear at sub-pixel widths.
                # Use a representative scale factor (sqrt(|det(CTM)|)).
                scale = self._approx_scale(full_ctm)
                width_px = max(1.0, self._gs.line_width * scale)
                pen = aggdraw.Pen(self._gs.stroke_rgb, width=width_px)
            if fill:
                brush = aggdraw.Brush(self._gs.fill_rgb)
            # ``even_odd=`` is a wave-1330B shim extension — aggdraw had
            # no fill-rule knob.
            self._draw.path(path, pen, brush, even_odd=even_odd)
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
        self, subpath: list[_PathSegment], ctm: _Matrix
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
            if tag in {"M", "L"}:
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

    # ---- pattern + shading fill helpers ----

    def _build_path_mask(self, *, even_odd: bool) -> Image.Image | None:
        """Rasterise the current path into a same-size ``"L"`` PIL mask.

        Used by tiling-pattern and shading fill to bound the painted region
        to the path's interior. Returns ``None`` when no subpaths produce a
        polygon (degenerate / empty path).

        Wave 1373: replaced the legacy Bezier-flatten + XOR-per-subpath
        mask construction with a direct ``skia.Path`` rasterisation —
        skia honours ``PathFillType.kEvenOdd`` natively with full sub-
        pixel anti-aliasing on the outer edge, eliminating the documented
        AA loss the XOR path exhibited.
        """
        if self._image is None:
            return None
        mask = self._build_skia_path_alpha_mask(even_odd=even_odd)
        return mask

    def _build_skia_path_alpha_mask(
        self, *, even_odd: bool,
    ) -> Image.Image | None:
        """Rasterise the current subpaths through skia and return the
        alpha channel as an ``"L"`` PIL image (same size as ``_image``).

        Anti-aliasing on the path outline is preserved because skia
        renders with sub-pixel alpha; both even-odd and non-zero fill
        rules are handled natively via ``skia.PathFillType``.
        """
        if self._image is None:
            return None
        # Defer the skia import to keep the renderer module load light.
        import skia  # noqa: PLC0415

        width_px, height_px = self._image.size
        sk_path = skia.Path()
        any_segments = False
        for subpath in self._subpaths:
            for seg in subpath:
                tag = seg[0]
                if tag == "M":
                    sk_path.moveTo(float(seg[1]), float(seg[2]))
                    any_segments = True
                elif tag == "L":
                    sk_path.lineTo(float(seg[1]), float(seg[2]))
                    any_segments = True
                elif tag == "C":
                    sk_path.cubicTo(
                        float(seg[1]), float(seg[2]),
                        float(seg[3]), float(seg[4]),
                        float(seg[5]), float(seg[6]),
                    )
                    any_segments = True
                elif tag == "Z":
                    sk_path.close()
        if not any_segments:
            return None
        # Degenerate paths (single point, all-collinear, zero-area) carry
        # no fillable interior; mirror the legacy len(polygon) < 3 short-
        # circuit by checking the path's bounding box. Skia would render
        # nothing for them but still allocate a buffer.
        bounds = sk_path.getBounds()
        if (
            bounds.width() <= 0.0
            or bounds.height() <= 0.0
            or not (math.isfinite(bounds.width()) and math.isfinite(bounds.height()))
        ):
            return None
        sk_path.setFillType(
            skia.PathFillType.kEvenOdd if even_odd
            else skia.PathFillType.kWinding,
        )
        return self._build_skia_path_alpha_mask_rgba(
            sk_path, width_px, height_px,
        )

    def _build_skia_path_alpha_mask_rgba(
        self, sk_path: Any, width_px: int, height_px: int,
    ) -> Image.Image | None:
        """Rasterise the path into an RGBA buffer and extract the alpha
        channel as an ``"L"`` PIL image.
        """
        import skia  # noqa: PLC0415

        row_bytes = width_px * 4
        pixels = bytearray(width_px * height_px * 4)
        info = skia.ImageInfo.Make(
            width_px, height_px,
            skia.kRGBA_8888_ColorType,
            skia.kUnpremul_AlphaType,
        )
        surface = skia.Surface.MakeRasterDirect(info, pixels, row_bytes)
        if surface is None:  # pragma: no cover - skia always succeeds
            return None
        canvas = surface.getCanvas()
        # PDF CTM (a, b, c, d, e, f) maps (x, y) → (a*x + c*y + e,
        # b*x + d*y + f). Skia's MakeAll takes a row-vector matrix
        # (scaleX, skewX, transX, skewY, scaleY, transY) where
        # x' = scaleX*x + skewX*y + transX, so the PDF tuple is
        # transposed via the same helper aggdraw uses.
        a, b, c_, d, e, f = self._full_ctm()
        canvas.setMatrix(
            skia.Matrix.MakeAll(a, c_, e, b, d, f, 0.0, 0.0, 1.0),
        )
        paint = skia.Paint(
            Color=skia.ColorSetARGB(255, 255, 255, 255),
            Style=skia.Paint.kFill_Style,
            AntiAlias=True,
        )
        canvas.drawPath(sk_path, paint)
        surface.flushAndSubmit()
        rgba = Image.frombytes(
            "RGBA", (width_px, height_px), bytes(pixels),
        )
        return rgba.split()[3]

    def _paint_pattern_fill(self, *, even_odd: bool) -> None:
        """Dispatch a pattern fill to the right helper. Tiling vs. shading
        is decided on the resolved ``PDAbstractPattern`` instance.
        Falls back to a solid fill (using the GS ``fill_rgb``) for any
        pattern type we don't yet rasterise."""
        # Local import — pattern types live in pdmodel.graphics.pattern and
        # we don't want to drag them into renderer module load time.
        from pypdfbox.pdmodel.graphics.pattern import (  # noqa: PLC0415
            PDShadingPattern,
            PDTilingPattern,
        )

        pattern = self._gs.fill_pattern
        if pattern is None:
            return
        mask = self._build_path_mask(even_odd=even_odd)
        if mask is None:
            return
        # Compose with current clip mask, if any.
        clip_mask = self._gs.clip_mask
        if clip_mask is not None:
            mask = ImageChops.multiply(mask, clip_mask)

        if isinstance(pattern, PDTilingPattern):
            self._paint_tiling_pattern(pattern, region_mask=mask)
            return
        if isinstance(pattern, PDShadingPattern):
            shading = pattern.get_shading()
            if shading is not None:
                self._paint_shading(shading, region_mask=mask)
                return
        # Unknown / unsupported — fall back to solid fill.
        _log.debug(
            "rendering: unsupported pattern type %s; falling back to solid",
            type(pattern).__name__,
        )
        self._fill_mask_with_rgb(mask, self._gs.fill_rgb)

    def _fill_mask_with_rgb(
        self, mask: Image.Image, rgb: tuple[int, int, int]
    ) -> None:
        """Paint ``rgb`` onto the canvas wherever ``mask`` is non-zero."""
        if self._image is None or self._draw is None:
            return
        self._draw.flush()
        if self._image.mode == "RGBA":
            r, g, b = rgb
            layer = Image.new("RGBA", self._image.size, (r, g, b, 255))
        else:
            layer = Image.new("RGB", self._image.size, rgb)
        self._image.paste(layer, (0, 0), mask)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _paint_tiling_pattern(
        self,
        pattern: Any,
        *,
        region_mask: Image.Image | None,
    ) -> None:
        """Render a ``PDTilingPattern`` onto the canvas, bounded by
        ``region_mask`` (the path interior in device space).

        Strategy: rasterise one cell of the pattern's content stream into a
        Pillow tile sized by ``/BBox``+``/XStep``+``/YStep``, then tile that
        tile across the canvas via repeated ``Image.paste`` and composite
        through ``region_mask``.
        """
        if self._image is None or self._draw is None or region_mask is None:
            return
        bbox = pattern.get_b_box()
        x_step = pattern.get_x_step()
        y_step = pattern.get_y_step()
        if bbox is None or x_step <= 0.0 or y_step <= 0.0:
            _log.debug(
                "rendering: tiling pattern missing /BBox or /XStep/YStep"
            )
            return
        # Render one cell. We want the cell as it appears under the page's
        # current CTM scaled by the device CTM, so the tile pixel
        # dimensions match the on-page dimensions (i.e. one device pixel per
        # device pixel).
        full_ctm = self._full_ctm()
        # Tile bounding-box dimensions in user space.
        bbox_w = bbox.get_width()
        bbox_h = bbox.get_height()
        if bbox_w <= 0.0 or bbox_h <= 0.0:
            return
        # Scale factor from user space to device pixels (same metric used
        # for stroke-width up-conversion).
        scale = self._approx_scale(full_ctm)
        # Tile size in device pixels — at least 1 px to avoid zero-size
        # PIL images.
        tile_w_px = max(1, int(round(x_step * scale)))
        tile_h_px = max(1, int(round(y_step * scale)))
        # BBox-sized cell region in device pixels (PDF 32000-1 §8.7.3.3:
        # the cell paints into a /BBox sub-region of the (XStep, YStep)
        # lattice; when /XStep or /YStep is larger than /BBox the gap
        # remains transparent. Clamp to the tile size — when the cell is
        # larger than the step (overlap case), the lattice still steps by
        # (XStep, YStep) and successive tiles paint over each other so
        # rendering the cell at min(bbox, step) keeps the visible result
        # correct without leaking past the next tile origin).
        bbox_w_px = max(1, min(tile_w_px, int(round(bbox.get_width() * scale))))
        bbox_h_px = max(1, min(tile_h_px, int(round(bbox.get_height() * scale))))

        # PaintType=2 uncolored tiling: seed the recursive _GState with
        # the tint colour so any cell op that consults the active fill /
        # stroke colour (e.g. plain ``f`` after a ``re``) paints in the
        # tint. PaintType=1 (colored) ignores the tint — the cell's own
        # content stream supplies all colour ops.
        tint_rgb: tuple[int, int, int] | None = None
        if (
            hasattr(pattern, "get_paint_type")
            and pattern.get_paint_type() == 2
        ):
            tint_rgb = self._gs.fill_pattern_tint

        try:
            tile = self._render_tiling_cell(
                pattern,
                bbox=bbox,
                tile_size=(tile_w_px, tile_h_px),
                cell_size=(bbox_w_px, bbox_h_px),
                tint_rgb=tint_rgb,
            )
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: tiling pattern cell render failed: %s", exc)
            return
        if tile is None:
            return

        # Build a same-size composed canvas of repeated tiles, then paste
        # through ``region_mask``. The tile carries an alpha channel so
        # gap pixels between /BBox cells (when /XStep or /YStep exceeds
        # the cell dimension) stay transparent and the page background
        # shows through.
        self._draw.flush()
        canvas_w, canvas_h = self._image.size
        tiled = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        for ty in range(0, canvas_h, tile_h_px):
            for tx in range(0, canvas_w, tile_w_px):
                tiled.paste(tile, (tx, ty))
        # Combine the tiled alpha with ``region_mask`` so only the path
        # interior receives pattern pixels and only the cell-painted
        # portion of each tile contributes (gap pixels stay transparent).
        tiled_alpha = tiled.split()[3]
        combined = ImageChops.multiply(tiled_alpha, region_mask)
        rgb_tile = tiled.convert("RGB")
        self._image.paste(rgb_tile, (0, 0), combined)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _render_tiling_cell(
        self,
        pattern: Any,
        *,
        bbox: Any,
        tile_size: tuple[int, int],
        cell_size: tuple[int, int] | None = None,
        tint_rgb: tuple[int, int, int] | None = None,
    ) -> Image.Image | None:
        """Render one cell of ``pattern`` to a fresh PIL image of size
        ``tile_size``.

        ``cell_size`` is the device-pixel footprint of the pattern's
        ``/BBox`` and defaults to ``tile_size`` (legacy behaviour). When
        ``/XStep`` or ``/YStep`` exceeds the cell dimension the cell
        paints only the cell-sized region of the tile and the surrounding
        pixels stay fully transparent (PDF 32000-1 §8.7.3.3).

        ``tint_rgb`` is the tint colour for ``PaintType=2`` (uncolored)
        tiling patterns — used to seed the recursive ``_GState``'s fill
        and stroke colours so the cell's content stream paints in the
        tint when it doesn't explicitly set a colour. ``None`` (default)
        means ``PaintType=1`` (colored) tiling — the cell paints its own
        colours.

        Internally swaps in a sub-renderer state targeting the tile image
        and feeds the pattern's content stream through the existing
        operator dispatch loop. The page state is saved + restored around
        the recursion so the outer render isn't disturbed.
        """
        cos_stream = pattern.get_cos_object()
        if not isinstance(cos_stream, COSStream):
            return None
        data = cos_stream.to_byte_array()
        if cell_size is None:
            cell_size = tile_size
        if not data:
            # Empty content stream — produce a fully transparent tile so
            # the caller's alpha-aware paste preserves the page background.
            return Image.new("RGBA", tile_size, (0, 0, 0, 0))

        tile_w, tile_h = tile_size
        cell_w, cell_h = cell_size
        # RGBA tile — transparent everywhere by default; the cell content
        # paints opaque pixels into the cell-sized sub-region.
        tile_image = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        bbox_w = bbox.get_width()
        bbox_h = bbox.get_height()
        if bbox_w <= 0.0 or bbox_h <= 0.0:
            return None
        bbox_x = bbox.get_lower_left_x()
        bbox_y = bbox.get_lower_left_y()
        # Affine that maps the pattern's /BBox onto the cell pixel
        # sub-region of the tile (origin (0, 0), size cell_size) with the
        # standard PDF y-flip baked in. When cell == tile this matches
        # the old behaviour; when cell < tile the extra strip on the
        # right / bottom remains transparent.
        sx = cell_w / bbox_w
        sy = cell_h / bbox_h
        tile_device_ctm: _Matrix = (
            sx, 0.0,
            0.0, -sy,
            -bbox_x * sx, bbox_y * sy + cell_h,
        )

        # Snapshot + replace per-render state for the recursion.
        prev_image = self._image
        prev_draw = self._draw
        prev_device_ctm = self._device_ctm
        prev_page_height = self._page_height_px
        prev_gs_stack = self._gs_stack
        prev_subpaths = self._subpaths
        prev_current_subpath = self._current_subpath
        prev_current_point = self._current_point
        prev_pending_clip = self._pending_clip
        prev_resources = self._resources

        self._image = tile_image
        self._draw = aggdraw.Draw(tile_image)
        self._draw.setantialias(True)
        self._device_ctm = tile_device_ctm
        # Use cell height for the page-height clip baseline so the y-flip
        # in operators that consult ``_page_height_px`` matches the
        # device-CTM we just installed.
        self._page_height_px = float(cell_h)
        # Seed the recursive _GState with the uncolored-tiling tint when
        # the caller supplied one — the cell's content stream then paints
        # in the tint for any op that consults the current colour without
        # setting it explicitly.
        cell_gs = _GState()
        if tint_rgb is not None:
            cell_gs.fill_rgb = tint_rgb
            cell_gs.stroke_rgb = tint_rgb
        self._gs_stack = [cell_gs]
        self._subpaths = []
        self._current_subpath = None
        self._current_point = (0.0, 0.0)
        self._pending_clip = None
        # Pattern resources live on the pattern's own /Resources dict.
        try:
            pattern_res = pattern.get_resources()
        except Exception:  # noqa: BLE001
            pattern_res = None
        if pattern_res is not None:
            self._resources = pattern_res

        try:
            self._process_form_bytes(data)
            current = self._draw
            if current is not None:
                current.flush()
        finally:
            self._image = prev_image
            self._draw = prev_draw
            self._device_ctm = prev_device_ctm
            self._page_height_px = prev_page_height
            self._gs_stack = prev_gs_stack
            self._subpaths = prev_subpaths
            self._current_subpath = prev_current_subpath
            self._current_point = prev_current_point
            self._pending_clip = prev_pending_clip
            self._resources = prev_resources

        return tile_image

    def _paint_shading(
        self,
        shading: Any,
        *,
        region_mask: Image.Image | None,
    ) -> None:
        """Render a ``PDShading`` onto the canvas. ``region_mask`` (when
        provided) restricts output to the path interior; ``None`` means
        "paint over the current clip / whole page" which is what the
        ``sh`` operator wants."""
        if self._image is None or self._draw is None:
            return
        # Local import to keep cluster boundaries explicit.
        from pypdfbox.pdmodel.graphics.shading import (  # noqa: PLC0415
            PDShadingType2,
            PDShadingType3,
        )

        # Region mask — for `sh`, default to the current clip if any, else
        # the full canvas.
        if region_mask is None:
            clip_mask = self._gs.clip_mask
            if clip_mask is not None:
                region_mask = clip_mask
            else:
                region_mask = Image.new("L", self._image.size, 255)

        if isinstance(shading, PDShadingType2):
            self._paint_axial_shading(shading, region_mask=region_mask)
            return
        if isinstance(shading, PDShadingType3):
            self._paint_radial_shading(shading, region_mask=region_mask)
            return
        from pypdfbox.pdmodel.graphics.shading import (  # noqa: PLC0415
            PDShadingType1,
            PDShadingType4,
            PDShadingType5,
            PDShadingType6,
            PDShadingType7,
        )

        if isinstance(shading, PDShadingType1):
            self._paint_function_shading(shading, region_mask=region_mask)
            return
        if isinstance(shading, (PDShadingType6, PDShadingType7)):
            # Wave 1375 — Coons (type 6) / tensor (type 7) patch mesh
            # rasterisation via N×N parametric subdivision.
            handled = self._paint_patch_mesh_shading(
                shading,
                region_mask=region_mask,
                control_points=16 if isinstance(shading, PDShadingType7) else 12,
            )
            if handled:
                return
            # Decode failure — fall through to the uniform-f(0) fallback.
        if isinstance(
            shading,
            (PDShadingType4, PDShadingType5, PDShadingType6, PDShadingType7),
        ):
            # Free-form / lattice Gouraud (types 4/5) still fall back to a
            # uniform fill at f(0); a future wave will port their
            # triangulator. Patch meshes only land here when ``parse_patches``
            # returned an empty list (no /Decode etc.).
            _log.debug(
                "rendering: mesh shading type %s deferred; falling back to f(0)",
                type(shading).__name__,
            )
            rgb = self._evaluate_shading_rgb(shading, 0.0)
            if rgb is None:
                return
            self._fill_mask_with_rgb(region_mask, _rgb_bytes(*rgb))
            return
        # Unknown/uncreated subclass — same fallback.
        _log.debug(
            "rendering: unsupported shading type %s; falling back to f(0)",
            type(shading).__name__,
        )
        rgb = self._evaluate_shading_rgb(shading, 0.0)
        if rgb is None:
            return
        self._fill_mask_with_rgb(region_mask, _rgb_bytes(*rgb))

    def _evaluate_shading_rgb(
        self, shading: Any, t: float
    ) -> tuple[float, float, float] | None:
        """Evaluate the shading's ``/Function`` at ``t`` and return an
        sRGB triple in [0, 1]. Returns ``None`` on failure (e.g. function
        type 0 / 4 — eval not yet implemented)."""
        try:
            fn = shading.get_function()
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: shading get_function failed: %s", exc)
            return None
        if fn is None:
            return None
        # Some shading subclasses (Type 2) return the raw ``/Function`` COS
        # object; others (Type 3) wrap into a typed ``PDFunction`` already.
        # Normalise via PDFunction.create() when ``fn`` lacks ``eval``.
        if not hasattr(fn, "eval"):
            try:
                from pypdfbox.pdmodel.common.function import (  # noqa: PLC0415
                    PDFunction,
                )

                fn = PDFunction.create(fn)
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: PDFunction.create failed: %s", exc)
                return None
            if fn is None:
                return None
        try:
            out = fn.eval([float(t)])
        except (NotImplementedError, Exception) as exc:  # noqa: BLE001
            _log.debug("rendering: shading function eval failed: %s", exc)
            return None
        if not out:
            return None
        # Honour the shading's /ColorSpace where possible. For DeviceRGB,
        # output is already 3 components in [0,1]. DeviceGray expands to
        # (g, g, g); DeviceCMYK uses the standard 1-x conversion. Anything
        # else falls back to padding/truncating to 3 channels.
        cs = None
        try:
            cs = shading.get_color_space()
        except Exception:  # noqa: BLE001
            cs = None
        cs_name = cs.name if isinstance(cs, COSName) else None
        if cs_name == "DeviceGray" or len(out) == 1:
            g = float(out[0])
            return (g, g, g)
        if cs_name == "DeviceCMYK" or len(out) == 4:
            c, m, y, k = (float(v) for v in out[:4])
            r = (1.0 - c) * (1.0 - k)
            g = (1.0 - m) * (1.0 - k)
            b = (1.0 - y) * (1.0 - k)
            return (r, g, b)
        # DeviceRGB / unknown 3-channel — pad with zeros if too short.
        padded = list(out) + [0.0, 0.0, 0.0]
        return (float(padded[0]), float(padded[1]), float(padded[2]))

    def _paint_axial_shading(
        self,
        shading: Any,
        *,
        region_mask: Image.Image,
    ) -> None:
        """Type 2 (axial) shading per PDF 32000-1 §8.7.4.5.3.

        ``/Coords`` = ``[x0 y0 x1 y1]`` in pattern user space. For each
        pixel in the region mask, project onto the axis to obtain
        ``u = ((x-x0)*(x1-x0) + (y-y0)*(y1-y0)) / |axis|^2``, clamp by
        ``/Extend``, then evaluate the function over ``/Domain``.
        """
        if self._image is None:
            return
        coords = shading.get_coords()
        if coords is None or coords.size() < 4:
            return
        x0 = _to_float(coords.get_object(0))
        y0 = _to_float(coords.get_object(1))
        x1 = _to_float(coords.get_object(2))
        y1 = _to_float(coords.get_object(3))
        dx = x1 - x0
        dy = y1 - y0
        denom = dx * dx + dy * dy
        if denom <= 0.0:
            return
        # Domain — default [0, 1] per spec.
        domain_lo, domain_hi = self._shading_domain(shading)
        # Extend — default [false, false] per spec.
        extend_start, extend_end = self._shading_extend(shading)

        # Inverse of the full CTM so device pixels can be mapped back to
        # pattern (user) space for axis projection.
        inv = self._invert_matrix(self._full_ctm())
        if inv is None:
            return

        canvas_w, canvas_h = self._image.size
        # Build an RGB pixel buffer for the painted region. Sample once
        # per pixel — straightforward and well within Pillow's sweet spot
        # for the small synthetic pages we render in tests. Larger pages
        # would benefit from numpy vectorisation; that's a perf cluster.
        pixels: list[int] = []
        mask_data = region_mask.tobytes()
        # Default fallback colour when function eval fails.
        fallback = (0, 0, 0)
        # Pre-evaluate a small ramp of colours and lerp. Cheap and
        # reasonably accurate for monotone Type 2 functions like
        # exponential interpolation.
        ramp_steps = 256
        ramp: list[tuple[int, int, int]] = []
        for i in range(ramp_steps):
            t = domain_lo + (domain_hi - domain_lo) * (i / (ramp_steps - 1))
            rgb = self._evaluate_shading_rgb(shading, t)
            if rgb is None:
                ramp.append(fallback)
            else:
                ramp.append(_rgb_bytes(*rgb))
        # Precompute the affine for inverse CTM application.
        ia, ib, ic, id_, ie, if_ = inv
        for py in range(canvas_h):
            row_off = py * canvas_w
            for px in range(canvas_w):
                if mask_data[row_off + px] == 0:
                    pixels.extend((255, 255, 255))
                    continue
                # Map device pixel -> pattern (user) space.
                ux = ia * px + ic * py + ie
                uy = ib * px + id_ * py + if_
                u = ((ux - x0) * dx + (uy - y0) * dy) / denom
                # Apply /Extend handling per §8.7.4.5.3.
                if u < 0.0:
                    if not extend_start:
                        pixels.extend((255, 255, 255))
                        continue
                    u = 0.0
                elif u > 1.0:
                    if not extend_end:
                        pixels.extend((255, 255, 255))
                        continue
                    u = 1.0
                # Map u in [0,1] to /Domain.
                t = domain_lo + (domain_hi - domain_lo) * u
                # Lerp into pre-evaluated ramp.
                if domain_hi == domain_lo:
                    idx = 0
                else:
                    idx = int(round(
                        (t - domain_lo) / (domain_hi - domain_lo)
                        * (ramp_steps - 1)
                    ))
                if idx < 0:
                    idx = 0
                elif idx >= ramp_steps:
                    idx = ramp_steps - 1
                r, g, b = ramp[idx]
                pixels.extend((r, g, b))

        gradient = Image.frombytes(
            "RGB", (canvas_w, canvas_h), bytes(pixels)
        )
        # Compose: use ``region_mask`` as the paste mask so only the
        # interior of the region picks up the gradient.
        self._draw.flush() if self._draw is not None else None
        self._image.paste(gradient, (0, 0), region_mask)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _paint_radial_shading(
        self,
        shading: Any,
        *,
        region_mask: Image.Image,
    ) -> None:
        """Type 3 (radial) shading per PDF 32000-1 §8.7.4.5.4.

        ``/Coords`` = ``[x0 y0 r0 x1 y1 r1]`` defines two circles. For
        each pixel, find the parameter ``s`` such that the pixel sits on
        the circle ``c(s) = ((1-s)*c0 + s*c1, (1-s)*r0 + s*r1)``. We solve
        the standard quadratic in ``s`` and pick the larger valid root
        (matches Adobe / Java2D behaviour).
        """
        if self._image is None:
            return
        coords = shading.get_coords()
        if coords is None or coords.size() < 6:
            return
        x0 = _to_float(coords.get_object(0))
        y0 = _to_float(coords.get_object(1))
        r0 = _to_float(coords.get_object(2))
        x1 = _to_float(coords.get_object(3))
        y1 = _to_float(coords.get_object(4))
        r1 = _to_float(coords.get_object(5))

        domain_lo, domain_hi = self._shading_domain(shading)
        extend_start, extend_end = self._shading_extend(shading)
        inv = self._invert_matrix(self._full_ctm())
        if inv is None:
            return

        canvas_w, canvas_h = self._image.size
        ramp_steps = 256
        ramp: list[tuple[int, int, int]] = []
        for i in range(ramp_steps):
            t = domain_lo + (domain_hi - domain_lo) * (i / (ramp_steps - 1))
            rgb = self._evaluate_shading_rgb(shading, t)
            ramp.append(_rgb_bytes(*rgb) if rgb is not None else (0, 0, 0))

        ia, ib, ic, id_, ie, if_ = inv
        dx = x1 - x0
        dy = y1 - y0
        dr = r1 - r0
        # Quadratic coefficients in s for ((x-cs)^2 + (y-cs')^2 = r(s)^2).
        a = dx * dx + dy * dy - dr * dr

        pixels: list[int] = []
        mask_data = region_mask.tobytes()
        for py in range(canvas_h):
            row_off = py * canvas_w
            for px in range(canvas_w):
                if mask_data[row_off + px] == 0:
                    pixels.extend((255, 255, 255))
                    continue
                ux = ia * px + ic * py + ie
                uy = ib * px + id_ * py + if_
                # Solve a*s^2 + b*s + c = 0 where:
                # b = -2*((ux-x0)*dx + (uy-y0)*dy + r0*dr)
                # c = (ux-x0)^2 + (uy-y0)^2 - r0^2
                bx = ux - x0
                by = uy - y0
                bcoef = -2.0 * (bx * dx + by * dy + r0 * dr)
                ccoef = bx * bx + by * by - r0 * r0
                s: float | None = None
                if abs(a) < 1e-12:
                    # Degenerate (parallel circles, equal radii) — linear.
                    if abs(bcoef) > 1e-12:
                        cand = -ccoef / bcoef
                        s = cand
                else:
                    disc = bcoef * bcoef - 4.0 * a * ccoef
                    if disc >= 0.0:
                        sqrt_disc = disc ** 0.5
                        s_plus = (-bcoef + sqrt_disc) / (2.0 * a)
                        s_minus = (-bcoef - sqrt_disc) / (2.0 * a)
                        # Pick the larger root that is in-range, falling
                        # back to the smaller one when it is.
                        candidates = sorted(
                            (s_minus, s_plus), reverse=True
                        )
                        for cand in candidates:
                            # Radius at this parameter must be non-negative.
                            radius = r0 + cand * dr
                            if radius < 0.0:
                                continue
                            s = cand
                            break
                if s is None:
                    pixels.extend((255, 255, 255))
                    continue
                if s < 0.0:
                    if not extend_start:
                        pixels.extend((255, 255, 255))
                        continue
                    s = 0.0
                elif s > 1.0:
                    if not extend_end:
                        pixels.extend((255, 255, 255))
                        continue
                    s = 1.0
                t = domain_lo + (domain_hi - domain_lo) * s
                if domain_hi == domain_lo:
                    idx = 0
                else:
                    idx = int(round(
                        (t - domain_lo) / (domain_hi - domain_lo)
                        * (ramp_steps - 1)
                    ))
                if idx < 0:
                    idx = 0
                elif idx >= ramp_steps:
                    idx = ramp_steps - 1
                r, g, b = ramp[idx]
                pixels.extend((r, g, b))

        gradient = Image.frombytes(
            "RGB", (canvas_w, canvas_h), bytes(pixels)
        )
        if self._draw is not None:
            self._draw.flush()
        self._image.paste(gradient, (0, 0), region_mask)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _paint_function_shading(
        self,
        shading: Any,
        *,
        region_mask: Image.Image,
    ) -> None:
        """Type 1 (function-based) shading per PDF 32000-1 §8.7.4.5.2.

        ``/Domain`` = ``[xmin xmax ymin ymax]`` defines a rectangle in
        the shading's parametric space; ``/Matrix`` (default identity)
        maps that rectangle into pattern user space; ``/Function`` is a
        2-input function (or array of 1-input functions, one per output
        component) that returns the colour at each ``(x, y)`` in domain
        space.

        For each output pixel: invert the device→user CTM to get pattern
        coordinates, invert the shading ``/Matrix`` to get domain
        coordinates, clip to ``/Domain``, then evaluate the function.
        """
        if self._image is None:
            return
        # Domain — 4 floats; default [0 1 0 1] per spec.
        domain_xmin, domain_xmax, domain_ymin, domain_ymax = (
            self._shading_domain_2d(shading)
        )
        if domain_xmax <= domain_xmin or domain_ymax <= domain_ymin:
            return
        # Optional /Matrix maps domain → pattern user space; identity by default.
        mtx = self._shading_matrix(shading)
        # Inverse so we can go pattern user → domain at each pixel.
        mtx_inv = self._invert_matrix(mtx)
        if mtx_inv is None:
            _log.debug("rendering: PDShadingType1 /Matrix is singular")
            return

        inv = self._invert_matrix(self._full_ctm())
        if inv is None:
            return
        ia, ib, ic, id_, ie, if_ = inv
        ma, mb, mc, md, me, mf = mtx_inv

        # Resolve the function once (PDFunction.eval handles 2-in/N-out).
        try:
            fn = shading.get_function()
        except Exception:  # noqa: BLE001
            fn = None
        if fn is None:
            _log.debug("rendering: PDShadingType1 missing /Function")
            return
        # Normalise: get_function may hand back a COSArray of per-channel
        # functions or a typed PDFunction. We need a callable that maps
        # [x, y] → [r, g, b...] in [0,1] regardless.
        from pypdfbox.pdmodel.common.function import PDFunction  # noqa: PLC0415

        if isinstance(fn, COSArray):
            # Array of single-output functions, one per colour component.
            sub_fns: list[Any] = []
            for i in range(fn.size()):
                entry = fn.get_object(i)
                if entry is None:
                    continue
                try:
                    sub_fns.append(PDFunction.create(entry))
                except Exception:  # noqa: BLE001
                    sub_fns.append(None)

            def evaluate(x: float, y: float) -> list[float]:
                out_vals: list[float] = []
                for sf in sub_fns:
                    if sf is None:
                        out_vals.append(0.0)
                        continue
                    try:
                        r = sf.eval([x, y])
                    except Exception:  # noqa: BLE001
                        out_vals.append(0.0)
                        continue
                    out_vals.append(float(r[0]) if r else 0.0)
                return out_vals
        else:
            if not hasattr(fn, "eval"):
                try:
                    fn = PDFunction.create(fn)
                except Exception:  # noqa: BLE001
                    fn = None
            if fn is None:
                return

            def evaluate(x: float, y: float) -> list[float]:
                try:
                    return list(fn.eval([x, y]))
                except Exception:  # noqa: BLE001
                    return []

        cs_obj = None
        try:
            cs_obj = shading.get_color_space()
        except Exception:  # noqa: BLE001
            cs_obj = None
        cs_name = cs_obj.name if isinstance(cs_obj, COSName) else None

        canvas_w, canvas_h = self._image.size
        pixels = bytearray(canvas_w * canvas_h * 3)
        mask_data = region_mask.tobytes()

        # Sample colours through a small cache keyed by quantised (x,y) so
        # adjacent pixels don't all re-pay the function eval.
        cache_grid = 256
        cache: dict[tuple[int, int], tuple[int, int, int]] = {}
        bg = (255, 255, 255)
        for py in range(canvas_h):
            row_off = py * canvas_w
            for px in range(canvas_w):
                base = (row_off + px) * 3
                if mask_data[row_off + px] == 0:
                    pixels[base] = bg[0]
                    pixels[base + 1] = bg[1]
                    pixels[base + 2] = bg[2]
                    continue
                # device → pattern user
                ux = ia * px + ic * py + ie
                uy = ib * px + id_ * py + if_
                # pattern user → domain via inverse /Matrix
                dx = ma * ux + mc * uy + me
                dy = mb * ux + md * uy + mf
                if (
                    dx < domain_xmin
                    or dx > domain_xmax
                    or dy < domain_ymin
                    or dy > domain_ymax
                ):
                    pixels[base] = bg[0]
                    pixels[base + 1] = bg[1]
                    pixels[base + 2] = bg[2]
                    continue
                # Quantise to a per-domain grid for caching.
                qx = int(
                    (dx - domain_xmin)
                    / (domain_xmax - domain_xmin)
                    * (cache_grid - 1)
                )
                qy = int(
                    (dy - domain_ymin)
                    / (domain_ymax - domain_ymin)
                    * (cache_grid - 1)
                )
                key = (qx, qy)
                rgb = cache.get(key)
                if rgb is None:
                    out = evaluate(dx, dy)
                    rgb = self._function_output_to_rgb(out, cs_name) if out else bg
                    cache[key] = rgb
                pixels[base] = rgb[0]
                pixels[base + 1] = rgb[1]
                pixels[base + 2] = rgb[2]

        gradient = Image.frombytes(
            "RGB", (canvas_w, canvas_h), bytes(pixels)
        )
        if self._draw is not None:
            self._draw.flush()
        self._image.paste(gradient, (0, 0), region_mask)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    @staticmethod
    def _function_output_to_rgb(
        out: list[float] | tuple[float, ...], cs_name: str | None
    ) -> tuple[int, int, int]:
        """Coerce a function's colour-space output to an sRGB byte triple.

        Mirrors the colour-space dispatch used by
        :meth:`_evaluate_shading_rgb` but accepts a raw output list so the
        function-based shader can call it once per cache entry."""
        if not out:
            return (0, 0, 0)
        if cs_name == "DeviceGray" or len(out) == 1:
            g = float(out[0])
            return _rgb_bytes(g, g, g)
        if cs_name == "DeviceCMYK" or len(out) == 4:
            c, m, y, k = (float(v) for v in out[:4])
            return _cmyk_to_rgb_bytes(c, m, y, k)
        padded = list(out) + [0.0, 0.0, 0.0]
        return _rgb_bytes(float(padded[0]), float(padded[1]), float(padded[2]))

    # ---- Type 6 / Type 7 (Coons / tensor patch mesh) ----

    # Maximum subdivision count per patch parametric axis. Wave 1377 ports
    # upstream's adaptive ``calcLevel`` (see :func:`_calc_patch_level`);
    # this constant is the upper bound (= ``2 ** _PATCH_MAX_LEVEL`` = 16
    # cells per axis, 512 triangles per patch). The class-level attribute
    # is kept for backwards compatibility with downstream code that
    # tunes the cap (e.g. test harnesses pinning a smaller value).
    _PATCH_SUBDIVISION_N: int = 2 ** _PATCH_MAX_LEVEL

    def _paint_patch_mesh_shading(
        self,
        shading: Any,
        *,
        region_mask: Image.Image,
        control_points: int,
    ) -> bool:
        """Rasterise a Type 6 (Coons, ``control_points=12``) or Type 7
        (tensor-product, ``control_points=16``) patch-mesh shading.

        Returns ``True`` when the patch list decoded and was painted (even
        as an empty mesh — the caller should NOT fall through to the
        uniform-f(0) fallback in that case). Returns ``False`` only when
        the patch decoder itself failed (missing ``/Decode`` / non-stream
        backing) so the caller can still produce a solid-colour fallback
        that preserves the legacy behaviour.

        Approach: subdivide each patch into an ``n_v × n_u`` grid of
        ``(u, v)`` samples, where ``(n_u, n_v)`` are picked adaptively by
        :func:`_calc_patch_level` (Wave 1377 — port of upstream's
        ``CoonsPatch.calcLevel`` / ``TensorPatch.calcLevel``) and capped
        at ``_PATCH_SUBDIVISION_N`` per axis. For Coons patches the Coons
        surface formula combines the 4 boundary cubic Beziers with a
        bilinear correction; for tensor patches the standard tensor-
        product Bezier formula is used. Per-vertex colours are bilinearly
        interpolated from the 4 corner colours, then routed through the
        shading's ``/Function`` (when present) plus its colour-space.
        Each grid cell becomes 2 triangles fed to skia.
        """
        if self._image is None:
            return True
        try:
            patches = shading.parse_patches()
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: patch-mesh parse_patches failed: %s", exc
            )
            return False
        if not patches:
            return False

        canvas_w, canvas_h = self._image.size
        import skia  # noqa: PLC0415

        # Allocate the RGBA destination matching the page canvas, then we
        # use skia to draw triangles. The background colour bleeds through
        # the page-level region_mask compositing at the end.
        row_bytes = canvas_w * 4
        pixels = bytearray(canvas_w * canvas_h * 4)
        info = skia.ImageInfo.Make(
            canvas_w, canvas_h,
            skia.kRGBA_8888_ColorType,
            skia.kUnpremul_AlphaType,
        )
        surface = skia.Surface.MakeRasterDirect(info, pixels, row_bytes)
        if surface is None:  # pragma: no cover - skia always succeeds
            return False
        canvas = surface.getCanvas()

        # Apply /Background (PDF 32000-1 §8.7.4.5.1 Table 79). Painted
        # everywhere first so the patch mesh overpaints only the covered
        # cells (any gaps between patches keep the background colour).
        bg_rgba = self._patch_background_rgba(shading)
        if bg_rgba is not None:
            canvas.clear(skia.ColorSetARGB(*bg_rgba))

        # Skia matrix matches the existing _build_skia_path_alpha_mask
        # convention: PDF (a, b, c, d, e, f) → row-vector MakeAll.
        a, b, c_, d, e, f = self._full_ctm()
        canvas.setMatrix(
            skia.Matrix.MakeAll(a, c_, e, b, d, f, 0.0, 0.0, 1.0),
        )

        # Apply /BBox clip when present (in pattern user space).
        bbox_rect = self._patch_bbox_rect(shading)
        if bbox_rect is not None:
            bx0, by0, bx1, by1 = bbox_rect
            clip_path = skia.Path()
            clip_path.addRect(skia.Rect.MakeLTRB(bx0, by0, bx1, by1))
            canvas.clipPath(clip_path, doAntiAlias=False)

        anti_alias = self._patch_anti_alias(shading)
        cs_obj = None
        try:
            cs_obj = shading.get_color_space()
        except Exception:  # noqa: BLE001
            cs_obj = None
        cs_name = cs_obj.name if isinstance(cs_obj, COSName) else None

        # Optional /Function used to map each interpolated scalar colour
        # value through a 1-input function. When present the patch corner
        # colours are 1-component "parameters" that the function turns
        # into N-component colour-space values.
        fn = None
        try:
            raw_fn = shading.get_function()
        except Exception:  # noqa: BLE001
            raw_fn = None
        if raw_fn is not None:
            if not hasattr(raw_fn, "eval"):
                try:
                    from pypdfbox.pdmodel.common.function import (  # noqa: PLC0415
                        PDFunction,
                    )
                    fn = PDFunction.create(raw_fn)
                except Exception:  # noqa: BLE001
                    fn = None
            else:
                fn = raw_fn

        # Wave 1377 — pick the per-patch subdivision adaptively from the
        # patch's geometry (cf. upstream ``CoonsPatch.calcLevel`` /
        # ``TensorPatch.calcLevel``). The class-level ``_PATCH_SUBDIVISION_N``
        # acts as the maximum cap.
        cap = self._PATCH_SUBDIVISION_N
        full_ctm = self._full_ctm()
        for patch in patches:
            patch_points = [tuple(p) for p in patch.points]
            n_u, n_v = _calc_patch_level(patch_points, full_ctm)
            n_u = min(n_u, cap)
            n_v = min(n_v, cap)
            self._rasterise_single_patch(
                canvas, skia, patch, control_points, n_u, n_v, fn, cs_name,
                anti_alias=anti_alias,
            )

        # Convert RGBA buffer to a PIL "RGBA" image, then alpha-blend onto
        # the page canvas through the region mask.
        patch_img = Image.frombytes("RGBA", (canvas_w, canvas_h), bytes(pixels))
        if self._draw is not None:
            self._draw.flush()
        # Multiply the patch image's alpha by the region mask so anything
        # outside the clip / path interior stays transparent.
        r, g, b_, a = patch_img.split()
        masked_a = ImageChops.multiply(a, region_mask)
        patch_img = Image.merge("RGBA", (r, g, b_, masked_a))
        if self._image.mode == "RGBA":
            self._image.alpha_composite(patch_img)
        else:
            self._image.paste(patch_img, (0, 0), masked_a)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)
        return True

    def _rasterise_single_patch(
        self,
        canvas: Any,
        skia_mod: Any,
        patch: Any,
        control_points: int,
        n_u: int,
        n_v: int,
        fn: Any,
        cs_name: str | None,
        *,
        anti_alias: bool,
    ) -> None:
        """Subdivide one Coons / tensor patch into ``n_v * n_u`` cells,
        then push two triangles per cell to ``canvas`` with the
        interpolated corner colour. ``fn``, when provided, is a
        single-input PDFunction whose outputs are routed through the
        shading's colour space.

        ``n_u`` and ``n_v`` are independent — they come from
        :func:`_calc_patch_level` and may differ when the patch's u-axis
        boundaries are short and its v-axis boundaries are long (or vice
        versa)."""
        points: list[tuple[float, float]] = list(patch.points)
        colors: list[list[float]] = [list(c) for c in patch.colors]
        if len(points) != control_points or len(colors) != 4:
            return

        n_u = max(1, int(n_u))
        n_v = max(1, int(n_v))

        # Evaluate (x, y) at each grid sample.
        sample = (
            self._tensor_patch_eval if control_points == 16
            else self._coons_patch_eval
        )
        grid_xy: list[list[tuple[float, float]]] = [
            [(0.0, 0.0)] * (n_u + 1) for _ in range(n_v + 1)
        ]
        for j in range(n_v + 1):
            v = j / n_v
            for i in range(n_u + 1):
                u = i / n_u
                grid_xy[j][i] = sample(points, u, v)

        # Pre-compute byte RGBA for each grid sample (bilinear corner-
        # colour interpolation -> optional /Function -> colour space).
        grid_rgba: list[list[tuple[int, int, int, int]]] = [
            [(0, 0, 0, 0)] * (n_u + 1) for _ in range(n_v + 1)
        ]
        for j in range(n_v + 1):
            v = j / n_v
            for i in range(n_u + 1):
                u = i / n_u
                grid_rgba[j][i] = self._patch_color_at(
                    colors, u, v, fn, cs_name,
                )

        # Push 2 triangles per cell.
        for j in range(n_v):
            for i in range(n_u):
                p00 = grid_xy[j][i]
                p10 = grid_xy[j][i + 1]
                p01 = grid_xy[j + 1][i]
                p11 = grid_xy[j + 1][i + 1]
                c00 = grid_rgba[j][i]
                c10 = grid_rgba[j][i + 1]
                c01 = grid_rgba[j + 1][i]
                c11 = grid_rgba[j + 1][i + 1]
                # Triangle 1: p00 / p10 / p11 — colour = avg of corners
                self._fill_skia_triangle(
                    canvas, skia_mod, p00, p10, p11, c00, c10, c11,
                    anti_alias=anti_alias,
                )
                # Triangle 2: p00 / p11 / p01
                self._fill_skia_triangle(
                    canvas, skia_mod, p00, p11, p01, c00, c11, c01,
                    anti_alias=anti_alias,
                )

    @staticmethod
    def _fill_skia_triangle(
        canvas: Any,
        skia_mod: Any,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        c0: tuple[int, int, int, int],
        c1: tuple[int, int, int, int],
        c2: tuple[int, int, int, int],
        *,
        anti_alias: bool,
    ) -> None:
        """Draw a single triangle into ``canvas`` with a flat fill equal
        to the per-vertex colour average. This is the same approximation
        upstream Java's ``Type6ShadingContext`` / ``Type7ShadingContext``
        use when ``N`` is large enough that per-triangle colour variation
        is below 1 byte."""
        ar = (c0[0] + c1[0] + c2[0]) // 3
        ag = (c0[1] + c1[1] + c2[1]) // 3
        ab = (c0[2] + c1[2] + c2[2]) // 3
        aa = (c0[3] + c1[3] + c2[3]) // 3
        if aa <= 0:
            return
        path = skia_mod.Path()
        path.moveTo(p0[0], p0[1])
        path.lineTo(p1[0], p1[1])
        path.lineTo(p2[0], p2[1])
        path.close()
        paint = skia_mod.Paint(
            Color=skia_mod.ColorSetARGB(aa, ar, ag, ab),
            Style=skia_mod.Paint.kFill_Style,
            AntiAlias=anti_alias,
        )
        canvas.drawPath(path, paint)

    @staticmethod
    def _coons_patch_eval(
        pts: list[tuple[float, float]], u: float, v: float
    ) -> tuple[float, float]:
        """Evaluate a Coons-patch surface at parameter ``(u, v)``.

        The 12 control points are ordered per PDF 32000-1 §8.7.4.5.7
        Figure 39: ``p[0..3]`` = bottom boundary (left → right), ``p[3..6]``
        = right boundary (bottom → top), ``p[6..9]`` = top boundary (right
        → left), ``p[9..11] + p[0]`` = left boundary (top → bottom).

        The Coons surface is:

            S(u, v) = Sc(u, v) + Sd(u, v) - Sb(u, v)

        where Sc is the linear ruled-surface between top and bottom
        boundaries, Sd is the same between left and right, and Sb is the
        bilinear corner-blend.
        """
        # Boundary cubic Beziers.
        # Bottom: p0 -> p1 -> p2 -> p3, parameter u.
        b0 = _cubic_bezier_pt(pts[0], pts[1], pts[2], pts[3], u)
        # Right: p3 -> p4 -> p5 -> p6, parameter v.
        r0 = _cubic_bezier_pt(pts[3], pts[4], pts[5], pts[6], v)
        # Top: p9 -> p8 -> p7 -> p6, parameter u (note reverse order so
        # u=0 lands at p9 — the top-left corner).
        t0 = _cubic_bezier_pt(pts[9], pts[8], pts[7], pts[6], u)
        # Left: p0 -> p11 -> p10 -> p9, parameter v.
        l0 = _cubic_bezier_pt(pts[0], pts[11], pts[10], pts[9], v)

        # Ruled surfaces and bilinear corner blend.
        sc_x = (1.0 - v) * b0[0] + v * t0[0]
        sc_y = (1.0 - v) * b0[1] + v * t0[1]
        sd_x = (1.0 - u) * l0[0] + u * r0[0]
        sd_y = (1.0 - u) * l0[1] + u * r0[1]
        # Corner blend uses the 4 patch corners: p0, p3, p6, p9.
        p00, p10, p11, p01 = pts[0], pts[3], pts[6], pts[9]
        sb_x = (
            (1.0 - u) * (1.0 - v) * p00[0]
            + u * (1.0 - v) * p10[0]
            + u * v * p11[0]
            + (1.0 - u) * v * p01[0]
        )
        sb_y = (
            (1.0 - u) * (1.0 - v) * p00[1]
            + u * (1.0 - v) * p10[1]
            + u * v * p11[1]
            + (1.0 - u) * v * p01[1]
        )
        return (sc_x + sd_x - sb_x, sc_y + sd_y - sb_y)

    @staticmethod
    def _tensor_patch_eval(
        pts: list[tuple[float, float]], u: float, v: float
    ) -> tuple[float, float]:
        """Evaluate a tensor-product cubic Bezier patch at ``(u, v)``.

        The 16 control points are arranged in a 4×4 grid per PDF 32000-1
        §8.7.4.5.8 Figure 40:

            p[ 0] p[ 1] p[ 2] p[ 3]   <- v = 0 boundary (bottom)
            p[11] p[12] p[13] p[ 4]
            p[10] p[15] p[14] p[ 5]
            p[ 9] p[ 8] p[ 7] p[ 6]   <- v = 1 boundary (top)

        That is, the *boundary* curves go p[0..3] (bottom), p[3..6]
        (right), p[6..9] (top, reverse), p[9,10,11,0] (left, reverse),
        while p[12..15] are the four interior control points (clockwise
        from the bottom-left interior corner).
        """
        # Reshape to grid[row][col] using the order documented above.
        grid = [
            [pts[0], pts[1], pts[2], pts[3]],
            [pts[11], pts[12], pts[13], pts[4]],
            [pts[10], pts[15], pts[14], pts[5]],
            [pts[9], pts[8], pts[7], pts[6]],
        ]
        # Bernstein basis weights at u and v.
        bu = _cubic_bernstein(u)
        bv = _cubic_bernstein(v)
        x = 0.0
        y = 0.0
        for j in range(4):
            for i in range(4):
                w = bv[j] * bu[i]
                px, py = grid[j][i]
                x += w * px
                y += w * py
        return (x, y)

    @staticmethod
    def _patch_color_at(
        corner_colors: list[list[float]],
        u: float,
        v: float,
        fn: Any,
        cs_name: str | None,
    ) -> tuple[int, int, int, int]:
        """Bilinearly interpolate the 4 corner-colour vectors at (u, v),
        optionally route through ``fn``, then coerce to RGBA bytes.

        ``corner_colors`` are ordered ``[c00, c10, c11, c01]`` matching the
        4 patch corners (bottom-left, bottom-right, top-right, top-left)
        — i.e. the upstream ``Patch.color`` order ``[p0, p3, p6, p9]``.
        """
        c00, c10, c11, c01 = corner_colors
        n_comp = len(c00)
        interp: list[float] = []
        for k in range(n_comp):
            v00 = c00[k] if k < len(c00) else 0.0
            v10 = c10[k] if k < len(c10) else 0.0
            v11 = c11[k] if k < len(c11) else 0.0
            v01 = c01[k] if k < len(c01) else 0.0
            interp.append(
                (1.0 - u) * (1.0 - v) * v00
                + u * (1.0 - v) * v10
                + u * v * v11
                + (1.0 - u) * v * v01
            )
        # When /Function is present each corner colour is a 1-D parameter
        # that maps through ``fn`` to N-component colour-space values.
        if fn is not None and interp:
            try:
                out = fn.eval([float(interp[0])])
                interp = [float(v) for v in out] if out else interp
            except Exception:  # noqa: BLE001
                pass
        r, g, b = PDFRenderer._function_output_to_rgb(interp, cs_name)
        return (r, g, b, 255)

    @staticmethod
    def _patch_background_rgba(
        shading: Any,
    ) -> tuple[int, int, int, int] | None:
        """Return the ``/Background`` colour for a patch shading as
        ``(a, r, g, b)`` bytes (skia ColorSetARGB order), or ``None`` when
        absent / unparseable."""
        try:
            bg = shading.get_background()
        except Exception:  # noqa: BLE001
            return None
        if bg is None:
            return None
        try:
            flat = bg.to_float_array()
        except Exception:  # noqa: BLE001
            return None
        if not flat:
            return None
        cs_obj = None
        try:
            cs_obj = shading.get_color_space()
        except Exception:  # noqa: BLE001
            cs_obj = None
        cs_name = cs_obj.name if isinstance(cs_obj, COSName) else None
        r, g, b = PDFRenderer._function_output_to_rgb(list(flat), cs_name)
        return (255, r, g, b)

    @staticmethod
    def _patch_bbox_rect(
        shading: Any,
    ) -> tuple[float, float, float, float] | None:
        """Return the shading's ``/BBox`` as ``(xmin, ymin, xmax, ymax)``
        in pattern user space, or ``None`` when absent."""
        try:
            bbox = shading.get_b_box()
        except Exception:  # noqa: BLE001
            return None
        if bbox is None:
            return None
        try:
            flat = bbox.to_float_array()
        except Exception:  # noqa: BLE001
            return None
        if len(flat) < 4:
            return None
        x0, y0, x1, y1 = (float(v) for v in flat[:4])
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    @staticmethod
    def _patch_anti_alias(shading: Any) -> bool:
        """Read ``/AntiAlias`` — default ``False`` per PDF 32000-1 Table 79."""
        try:
            return bool(shading.get_anti_alias())
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _shading_domain_2d(shading: Any) -> tuple[float, float, float, float]:
        """Read a 4-element /Domain (PDShadingType1) — defaults to
        [0 1 0 1]. Falls back to defaults for any shape mismatch."""
        try:
            domain = shading.get_domain()
        except Exception:  # noqa: BLE001
            return (0.0, 1.0, 0.0, 1.0)
        if domain is None:
            return (0.0, 1.0, 0.0, 1.0)
        try:
            flat = domain.to_float_array()
        except Exception:  # noqa: BLE001
            return (0.0, 1.0, 0.0, 1.0)
        if len(flat) < 4:
            return (0.0, 1.0, 0.0, 1.0)
        return (float(flat[0]), float(flat[1]), float(flat[2]), float(flat[3]))

    @staticmethod
    def _shading_matrix(shading: Any) -> _Matrix:
        """Read a 6-element /Matrix from a Type 1 shading; default
        identity."""
        try:
            mtx = shading.get_matrix()
        except Exception:  # noqa: BLE001
            return _IDENTITY
        if mtx is None:
            return _IDENTITY
        try:
            flat = mtx.to_float_array()
        except Exception:  # noqa: BLE001
            return _IDENTITY
        if len(flat) < 6:
            return _IDENTITY
        return (
            float(flat[0]),
            float(flat[1]),
            float(flat[2]),
            float(flat[3]),
            float(flat[4]),
            float(flat[5]),
        )

    @staticmethod
    def _shading_domain(shading: Any) -> tuple[float, float]:
        try:
            domain = shading.get_domain()
        except Exception:  # noqa: BLE001
            return (0.0, 1.0)
        if domain is None:
            return (0.0, 1.0)
        # PDShadingType3.get_domain may return a synthesised default;
        # PDShadingType2 returns the raw COSArray or None. Both expose
        # to_float_array via COSArray.
        try:
            flat = domain.to_float_array()
        except Exception:  # noqa: BLE001
            return (0.0, 1.0)
        if len(flat) < 2:
            return (0.0, 1.0)
        return (float(flat[0]), float(flat[1]))

    @staticmethod
    def _shading_extend(shading: Any) -> tuple[bool, bool]:
        # PDShadingType3 returns a 2-tuple of bools. PDShadingType2 returns
        # a COSArray (or None). Adapt both shapes.
        try:
            ext = shading.get_extend()
        except Exception:  # noqa: BLE001
            return (False, False)
        if ext is None:
            return (False, False)
        if isinstance(ext, tuple) and len(ext) == 2:
            return (bool(ext[0]), bool(ext[1]))
        # COSArray path.
        try:
            from pypdfbox.cos import COSBoolean  # noqa: PLC0415
        except Exception:  # noqa: BLE001
            return (False, False)
        try:
            size = ext.size()
        except Exception:  # noqa: BLE001
            return (False, False)
        if size < 2:
            return (False, False)
        a = ext.get_object(0)
        b = ext.get_object(1)
        return (
            isinstance(a, COSBoolean) and a.get_value(),
            isinstance(b, COSBoolean) and b.get_value(),
        )

    @staticmethod
    def _invert_matrix(m: _Matrix) -> _Matrix | None:
        a, b, c, d, e, f = m
        det = a * d - b * c
        if abs(det) < 1e-12:
            return None
        inv_det = 1.0 / det
        # Inverse of the 2x2 block.
        ia = d * inv_det
        ib = -b * inv_det
        ic = -c * inv_det
        id_ = a * inv_det
        # Translate back: -CTM_inv * (e, f)
        ie = -(ia * e + ic * f)
        if_ = -(ib * e + id_ * f)
        return (ia, ib, ic, id_, ie, if_)

    # ---- clip path ----

    def _apply_pending_clip(self, *, default_even_odd: bool) -> None:
        """If a ``W`` / ``W*`` was issued, intersect its mask with the
        current clip and stash the result on the GS. ``default_even_odd``
        is unused here (the W variant is recorded directly) but kept as a
        named arg so callers document intent.

        Wave 1373: both ``W`` and ``W*`` now build the clip mask through
        :meth:`_build_skia_path_alpha_mask` so the clip silhouette keeps
        sub-pixel anti-aliasing on the outer edge (the legacy XOR /
        union-of-polygons path produced a binary mask).
        """
        del default_even_odd  # callers pass it for documentation only
        clip_op = self._pending_clip
        if clip_op is None:
            return
        self._pending_clip = None
        if not self._subpaths or self._image is None:
            return

        width_px, height_px = self._image.size
        new_clip = self._build_skia_path_alpha_mask(even_odd=(clip_op == "W*"))
        if new_clip is None:
            new_clip = Image.new("L", (width_px, height_px), 0)

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
            # PDF spec §8.9.5.4: an image XObject with ``/ImageMask true``
            # is a stencil mask — the sample data is a 1-bit alpha matte
            # and the image is painted as the current non-stroking colour
            # wherever the matte is opaque. Upstream PDFBox handles this
            # in ``PageDrawer.drawImage`` (line 1078-1244); without the
            # branch our renderer would silently drop stencils.
            try:
                is_stencil = bool(xobject.is_stencil())
            except Exception:  # noqa: BLE001
                is_stencil = False
            if is_stencil:
                try:
                    self._paint_stencil_mask(xobject)
                except Exception as exc:  # noqa: BLE001
                    _log.debug("rendering: cannot paint stencil mask: %s", exc)
                return
            try:
                pil_image = self._decode_image_xobject(xobject)
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: cannot decode image: %s", exc)
                return
            if pil_image is None:
                return
            # PDF spec §11.6.5: an image XObject with /SMask carries a
            # separate grayscale alpha mask. Decode it and convert the
            # paste image to RGBA so the paste path can honour the alpha.
            try:
                smask = xobject.get_soft_mask()
            except Exception:  # noqa: BLE001
                smask = None
            if smask is not None:
                pil_image = self._apply_smask(pil_image, smask)
            self._paste_image(pil_image)
            return

        if isinstance(xobject, PDFormXObject):
            # PDF spec §11.4.7: a Form XObject with a /Group dict whose
            # /S is /Transparency is rendered onto its own backdrop and
            # alpha-composited onto the parent. Detect via the helper if
            # present (upstream PDFormXObject in newer versions exposes
            # is_transparency_group()), else fall back to inspecting
            # /Group/S directly.
            #
            # Recursion cap (wave 1385): upstream's ``DrawObject``
            # processor caps Form-XObject ``Do`` recursion at 50 levels
            # (DrawObject.java:84-89) to prevent a maliciously-crafted
            # PDF that nests ``/XObject /Fm0 = <stream with Do /Fm0>``
            # from blowing the Python stack. We mirror that exact limit.
            if self._form_x_object_depth >= self._form_x_object_depth_limit:
                _log.warning(
                    "rendering: Form XObject recursion depth %d exceeds "
                    "limit %d; skipping nested Do %s",
                    self._form_x_object_depth,
                    self._form_x_object_depth_limit,
                    name.name,
                )
                return
            self._form_x_object_depth += 1
            try:
                if self._is_transparency_group(xobject):
                    self._render_transparency_group(xobject)
                else:
                    self._render_form_xobject(xobject)
            finally:
                self._form_x_object_depth -= 1
            return

    def _annotation_should_skip(self, annotation: Any) -> bool:
        """Mirror upstream ``PageDrawer.shouldSkipAnnotation`` —
        consult the annotation's visibility flags against the active
        render destination so widgets that opt out of the current
        target are dropped before their appearance is resolved.

        Skip rules (per PDF 32000-1 §12.5.3):
        - ``/F`` bit 2 (Hidden) — never display the annotation.
        - ``/F`` bit 6 (NoView) — skip for View / Export destinations.
        - ``/F`` bit 3 (Print=false) — skip when destination is Print.
        - Unknown subtypes with ``/F`` bit 1 (Invisible) set.
        """
        destination = getattr(self, "_active_destination", None)
        if destination is None:
            destination = self._default_destination
        if isinstance(destination, RenderDestination):
            destination = destination.value
        try:
            if annotation.is_hidden():
                return True
            if destination == "Print" and not annotation.is_printed():
                return True
            if destination in ("View", "Export") and annotation.is_no_view():
                return True
        except Exception:  # noqa: BLE001 — defensive: malformed flags
            return False
        # Unknown subtypes with the Invisible bit set are dropped per spec.
        if annotation.__class__.__name__ == "PDAnnotationUnknown":
            try:
                if annotation.is_invisible():
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def _render_annotation(self, annotation: Any) -> None:
        """Render a single annotation's Normal Appearance.

        Mirrors upstream ``PageDrawer.showAnnotation`` →
        ``PDFStreamEngine.processAnnotation`` (PageDrawer.java line 1550
        and PDFStreamEngine.java line 321):

        1. Honour ``shouldSkipAnnotation`` so Hidden / NoView / Print
           flags drop the annotation before any work happens.
        2. Resolve the Normal Appearance stream
           (``annotation.get_normal_appearance_stream()``); when absent,
           try ``construct_appearances`` and re-resolve. Annotations
           with no appearance (e.g. plain Link annotations) are
           silently skipped — matches upstream's no-op path.
        3. Compute the transform that maps the appearance's ``/BBox``
           (after its ``/Matrix``) onto the annotation's ``/Rect``.
        4. Push a graphics state, concat the transform onto the CTM,
           clip to ``/BBox``, switch resources to the appearance's
           ``/Resources``, walk the appearance content stream.
        5. Pop graphics state and restore resources.
        """
        if self._annotation_should_skip(annotation):
            return
        # Resolve the normal appearance stream. If absent, give the
        # annotation one chance to synthesise one (upstream calls
        # ``annotation.constructAppearances(renderer.document)``).
        try:
            appearance = annotation.get_normal_appearance_stream()
        except Exception as exc:  # noqa: BLE001
            _log.debug("annotation: cannot resolve appearance: %s", exc)
            return
        if appearance is None:
            construct = getattr(annotation, "construct_appearances", None)
            if callable(construct):
                try:
                    try:
                        construct(self._document)
                    except TypeError:
                        construct()
                    appearance = annotation.get_normal_appearance_stream()
                except Exception as exc:  # noqa: BLE001
                    _log.debug(
                        "annotation: construct_appearances failed: %s", exc
                    )
                    appearance = None
        if appearance is None:
            return
        # Annotation rectangle in user space.
        try:
            rect = annotation.get_rectangle()
        except Exception:  # noqa: BLE001
            return
        if rect is None:
            return
        # Appearance bounding box + matrix (defaults to identity).
        try:
            bbox = appearance.get_bbox()
        except Exception:  # noqa: BLE001
            return
        if bbox is None:
            return
        # PDFBOX-4783: zero-sized rectangles are not valid — skip silently
        # so a malformed annotation can't crash the page render.
        if rect.get_width() <= 0 or rect.get_height() <= 0:
            return
        if bbox.get_width() <= 0 or bbox.get_height() <= 0:
            return
        try:
            matrix = appearance.get_matrix()
        except Exception:  # noqa: BLE001
            matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        if matrix is None or len(matrix) < 6:
            matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        m_appear: _Matrix = (
            float(matrix[0]),
            float(matrix[1]),
            float(matrix[2]),
            float(matrix[3]),
            float(matrix[4]),
            float(matrix[5]),
        )
        # Compute the transformed bounding box (the axis-aligned bounds
        # of the four bbox corners after applying ``m_appear``). Mirrors
        # upstream's ``bbox.transform(matrix).getBounds2D()``.
        x1 = bbox.get_lower_left_x()
        y1 = bbox.get_lower_left_y()
        x2 = bbox.get_upper_right_x()
        y2 = bbox.get_upper_right_y()
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        transformed_xs: list[float] = []
        transformed_ys: list[float] = []
        for cx, cy in corners:
            tx = m_appear[0] * cx + m_appear[2] * cy + m_appear[4]
            ty = m_appear[1] * cx + m_appear[3] * cy + m_appear[5]
            transformed_xs.append(tx)
            transformed_ys.append(ty)
        tb_x = min(transformed_xs)
        tb_y = min(transformed_ys)
        tb_w = max(transformed_xs) - tb_x
        tb_h = max(transformed_ys) - tb_y
        if tb_w <= 0 or tb_h <= 0:
            return
        # Build matrix ``a`` that scales/translates the transformed
        # appearance box onto the annotation rectangle (upstream
        # PDFStreamEngine.processAnnotation lines 343-346):
        #   a = T(rect.llx, rect.lly) * S(rect.w / tb.w, rect.h / tb.h)
        #       * T(-tb.x, -tb.y)
        sx = rect.get_width() / tb_w
        sy = rect.get_height() / tb_h
        a_matrix: _Matrix = (
            sx,
            0.0,
            0.0,
            sy,
            rect.get_lower_left_x() - tb_x * sx,
            rect.get_lower_left_y() - tb_y * sy,
        )
        # Concatenate ``a`` with the appearance's own ``/Matrix`` — see
        # PDFBox-3083: the combined transform is ``aa = a * matrix``
        # (upstream's ``Matrix.concatenate(a, matrix)``). Our ``_matmul``
        # convention applies the right argument first then the left, so
        # ``_matmul(a, m_appear)`` yields the correct composition.
        aa = _matmul(a_matrix, m_appear)
        # Save GS + resources, push the transform, clip to bbox, then
        # walk the appearance stream's bytes.
        self._push_gs()
        prev_resources = self._resources
        try:
            self._gs.ctm = _matmul(aa, self._gs.ctm)
            # Clip to the appearance's /BBox in pre-transform space.
            self._subpaths = []
            self._current_subpath = None
            self._start_subpath(x1, y1)
            assert self._current_subpath is not None
            self._current_subpath.append(("L", x2, y1))
            self._current_subpath.append(("L", x2, y2))
            self._current_subpath.append(("L", x1, y2))
            self._current_subpath.append(("Z",))
            self._pending_clip = "W"
            self._apply_pending_clip(default_even_odd=False)
            self._reset_path()
            # Switch resources to the appearance's /Resources if any.
            try:
                form_res = appearance.get_resources()
            except Exception:  # noqa: BLE001
                form_res = None
            if form_res is not None:
                self._resources = form_res
            # Walk the appearance content stream.
            try:
                cos_stream = appearance.get_cos_object()
            except Exception:  # noqa: BLE001
                cos_stream = None
            if isinstance(cos_stream, COSStream):
                try:
                    data = cos_stream.to_byte_array()
                except Exception as exc:  # noqa: BLE001
                    _log.debug(
                        "annotation: cannot decode appearance stream: %s", exc
                    )
                    data = b""
                if data:
                    self._process_form_bytes(data)
        finally:
            self._resources = prev_resources
            self._pop_gs()

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

    @staticmethod
    def _is_transparency_group(form: Any) -> bool:
        """Return True if ``form`` carries a ``/Group`` dict with
        ``/S /Transparency``. Honours an upstream-style
        :meth:`is_transparency_group` helper when present so a future
        ported variant of ``PDFormXObject`` plugs in seamlessly."""
        helper = getattr(form, "is_transparency_group", None)
        if callable(helper):
            try:
                return bool(helper())
            except Exception:  # noqa: BLE001 — defensive
                pass
        try:
            group = form.get_group()
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(group, COSDictionary):
            return False
        s = group.get_dictionary_object(COSName.get_pdf_name("S"))
        return isinstance(s, COSName) and s.name == "Transparency"

    @staticmethod
    def _blend(
        source: Image.Image, backdrop: Image.Image, mode: Any
    ) -> Image.Image:
        """Composite ``source`` over ``backdrop`` honouring a PDF blend mode.

        Implements the separable blend functions of PDF 32000-1 §11.3.5.1
        (``Normal`` / ``Multiply`` / ``Screen`` / ``Overlay`` / ``Darken`` /
        ``Lighten`` / ``ColorDodge`` / ``ColorBurn`` / ``HardLight`` /
        ``SoftLight`` / ``Difference`` / ``Exclusion``) plus the four
        non-separable HSL blend functions of §11.3.5.3 (``Hue`` /
        ``Saturation`` / ``Color`` / ``Luminosity``) via the spec helpers
        ``Lum`` / ``Sat`` / ``SetLum`` / ``SetSat`` / ``ClipColor``.

        Both inputs are converted to RGBA and the result is RGBA. The
        formula is applied per channel on the *colour* components only;
        the result alpha is the standard Porter-Duff "source over" alpha
        ``a_s + a_b * (1 - a_s)`` so transparent source pixels never
        affect the backdrop. Mirrors upstream PDFBox's
        ``BlendComposite`` per-channel formulas in
        ``org.apache.pdfbox.rendering`` (PageDrawer dispatches to a
        Java2D ``Composite`` whose ``compose`` method evaluates the same
        equations).
        """
        from pypdfbox.pdmodel.graphics.blend_mode import (  # noqa: PLC0415
            BlendMode,
        )

        if source.mode != "RGBA":
            source = source.convert("RGBA")
        if backdrop.mode != "RGBA":
            backdrop = backdrop.convert("RGBA")
        if source.size != backdrop.size:
            source = source.resize(backdrop.size, Image.Resampling.BILINEAR)

        if mode is None or mode is BlendMode.NORMAL:
            out = backdrop.copy()
            out.alpha_composite(source)
            return out

        sr, sg, sb, sa = source.split()
        br, bg, bb, ba = backdrop.split()
        name = getattr(mode, "name", None)

        # Non-separable HSL family (§11.3.5.3) — dispatch to dedicated
        # per-pixel helpers that operate on the full RGB triple at once
        # (separable per-channel formulas don't apply to these modes).
        if not getattr(mode, "is_separable", lambda: True)():
            if name == "Hue":
                cr, cg, cb = PDFRenderer._blend_hue(br, bg, bb, sr, sg, sb)
            elif name == "Saturation":
                cr, cg, cb = PDFRenderer._blend_saturation(
                    br, bg, bb, sr, sg, sb
                )
            elif name == "Color":
                cr, cg, cb = PDFRenderer._blend_color(
                    br, bg, bb, sr, sg, sb
                )
            elif name == "Luminosity":
                cr, cg, cb = PDFRenderer._blend_luminosity(
                    br, bg, bb, sr, sg, sb
                )
            else:
                _log.debug(
                    "rendering: unknown non-separable blend mode %r → Normal",
                    name,
                )
                out = backdrop.copy()
                out.alpha_composite(source)
                return out
            inv_sa = ImageChops.invert(sa)
            ba_keep = ImageChops.multiply(ba, inv_sa)
            out_a = ImageChops.add(sa, ba_keep)
            cr = Image.composite(cr, br, sa)
            cg = Image.composite(cg, bg, sa)
            cb = Image.composite(cb, bb, sa)
            return Image.merge("RGBA", (cr, cg, cb, out_a))

        # ImageChops paths are vectorised in C — prefer them whenever the
        # blend formula maps cleanly to a single primitive.
        if name == "Multiply":
            cr = ImageChops.multiply(br, sr)
            cg = ImageChops.multiply(bg, sg)
            cb = ImageChops.multiply(bb, sb)
        elif name == "Screen":
            cr = ImageChops.screen(br, sr)
            cg = ImageChops.screen(bg, sg)
            cb = ImageChops.screen(bb, sb)
        elif name == "Darken":
            cr = ImageChops.darker(br, sr)
            cg = ImageChops.darker(bg, sg)
            cb = ImageChops.darker(bb, sb)
        elif name == "Lighten":
            cr = ImageChops.lighter(br, sr)
            cg = ImageChops.lighter(bg, sg)
            cb = ImageChops.lighter(bb, sb)
        elif name == "Difference":
            cr = ImageChops.difference(br, sr)
            cg = ImageChops.difference(bg, sg)
            cb = ImageChops.difference(bb, sb)
        else:
            # Per-pixel fallback for the remaining separable modes. Pure
            # Python loops are slow but lite-renderer canvases are small
            # at the rendering DPI; correctness over throughput here.
            cr = PDFRenderer._blend_channel(br, sr, name)
            cg = PDFRenderer._blend_channel(bg, sg, name)
            cb = PDFRenderer._blend_channel(bb, sb, name)

        # Porter-Duff alpha-over for the resulting alpha channel:
        #   a_out = a_s + a_b * (1 - a_s)
        inv_sa = ImageChops.invert(sa)
        ba_keep = ImageChops.multiply(ba, inv_sa)
        out_a = ImageChops.add(sa, ba_keep)

        # Where source is fully transparent the backdrop colour wins; where
        # source is fully opaque the blend result wins. For partial alpha
        # interpolate the per-channel blend back toward the backdrop using
        # ``a_s`` as the weight (the simplified compositing equation when
        # no shape coverage is involved):
        #   c_out = (1 - a_s) * c_b + a_s * blend(c_b, c_s)
        cr = Image.composite(cr, br, sa)
        cg = Image.composite(cg, bg, sa)
        cb = Image.composite(cb, bb, sa)

        return Image.merge("RGBA", (cr, cg, cb, out_a))

    @staticmethod
    def _blend_channel(
        backdrop: Image.Image, source: Image.Image, mode_name: str | None
    ) -> Image.Image:
        """Per-pixel blend for separable modes that don't map to a single
        :mod:`PIL.ImageChops` primitive.

        Inputs are 8-bit ``L`` images of identical size; output is an
        8-bit ``L`` image. ``mode_name`` is the PDF blend-mode name
        (``Overlay`` / ``ColorDodge`` / ``ColorBurn`` / ``HardLight`` /
        ``SoftLight``); unknown names leave the backdrop unchanged."""
        if mode_name is None:
            return backdrop
        bd = cast(Any, backdrop.load())
        sd = cast(Any, source.load())
        w, h = backdrop.size
        out = Image.new("L", (w, h))
        od = cast(Any, out.load())
        for y in range(h):
            for x in range(w):
                b = bd[x, y] / 255.0
                s = sd[x, y] / 255.0
                v = PDFRenderer._blend_scalar(b, s, mode_name)
                if v < 0.0:
                    v = 0.0
                elif v > 1.0:
                    v = 1.0
                od[x, y] = int(round(v * 255.0))
        return out

    @staticmethod
    def _blend_scalar(b: float, s: float, mode_name: str) -> float:
        """Single-channel blend formula in [0, 1] space (PDF 32000-1
        §11.3.5.1 Table 136). ``b`` = backdrop, ``s`` = source."""
        if mode_name == "Overlay":
            # Overlay(b, s) = HardLight(s, b)
            return PDFRenderer._blend_scalar(s, b, "HardLight")
        if mode_name == "HardLight":
            if s <= 0.5:
                return 2.0 * b * s
            return 1.0 - 2.0 * (1.0 - b) * (1.0 - s)
        if mode_name == "ColorDodge":
            # PDF 2.0 §11.3.5.1 ColorDodge — matches upstream PDFBox 3.0.x
            # ``BlendMode.java`` line 75-86. Aligned in wave 1363.
            if b == 0.0:
                return 0.0
            if b >= 1.0 - s:
                return 1.0
            return b / (1.0 - s)
        if mode_name == "ColorBurn":
            # PDF 2.0 §11.3.5.1 ColorBurn — matches upstream PDFBox 3.0.x
            # ``BlendMode.java`` line 88-99. Aligned in wave 1363.
            if b == 1.0:
                return 1.0
            if 1.0 - b >= s:
                return 0.0
            return 1.0 - (1.0 - b) / s
        if mode_name == "SoftLight":
            # PDF spec form (matches Adobe's): two-piece quadratic.
            if s <= 0.5:
                return b - (1.0 - 2.0 * s) * b * (1.0 - b)
            d = ((16.0 * b - 12.0) * b + 4.0) * b if b <= 0.25 else b ** 0.5
            return b + (2.0 * s - 1.0) * (d - b)
        if mode_name == "Exclusion":
            return b + s - 2.0 * b * s
        if mode_name == "Multiply":
            return b * s
        if mode_name == "Screen":
            return b + s - b * s
        if mode_name == "Darken":
            return min(b, s)
        if mode_name == "Lighten":
            return max(b, s)
        if mode_name == "Difference":
            return abs(b - s)
        # Fallback — leave backdrop unchanged for unknown / non-separable.
        return b

    # ------------------------------------------------------------------
    # Non-separable HSL helpers (PDF 32000-1 §11.3.5.3)
    # ------------------------------------------------------------------
    #
    # The four HSL blend modes treat each pixel's RGB triple as a single
    # colour and compose Hue / Saturation / Luminosity components from the
    # backdrop and the source. The spec defines a small kit of pure
    # functions on (R, G, B) tuples:
    #
    #     Lum(C)        = 0.30*R + 0.59*G + 0.11*B
    #     Sat(C)        = max(R, G, B) - min(R, G, B)
    #     ClipColor(C)  : push out-of-gamut RGB values back into [0, 1]
    #                     while preserving Lum.
    #     SetLum(C, l)  : translate C so its luminance equals l, then clip.
    #     SetSat(C, s)  : remap C's component range to [0, s] preserving
    #                     the relative ordering of R, G, B.
    #
    # Each blend mode is a one-line composition of those primitives:
    #
    #     Hue        = SetLum(SetSat(Cs, Sat(Cb)),  Lum(Cb))
    #     Saturation = SetLum(SetSat(Cb, Sat(Cs)),  Lum(Cb))
    #     Color      = SetLum(Cs,                   Lum(Cb))
    #     Luminosity = SetLum(Cb,                   Lum(Cs))
    #
    # Implementation walks the canvas pixel-by-pixel. Lite-renderer
    # canvases are small enough at typical DPIs that the per-pixel cost
    # is dwarfed by the wider rasterisation pipeline; we prioritise
    # spec-faithful arithmetic in [0, 1] space over throughput.

    @staticmethod
    def _hsl_lum(r: float, g: float, b: float) -> float:
        return 0.30 * r + 0.59 * g + 0.11 * b

    @staticmethod
    def _hsl_sat(r: float, g: float, b: float) -> float:
        return max(r, g, b) - min(r, g, b)

    @staticmethod
    def _hsl_clip_color(
        r: float, g: float, b: float
    ) -> tuple[float, float, float]:
        """Push (R, G, B) back into [0, 1] while preserving luminance.

        Mirrors the ``ClipColor`` pseudocode in §11.3.5.3."""
        lum = PDFRenderer._hsl_lum(r, g, b)
        cmin = min(r, g, b)
        cmax = max(r, g, b)
        if cmin < 0.0:
            denom = lum - cmin
            if denom != 0.0:
                r = lum + (r - lum) * lum / denom
                g = lum + (g - lum) * lum / denom
                b = lum + (b - lum) * lum / denom
            else:
                r = g = b = lum
        if cmax > 1.0:
            denom = cmax - lum
            if denom != 0.0:
                r = lum + (r - lum) * (1.0 - lum) / denom
                g = lum + (g - lum) * (1.0 - lum) / denom
                b = lum + (b - lum) * (1.0 - lum) / denom
            else:
                r = g = b = lum
        return r, g, b

    @staticmethod
    def _hsl_set_lum(
        r: float, g: float, b: float, lum: float
    ) -> tuple[float, float, float]:
        """Return colour with luminance ``lum`` (clipped to [0, 1])."""
        d = lum - PDFRenderer._hsl_lum(r, g, b)
        return PDFRenderer._hsl_clip_color(r + d, g + d, b + d)

    @staticmethod
    def _hsl_set_sat(
        r: float, g: float, b: float, sat: float
    ) -> tuple[float, float, float]:
        """Return colour with saturation ``sat`` preserving the relative
        ordering of components — the §11.3.5.3 ``SetSat`` algorithm.

        The spec sorts the components into (Cmin, Cmid, Cmax). The mid
        component is rescaled into [0, sat] using its position between
        Cmin and Cmax, the max becomes ``sat``, and the min becomes 0.
        """
        # Identify min / mid / max indices. With three components a small
        # branching table is clearer (and faster) than an explicit sort.
        components = [r, g, b]
        cmax = max(components)
        cmin = min(components)
        if cmax == cmin:
            return 0.0, 0.0, 0.0
        # Locate indices for max and min; the remaining one is mid.
        max_idx = components.index(cmax)
        # ``index`` returns the first match; if max == mid that's still
        # fine because the mid handling below scales using cmax-cmin and
        # any component equal to cmax maps to ``sat`` anyway.
        min_idx = next(
            (i for i in range(3) if i != max_idx and components[i] == cmin),
            None,
        )
        if min_idx is None:
            # All three equal — already handled above, but guard anyway.
            return 0.0, 0.0, 0.0
        mid_idx = 3 - max_idx - min_idx
        out = [0.0, 0.0, 0.0]
        out[mid_idx] = (components[mid_idx] - cmin) * sat / (cmax - cmin)
        out[max_idx] = sat
        out[min_idx] = 0.0
        return out[0], out[1], out[2]

    @staticmethod
    def _hsl_blend_pixels(
        backdrop: Image.Image,
        source: Image.Image,
        compose: Callable[[_RGBFloat, _RGBFloat], _RGBFloat],
    ) -> tuple[Image.Image, Image.Image, Image.Image]:
        """Apply ``compose(cb, cs)`` per pixel and return three ``L``
        channel images. ``backdrop`` and ``source`` are RGBA inputs of
        identical size (callers ensure this); ``compose`` accepts and
        returns RGB triples in [0, 1] space."""
        w, h = backdrop.size
        # Drop the alpha channel — alpha is reapplied by the caller via
        # ``Image.composite(...)`` against the source alpha.
        bd = cast(Any, backdrop.convert("RGB").load())
        sd = cast(Any, source.convert("RGB").load())
        out_r = Image.new("L", (w, h))
        out_g = Image.new("L", (w, h))
        out_b = Image.new("L", (w, h))
        rd = cast(Any, out_r.load())
        gd = cast(Any, out_g.load())
        bd_out = cast(Any, out_b.load())
        for y in range(h):
            for x in range(w):
                br, bg, bb = bd[x, y]
                sr, sg, sb = sd[x, y]
                cb = (br / 255.0, bg / 255.0, bb / 255.0)
                cs = (sr / 255.0, sg / 255.0, sb / 255.0)
                cr, cgc, cbc = compose(cb, cs)
                cr = 0.0 if cr < 0.0 else 1.0 if cr > 1.0 else cr
                cgc = 0.0 if cgc < 0.0 else 1.0 if cgc > 1.0 else cgc
                cbc = 0.0 if cbc < 0.0 else 1.0 if cbc > 1.0 else cbc
                rd[x, y] = int(round(cr * 255.0))
                gd[x, y] = int(round(cgc * 255.0))
                bd_out[x, y] = int(round(cbc * 255.0))
        return out_r, out_g, out_b

    @staticmethod
    def _blend_hue(
        br: Image.Image,
        bg: Image.Image,
        bb: Image.Image,
        sr: Image.Image,
        sg: Image.Image,
        sb: Image.Image,
    ) -> tuple[Image.Image, Image.Image, Image.Image]:
        """Hue: keep backdrop's saturation and luminance, take source's hue.

        Spec formula: ``B(Cb, Cs) = SetLum(SetSat(Cs, Sat(Cb)), Lum(Cb))``.
        """
        backdrop = Image.merge("RGB", (br, bg, bb))
        source = Image.merge("RGB", (sr, sg, sb))

        def _compose(cb: _RGBFloat, cs: _RGBFloat) -> _RGBFloat:
            r, g, b = PDFRenderer._hsl_set_sat(
                cs[0], cs[1], cs[2], PDFRenderer._hsl_sat(*cb)
            )
            return PDFRenderer._hsl_set_lum(r, g, b, PDFRenderer._hsl_lum(*cb))

        return PDFRenderer._hsl_blend_pixels(backdrop, source, _compose)

    @staticmethod
    def _blend_saturation(
        br: Image.Image,
        bg: Image.Image,
        bb: Image.Image,
        sr: Image.Image,
        sg: Image.Image,
        sb: Image.Image,
    ) -> tuple[Image.Image, Image.Image, Image.Image]:
        """Saturation: keep backdrop's hue and luminance, take source's saturation.

        Spec formula: ``B(Cb, Cs) = SetLum(SetSat(Cb, Sat(Cs)), Lum(Cb))``.
        """
        backdrop = Image.merge("RGB", (br, bg, bb))
        source = Image.merge("RGB", (sr, sg, sb))

        def _compose(cb: _RGBFloat, cs: _RGBFloat) -> _RGBFloat:
            r, g, b = PDFRenderer._hsl_set_sat(
                cb[0], cb[1], cb[2], PDFRenderer._hsl_sat(*cs)
            )
            return PDFRenderer._hsl_set_lum(r, g, b, PDFRenderer._hsl_lum(*cb))

        return PDFRenderer._hsl_blend_pixels(backdrop, source, _compose)

    @staticmethod
    def _blend_color(
        br: Image.Image,
        bg: Image.Image,
        bb: Image.Image,
        sr: Image.Image,
        sg: Image.Image,
        sb: Image.Image,
    ) -> tuple[Image.Image, Image.Image, Image.Image]:
        """Color: keep backdrop's luminance, take source's hue+saturation.

        Spec formula: ``B(Cb, Cs) = SetLum(Cs, Lum(Cb))``.
        """
        backdrop = Image.merge("RGB", (br, bg, bb))
        source = Image.merge("RGB", (sr, sg, sb))

        def _compose(cb: _RGBFloat, cs: _RGBFloat) -> _RGBFloat:
            return PDFRenderer._hsl_set_lum(
                cs[0], cs[1], cs[2], PDFRenderer._hsl_lum(*cb)
            )

        return PDFRenderer._hsl_blend_pixels(backdrop, source, _compose)

    @staticmethod
    def _blend_luminosity(
        br: Image.Image,
        bg: Image.Image,
        bb: Image.Image,
        sr: Image.Image,
        sg: Image.Image,
        sb: Image.Image,
    ) -> tuple[Image.Image, Image.Image, Image.Image]:
        """Luminosity: keep backdrop's hue+saturation, take source's luminance.

        Spec formula: ``B(Cb, Cs) = SetLum(Cb, Lum(Cs))``.
        """
        backdrop = Image.merge("RGB", (br, bg, bb))
        source = Image.merge("RGB", (sr, sg, sb))

        def _compose(cb: _RGBFloat, cs: _RGBFloat) -> _RGBFloat:
            return PDFRenderer._hsl_set_lum(
                cb[0], cb[1], cb[2], PDFRenderer._hsl_lum(*cs)
            )

        return PDFRenderer._hsl_blend_pixels(backdrop, source, _compose)

    def _apply_smask(self, image: Image.Image, smask: Any) -> Image.Image:
        """Return ``image`` with the SMask Image XObject applied as alpha.

        The mask is decoded as 8-bit grayscale via the existing
        :meth:`PDImageXObject.to_pil_image` helper and resized to match
        the cover image. Any failure logs at debug level and returns the
        original image unchanged — alpha-mask compositing is best-effort
        in the lite renderer (PDF spec §11.6.5)."""
        try:
            mask_image = smask.to_pil_image()
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: cannot decode SMask: %s", exc)
            return image
        if mask_image is None:
            return image
        # Spec mandates the SMask be evaluated as luminance (single-channel
        # grayscale). PIL's "L" conversion handles RGB → luminance for us.
        if mask_image.mode != "L":
            mask_image = mask_image.convert("L")
        if mask_image.size != image.size:
            mask_image = mask_image.resize(image.size, Image.Resampling.BILINEAR)
        rgba = image.convert("RGBA")
        rgba.putalpha(mask_image)
        return rgba

    def _render_soft_mask_alpha(
        self, soft_mask: Any, size: tuple[int, int]
    ) -> Image.Image | None:
        """Render an ExtGState soft-mask dictionary into an ``"L"`` alpha
        plane sized to ``size`` (matching the active group canvas).

        Per PDF spec §11.6.5.2-3:

        - ``/G`` (transparency-group XObject) is rendered onto a fresh
          RGBA canvas. For ``/Luminosity`` the canvas is pre-filled with
          the backdrop colour ``/BC`` (default 0 in the group's colour
          space) so areas the group leaves untouched contribute the
          backdrop's luminance to the mask. For ``/Alpha`` the canvas
          starts fully transparent so untouched areas contribute zero.
        - The mask values are taken from either the alpha channel
          (``/Alpha``) or the luminance of RGB (``/Luminosity``).
        - The optional ``/TR`` transfer function (default ``/Identity``)
          remaps mask values before they become alpha multipliers.

        Returns ``None`` when the soft mask is malformed or unrenderable."""
        from pypdfbox.pdmodel.graphics.state.pd_soft_mask import (  # noqa: PLC0415
            PDSoftMask,
        )

        if not isinstance(soft_mask, PDSoftMask):
            return None
        group_form = soft_mask.get_group()
        if group_form is None:
            _log.debug("rendering: soft mask /G missing or malformed")
            return None

        # Initial mask canvas. /Luminosity uses the backdrop colour; /Alpha
        # starts with zero alpha (a fully-masked-out canvas).
        is_luminosity = soft_mask.is_luminosity()
        if is_luminosity:
            bc = self._soft_mask_backdrop_rgb(soft_mask)
            mask_canvas = Image.new("RGBA", size, (bc[0], bc[1], bc[2], 255))
        else:
            mask_canvas = Image.new("RGBA", size, (0, 0, 0, 0))

        # Redirect rendering onto the mask canvas with a fresh GS stack so
        # the active soft mask doesn't recursively trigger another mask
        # render. The mask group's own /G ExtGStates may set their own
        # blend modes; we contain those by snapshotting the renderer's
        # mutable state.
        prev_image = self._image
        prev_draw = self._draw
        prev_gs_stack = self._gs_stack
        prev_subpaths = self._subpaths
        prev_subpath = self._current_subpath
        prev_pending_clip = self._pending_clip
        prev_resources = self._resources
        prev_knockout_active = self._knockout_active
        prev_knockout_snapshot = self._knockout_snapshot
        prev_knockout_form_depth = self._knockout_form_depth
        # Avoid recursive soft-mask rendering during the mask render itself.
        fresh_gs = _GState()
        fresh_gs.ctm = self._gs.ctm
        fresh_gs.soft_mask = None
        self._image = mask_canvas
        self._draw = aggdraw.Draw(mask_canvas)
        self._draw.setantialias(True)
        self._gs_stack = [fresh_gs]
        self._subpaths = []
        self._current_subpath = None
        self._pending_clip = None
        self._knockout_active = False
        self._knockout_snapshot = None
        self._knockout_form_depth = 0
        # Suppress per-paint SMask handling inside the soft-mask group's
        # own recursive render — its content stream paints land raw onto
        # ``mask_canvas`` and we extract the alpha/luminance channel after.
        self._transparency_group_depth += 1
        try:
            self._render_form_xobject(group_form)
            current = self._draw
            if current is not None:
                current.flush()
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: soft-mask group render failed: %s", exc)
            return None
        finally:
            self._transparency_group_depth -= 1
            self._image = prev_image
            self._draw = prev_draw
            self._gs_stack = prev_gs_stack
            self._subpaths = prev_subpaths
            self._current_subpath = prev_subpath
            self._pending_clip = prev_pending_clip
            self._resources = prev_resources
            self._knockout_active = prev_knockout_active
            self._knockout_snapshot = prev_knockout_snapshot
            self._knockout_form_depth = prev_knockout_form_depth

        # Extract the mask channel.
        # Luminance of RGB → 8-bit grayscale.
        alpha_plane = mask_canvas.convert("L") if is_luminosity else mask_canvas.split()[3]

        # Apply /TR transfer function if present (and not /Identity).
        tr = soft_mask.get_transfer_function()
        if tr is not None:
            tr_lookup = self._build_transfer_lookup(tr)
            if tr_lookup is not None:
                alpha_plane = alpha_plane.point(tr_lookup)

        return alpha_plane

    def _soft_mask_backdrop_rgb(self, soft_mask: Any) -> tuple[int, int, int]:
        """Resolve a soft-mask ``/BC`` array to an sRGB byte triple.

        Defaults to black (the "no-colour" default for /Luminosity per
        PDF spec §11.6.5.3) when ``/BC`` is absent or unparseable. The
        component count drives the colour-space dispatch (1 → DeviceGray,
        3 → DeviceRGB, 4 → DeviceCMYK)."""
        bc = soft_mask.get_backdrop_color()
        if bc is None:
            return (0, 0, 0)
        try:
            flat = bc.to_float_array()
        except Exception:  # noqa: BLE001
            return (0, 0, 0)
        if not flat:
            return (0, 0, 0)
        if len(flat) == 1:
            g = float(flat[0])
            return _rgb_bytes(g, g, g)
        if len(flat) == 4:
            return _cmyk_to_rgb_bytes(*(float(v) for v in flat[:4]))
        # 3-channel (DeviceRGB / unknown 3-channel) — pad / clamp.
        padded = list(flat) + [0.0, 0.0, 0.0]
        return _rgb_bytes(
            float(padded[0]), float(padded[1]), float(padded[2])
        )

    @staticmethod
    def _build_transfer_lookup(tr: Any) -> list[int] | None:
        """Build a 256-entry PIL ``point`` lookup table from a transfer
        function. Returns ``None`` for ``/Identity`` (no remap needed)
        and on any function-type that fails to evaluate.

        Per PDF spec §11.6.5.3 the transfer function maps mask values in
        [0, 1] back to [0, 1]; we sample once per byte value."""
        if isinstance(tr, COSName) and tr.name in ("Identity", "Default"):
            return None
        from pypdfbox.pdmodel.common.function import PDFunction  # noqa: PLC0415

        try:
            fn = PDFunction.create(tr)
        except Exception:  # noqa: BLE001
            return None
        if fn is None:
            return None
        try:
            lut = []
            for i in range(256):
                out = fn.eval([i / 255.0])
                v = float(out[0]) if out else i / 255.0
                v = max(0.0, min(1.0, v))
                lut.append(int(round(v * 255.0)))
        except Exception:  # noqa: BLE001
            return None
        return lut

    def _render_transparency_group(self, form: Any) -> None:
        """Render a transparency-group Form XObject onto its own RGBA
        canvas and alpha-composite onto the parent.

        Honours PDF spec §11.4.7 group attributes:

        - ``/I`` (isolated, default false): when true the group is
          painted onto a fully transparent backdrop; when false the
          backdrop is the parent canvas's contents at group entry so
          paints inside the group can mix with what's already there.
        - ``/K`` (knockout, default false): when true each top-level
          painted child fully replaces (rather than composites with)
          prior contents at the group level. We snapshot the group
          canvas at group entry and restore it before each top-level
          painting operator (see :meth:`process_operator`).
        - ``/CS`` (group colour space): the group's blending colour
          space (DeviceGray / DeviceRGB / DeviceCMYK / ICCBased / etc.).
          Lite renderer composes everything in sRGB; we read /CS for
          parity but log when it would alter the result.
        - Active ExtGState ``/SMask``: when set, after the group renders
          to its own canvas we rasterise the soft-mask group XObject,
          extract per-pixel alpha (via ``/S /Alpha`` or ``/Luminosity``
          + optional ``/TR`` transfer function), and multiply it into
          the group canvas's alpha before alpha-compositing onto the
          parent (PDF spec §11.6.5.2-3)."""
        assert self._image is not None
        assert self._draw is not None

        isolated = False
        knockout = False
        cs_obj: COSBase | None = None
        try:
            group = form.get_group()
        except Exception:  # noqa: BLE001
            group = None
        if isinstance(group, COSDictionary):
            isolated = group.get_boolean(COSName.get_pdf_name("I"), default=False)
            knockout = group.get_boolean(COSName.get_pdf_name("K"), default=False)
            cs_obj = group.get_dictionary_object(COSName.get_pdf_name("CS"))
            if cs_obj is not None:
                # Parity log only — lite renderer always composes in sRGB.
                cs_repr = (
                    cs_obj.name if isinstance(cs_obj, COSName) else type(cs_obj).__name__
                )
                _log.debug(
                    "rendering: transparency group /CS=%s — lite renderer "
                    "composites in sRGB regardless",
                    cs_repr,
                )

        # Flush any pending aggdraw strokes onto the parent canvas before
        # we redirect to a fresh group canvas — otherwise they'd be
        # silently dropped on the floor when we replace ``self._draw``.
        self._draw.flush()

        parent_image = self._image
        parent_draw = self._draw
        # Initial group backdrop:
        #   isolated → fully transparent (group's own paints determine
        #     final alpha; matches the §11.4.7.2 isolated rule).
        #   non-isolated → an RGBA copy of the parent so the group's
        #     paints mix with the existing page contents during its
        #     own rendering (§11.4.7.2 non-isolated rule).
        if isolated:
            group_canvas = Image.new("RGBA", parent_image.size, (0, 0, 0, 0))
        else:
            group_canvas = parent_image.convert("RGBA")
        # The renderer's path/text helpers blit through aggdraw which
        # only supports RGB(A) PIL images — RGBA works.
        self._image = group_canvas
        self._draw = aggdraw.Draw(group_canvas)
        self._draw.setantialias(True)

        # Knockout setup: capture the group-entry pixels so subsequent
        # top-level paints can revert to them (see process_operator).
        prev_knockout_active = self._knockout_active
        prev_knockout_snapshot = self._knockout_snapshot
        prev_knockout_form_depth = self._knockout_form_depth
        if knockout:
            self._knockout_active = True
            self._knockout_snapshot = group_canvas.copy()
            # Start at -1 so the first ``_process_form_bytes`` increment
            # lands on 0 (the group's own top-level operators); nested
            # form Do calls then run at depth >= 1 and don't fire the
            # snapshot reset.
            self._knockout_form_depth = -1
        # Suppress per-paint SMask while rendering the group's own contents
        # (the SMask is applied once at the group's composite step below).
        self._transparency_group_depth += 1
        try:
            self._render_form_xobject(form)
        finally:
            self._transparency_group_depth -= 1
            # Commit any final group strokes, then composite back.
            current = self._draw
            if current is not None:
                current.flush()
            self._image = parent_image
            self._draw = parent_draw
            # Restore prior knockout state (handles nested groups).
            self._knockout_active = prev_knockout_active
            self._knockout_snapshot = prev_knockout_snapshot
            self._knockout_form_depth = prev_knockout_form_depth

        # Apply ExtGState /SMask (PDF spec §11.6.5.2): if a soft mask
        # is active, multiply the group's alpha by the mask's alpha
        # before compositing onto the parent.
        soft_mask = self._gs.soft_mask
        if soft_mask is not None:
            try:
                mask_alpha = self._render_soft_mask_alpha(
                    soft_mask, group_canvas.size
                )
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: soft-mask render failed: %s", exc)
                mask_alpha = None
            if mask_alpha is not None:
                # Combine: out_alpha = group_alpha * mask_alpha / 255.
                bands = group_canvas.split()
                new_alpha = ImageChops.multiply(bands[3], mask_alpha)
                group_canvas = Image.merge(
                    "RGBA", (bands[0], bands[1], bands[2], new_alpha)
                )

        # Composite the group result onto the parent. When the active
        # ExtGState blend mode is non-Normal (PDF 32000-1 §11.4.7.4 +
        # §11.3.5) the group is treated as the source and the parent as
        # the backdrop in the chosen blend formula; otherwise plain
        # alpha-over via Pillow's native ``alpha_composite``.
        parent_rgba = parent_image.convert("RGBA")
        blend_mode = self._gs.blend_mode
        if blend_mode is not None:
            blended = PDFRenderer._blend(group_canvas, parent_rgba, blend_mode)
            composited = blended.convert("RGB")
        else:
            parent_rgba.alpha_composite(group_canvas)
            composited = parent_rgba.convert("RGB")
        # In-place pixel copy keeps ``self._image`` identity stable
        # across the rest of the page render.
        parent_image.paste(composited, (0, 0))
        # Re-attach the aggdraw wrapper so further drawing sees the
        # composited pixels.
        self._draw = aggdraw.Draw(parent_image)
        self._draw.setantialias(True)

    def _restore_knockout_snapshot(self) -> None:
        """Restore the group canvas to the snapshot taken at knockout-
        group entry. Called immediately before each top-level painting
        operator inside a ``/K true`` group so each child object fully
        replaces prior contents (PDF spec §11.4.7.3)."""
        if self._knockout_snapshot is None or self._image is None:
            return
        # Flush any aggdraw work to the canvas first so we don't drop
        # buffered strokes as we replace pixels underneath them.
        if self._draw is not None:
            self._draw.flush()
        # In-place pixel copy keeps ``self._image`` identity stable.
        self._image.paste(self._knockout_snapshot, (0, 0))
        # Re-bind the aggdraw wrapper to see the restored pixels.
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _process_form_bytes(self, data: bytes) -> None:
        """Internal: feed a Form XObject's content-stream bytes through
        the same dispatch loop ``process_page`` uses.

        While inside a knockout group the depth counter is bumped so
        :meth:`process_operator` only fires the snapshot reset for the
        *top-level* group children, not for paints inside nested forms
        (PDF spec §11.4.7.3)."""
        from pypdfbox.pdfparser.pdf_stream_parser import (  # noqa: PLC0415
            PDFStreamParser,
        )

        if self._knockout_active:
            self._knockout_form_depth += 1
        try:
            with RandomAccessReadBuffer(data) as src:
                parser = PDFStreamParser(src)
                self._dispatch_tokens(parser)
        finally:
            if self._knockout_active:
                self._knockout_form_depth -= 1

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
        to_pil_image = getattr(image, "to_pil_image", None)
        if callable(to_pil_image):
            decoded = to_pil_image()
            if isinstance(decoded, Image.Image):
                return decoded.convert("RGB")

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

        # Raw raster path. ``PDColorSpace`` wrappers expose
        # ``get_name()`` (the spec colour-space name, e.g.
        # ``"DeviceRGB"`` / ``"ICCBased"`` / ``"Indexed"`` /
        # ``"Separation"`` / ``"DeviceN"``) and ``to_rgb_image(raster,
        # w, h)`` for the generic sample-through-transform conversion.
        # Direct ``DeviceRGB`` / ``DeviceGray`` cases build the PIL
        # image straight from the bytes (fastest path); every other
        # colour space (Indexed, ICCBased, Separation, DeviceN, CalRGB,
        # CalGray, Lab) is routed through the typed wrapper's transform.
        #
        # Wave 1385 reworked colour-space dispatch — the old
        # ``image.get_color_space().name`` pattern raised
        # ``AttributeError`` on every non-``Device*`` colour space
        # because the typed wrappers don't expose a literal ``.name``
        # attribute; the exception fell into the outer ``_op_do``
        # ``except`` and the image was silently dropped. Mirrors
        # upstream ``PageDrawer.drawImage`` which routes through
        # ``PDColorSpace.toRGBImage``.
        bpc = image.get_bits_per_component()
        if bpc not in (8, -1):  # -1 means absent → assume 8
            return None
        try:
            cs = image.get_color_space()
        except Exception:  # noqa: BLE001
            cs = None
        cs_name = cs.get_name() if cs is not None else None
        with image.create_input_stream() as src:
            data = src.read()
        if cs_name == "DeviceRGB" or (
            cs_name is None and len(data) >= width * height * 3
        ):
            return Image.frombytes(
                "RGB", (width, height), data[: width * height * 3]
            )
        if cs_name == "DeviceGray":
            return Image.frombytes(
                "L", (width, height), data[: width * height]
            ).convert("RGB")
        if cs is not None:
            to_rgb_image = getattr(cs, "to_rgb_image", None)
            if callable(to_rgb_image):
                try:
                    result = to_rgb_image(data, width, height)
                except Exception as exc:  # noqa: BLE001
                    _log.debug(
                        "rendering: %s.to_rgb_image failed: %s",
                        type(cs).__name__,
                        exc,
                    )
                    return None
                if isinstance(result, Image.Image):
                    return result.convert("RGB")
        return None

    def _paint_stencil_mask(self, image: Any) -> None:
        """Paint a stencil-mask image XObject in the current non-stroking
        colour. Mirrors upstream ``PageDrawer.drawImage`` (lines
        1078-1244) which detects ``isStencil()`` and feeds the 1-bit
        matte into a coloured-mask paint.

        Per PDF spec §8.9.5.4, a stencil image (``/ImageMask true``)
        sample bytes are a 1-bit-per-pixel matte: a ``0`` bit means the
        pixel is *opaque* and is painted with the current non-stroking
        colour; a ``1`` bit means the pixel is *transparent* and the
        backdrop shows through (the ``/Decode`` array can invert this —
        the default for a stencil is ``[0 1]``).

        Steps:

        1. Decode the 1-bit matte to an 8-bit alpha plane via
           :func:`_unpack_sub_byte_samples` (existing helper).
        2. Apply ``/Decode`` semantics: a default ``[0 1]`` means
           sample-0 → 255 (opaque) and sample-1 → 0 (transparent).
           When ``/Decode [1 0]`` is supplied the polarity is swapped.
        3. Build an RGBA image where every pixel carries the current
           non-stroking RGB colour and the alpha is the decoded matte.
        4. Hand that off to :meth:`_paste_image` so the existing CTM /
           clip / blend / SMask pipeline still runs on the stencil
           output exactly as it would for an inline-coloured image.
        """
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            _unpack_sub_byte_samples,
        )

        width = int(image.get_width())
        height = int(image.get_height())
        if width <= 0 or height <= 0:
            return
        bpc = image.get_bits_per_component()
        if bpc not in (1, -1):
            # Stencils are spec-mandated 1 bpc; reject malformed ones.
            return
        with image.create_input_stream() as src:
            data = src.read()
        samples = _unpack_sub_byte_samples(data, width, height, 1)
        if samples is None:
            return
        # Apply /Decode. Spec default for a stencil is [0 1] → 0 paints,
        # 1 is transparent. [1 0] reverses (0 transparent, 1 paints).
        decode = image.get_decode()
        if decode is not None and len(decode) >= 2 and decode[0] > decode[1]:
            opaque_sample = 1
        else:
            opaque_sample = 0
        # Build the per-pixel alpha plane (255 where the stencil is
        # opaque, 0 elsewhere).
        alpha_bytes = bytearray(width * height)
        for i, s in enumerate(samples):
            alpha_bytes[i] = 255 if s == opaque_sample else 0
        alpha = Image.frombytes("L", (width, height), bytes(alpha_bytes))
        # Tint every pixel with the active non-stroking colour and
        # apply the matte as the alpha channel; the paste path then
        # alpha-composites onto the page canvas.
        r, g, b = self._gs.fill_rgb
        rgba = Image.new("RGBA", (width, height), (r, g, b, 0))
        rgba.putalpha(alpha)
        self._paste_image(rgba)

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
        resized = pil_image.resize((target_w, target_h), Image.Resampling.BILINEAR)
        flipped = resized.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        # If the source image carries an alpha channel (e.g. an SMask
        # was applied upstream), split it off and use it as the paste
        # mask so transparent pixels don't overwrite the canvas.
        alpha: Image.Image | None = None
        if flipped.mode == "RGBA":
            alpha = flipped.split()[3]
            flipped_rgb = flipped.convert("RGB")
        else:
            flipped_rgb = flipped

        clip_mask = self._gs.clip_mask
        blend_mode = self._gs.blend_mode
        if blend_mode is not None:
            # Non-Normal blend mode active — route through ``_blend`` so the
            # source image's RGB components are combined with the backdrop
            # via the chosen separable blend formula instead of plain
            # alpha-over. The clip / SMask alpha pipeline still runs but
            # gates the *blended* pixels rather than the raw ones.
            self._paste_image_with_blend(
                flipped_rgb,
                alpha,
                (x0, y0, target_w, target_h),
                clip_mask,
                blend_mode,
            )
        elif clip_mask is None:
            if alpha is None:
                self._image.paste(flipped_rgb, (x0, y0))
            else:
                self._image.paste(flipped_rgb, (x0, y0), alpha)
        else:
            # Build a mask of the image bbox inside the clip and composite.
            paste_mask = Image.new("L", self._image.size, 0)
            paste_mask.paste(255, (x0, y0, x0 + target_w, y0 + target_h))
            combined = ImageChops.multiply(paste_mask, clip_mask)
            if alpha is not None:
                # Multiply the per-pixel alpha into the bbox-restricted mask
                # so transparent SMask regions don't over-paint the clip.
                full_alpha = Image.new("L", self._image.size, 0)
                full_alpha.paste(alpha, (x0, y0))
                combined = ImageChops.multiply(combined, full_alpha)
            # Place the image into a same-size buffer to align with mask.
            staging = Image.new("RGB", self._image.size, (255, 255, 255))
            staging.paste(flipped_rgb, (x0, y0))
            self._image.paste(staging, (0, 0), combined)

        # Re-attach the aggdraw wrapper so further drawing sees the new
        # pixels.
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _paste_image_with_blend(
        self,
        flipped_rgb: Image.Image,
        alpha: Image.Image | None,
        bbox: tuple[int, int, int, int],
        clip_mask: Image.Image | None,
        blend_mode: Any,
    ) -> None:
        """Paste ``flipped_rgb`` through a non-Normal blend mode.

        Builds a full-canvas RGBA source layer with the image staged at
        the bbox (transparent elsewhere), runs :meth:`_blend` against the
        current canvas as backdrop, then commits the result back to
        ``self._image``. ``clip_mask`` (if any) and ``alpha`` (if any)
        compose into the source's per-pixel alpha so the blend only
        affects the visible region — outside the clip / where the image
        is transparent the backdrop pixel is preserved unchanged.
        """
        assert self._image is not None
        x0, y0, target_w, target_h = bbox
        # Build a full-canvas source: opaque only inside the bbox.
        source = Image.new("RGBA", self._image.size, (0, 0, 0, 0))
        source_alpha = Image.new("L", self._image.size, 0)
        if alpha is None:
            source_alpha.paste(255, (x0, y0, x0 + target_w, y0 + target_h))
        else:
            source_alpha.paste(alpha, (x0, y0))
        if clip_mask is not None:
            source_alpha = ImageChops.multiply(source_alpha, clip_mask)
        source.paste(flipped_rgb, (x0, y0))
        source.putalpha(source_alpha)

        backdrop = self._image.convert("RGBA")
        blended = PDFRenderer._blend(source, backdrop, blend_mode)
        # Commit back to the page canvas, preserving its mode (RGB / RGBA).
        if self._image.mode == "RGB":
            self._image.paste(blended.convert("RGB"), (0, 0))
        else:
            self._image.paste(blended, (0, 0))

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
        from pypdfbox.pdmodel.graphics.image.pd_inline_image import (  # noqa: PLC0415
            PDInlineImage,
        )

        try:
            inline_image = PDInlineImage(params, data, self._resources)
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: cannot construct inline image: %s", exc)
            return
        self.show_inline_image(inline_image)

    def show_inline_image(self, inline_image: Any) -> None:
        """Paste a fully-constructed :class:`PDInlineImage` onto the
        current canvas honouring the active CTM.

        Mirrors upstream's
        ``PDFGraphicsStreamEngine.showInlineImage``-via-``drawImage``
        path: an inline image is rendered through the same paste
        pipeline as an XObject image. We first try the
        :meth:`PDInlineImage.to_pil_image` helper (handles JPEG / JPX /
        plain DeviceRGB / DeviceGray) and fall back to the legacy
        :meth:`_decode_inline_image` path for parameter shapes the
        helper doesn't yet cover (so previously-rendering inline images
        keep rendering).
        """
        if self._draw is None or self._image is None:
            return
        pil_image: Image.Image | None
        try:
            pil_image = inline_image.to_pil_image()
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: cannot decode inline image (helper): %s", exc)
            pil_image = None
        if pil_image is None:
            try:
                pil_image = self._decode_inline_image(
                    inline_image.get_cos_object(), inline_image.get_stream()
                )
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: cannot decode inline image: %s", exc)
                return
        if pil_image is None:
            return
        self._paste_image(pil_image)

    def _decode_inline_image(
        self, params: COSDictionary | None = None, data: bytes | None = None
    ) -> Image.Image | None:
        """Build a PIL image from inline-image parameters + bytes.

        Inline-image dictionaries use abbreviated keys per PDF spec
        §8.9.7 Table 92 (W/H/CS/BPC/F). Recognises the same colour-space
        set as :meth:`_decode_image_xobject` for XObject-form images:
        DeviceGray, DeviceRGB, DeviceCMYK, Indexed, ICCBased, Separation,
        DeviceN, and their abbreviated forms (G, RGB, CMYK, I). Per-pixel
        components are routed through the colour space's ``to_rgb``
        transform (mirrors upstream ``PDImageXObject.getColorImage`` +
        ``PDInlineImage`` decode).

        Backwards-compatibility: pre-1385 callers invoked this as a
        ``@staticmethod`` (``PDFRenderer._decode_inline_image(params,
        data)``). When that calling form lands here ``self`` arrives as
        the params dict; we detect it and forward to the bound-method
        path with ``self._resources`` left implicit (``None`` means
        only the direct device CSes resolve, which is exactly what the
        pre-1385 implementation supported).
        """
        # Pre-1385 static call: ``PDFRenderer._decode_inline_image(
        # params, data)`` → here ``self == params`` and ``params ==
        # data``. Detect and dispatch.
        if not isinstance(self, PDFRenderer):
            return _decode_inline_image_static(self, params)
        # Else: instance method form. `params` and `data` are now the
        # named args.
        if params is None or data is None:
            return None

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

        # Resolve the colour space. Inline images can name the space
        # directly (DeviceRGB / G / RGB / CMYK / I / …) or reference a
        # named entry in /Resources/ColorSpace (Indexed, ICCBased,
        # Separation, DeviceN). Abbreviated names map straight to the
        # built-in singletons; everything else routes through
        # :meth:`_resolve_color_space` for resource lookup.
        cs_abbrev = {
            "G": "DeviceGray",
            "RGB": "DeviceRGB",
            "CMYK": "DeviceCMYK",
            "I": "Indexed",
        }
        colour_space: Any | None = None
        cs_name: str | None = None
        if isinstance(cs_obj, COSName):
            cs_name = cs_abbrev.get(cs_obj.name, cs_obj.name)
            if cs_name in _BUILTIN_DEVICE_COLOR_SPACES:
                colour_space = _BUILTIN_DEVICE_COLOR_SPACES[cs_name]
            else:
                # Try the resources lookup with the *unabbreviated* name
                # so /Resources/ColorSpace entries resolve.
                resolved = self._resolve_color_space(
                    COSName.get_pdf_name(cs_name)
                )
                if resolved is not None:
                    colour_space = resolved
        elif cs_obj is not None:
            # Direct CS array form (e.g. ``[/Indexed /DeviceRGB 255 < … >]``,
            # ``[/ICCBased <stream>]``, ``[/Separation /Name /DeviceCMYK <fn>]``).
            try:
                from pypdfbox.pdmodel.graphics.color.pd_color_space import (  # noqa: PLC0415
                    PDColorSpace,
                )

                colour_space = PDColorSpace.create(cs_obj)
            except Exception as exc:  # noqa: BLE001
                _log.debug(
                    "rendering: inline image CS array failed to resolve: %s",
                    exc,
                )
                colour_space = None

        # Default colour space when ``/CS`` is absent: DeviceRGB if the
        # payload looks 3-channel, else DeviceGray. Mirrors the legacy
        # behaviour from before colour-space dispatch landed.
        if colour_space is None:
            if cs_name is None and len(data) >= width * height * 3:
                colour_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceRGB"]
            elif cs_name is None:
                colour_space = _BUILTIN_DEVICE_COLOR_SPACES["DeviceGray"]
            else:
                _log.debug(
                    "rendering: inline image CS %s did not resolve", cs_name
                )
                return None

        # Fast paths for the device singletons — avoid the per-pixel
        # Python loop that the generic path would take.
        builtin_gray = _BUILTIN_DEVICE_COLOR_SPACES["DeviceGray"]
        builtin_rgb = _BUILTIN_DEVICE_COLOR_SPACES["DeviceRGB"]
        builtin_cmyk = _BUILTIN_DEVICE_COLOR_SPACES["DeviceCMYK"]
        if colour_space is builtin_rgb:
            return Image.frombytes(
                "RGB", (width, height), data[: width * height * 3]
            )
        if colour_space is builtin_gray:
            return Image.frombytes(
                "L", (width, height), data[: width * height]
            ).convert("RGB")
        if colour_space is builtin_cmyk:
            # PIL native CMYK -> RGB conversion (perceptual, no profile).
            return Image.frombytes(
                "CMYK", (width, height), data[: width * height * 4]
            ).convert("RGB")

        # Indexed: 1 byte per pixel, palette lookup via
        # ``PDIndexed.to_rgb_image`` (library-first Pillow palette path).
        to_rgb_image = getattr(colour_space, "to_rgb_image", None)
        if callable(to_rgb_image):
            try:
                rgb_image = to_rgb_image(
                    data[: width * height], width, height
                )
            except Exception as exc:  # noqa: BLE001
                _log.debug(
                    "rendering: inline image %s.to_rgb_image failed: %s",
                    type(colour_space).__name__,
                    exc,
                )
                rgb_image = None
            if rgb_image is not None:
                # Some palette paths return raw "P" or "L"; ensure RGB.
                if rgb_image.mode != "RGB":
                    rgb_image = rgb_image.convert("RGB")
                return rgb_image

        # Generic multi-channel path — walk pixels through the colour
        # space's ``to_rgb`` and stage to an RGB Pillow image. Handles
        # ICCBased / Separation / DeviceN / CalGray / CalRGB / Lab.
        components_count = 0
        try:
            components_count = int(colour_space.get_number_of_components())
        except Exception:  # noqa: BLE001
            components_count = 0
        if components_count <= 0:
            _log.debug(
                "rendering: inline image %s reports zero components",
                type(colour_space).__name__,
            )
            return None
        expected = width * height * components_count
        if len(data) < expected:
            return None
        pixels = bytearray(width * height * 3)
        i = 0
        out = 0
        to_rgb = getattr(colour_space, "to_rgb", None)
        if not callable(to_rgb):
            return None
        try:
            for _ in range(width * height):
                comps = tuple(
                    data[i + k] / 255.0 for k in range(components_count)
                )
                i += components_count
                rgb_floats = to_rgb(comps)
                if (
                    rgb_floats is None
                    or not isinstance(rgb_floats, (tuple, list))
                    or len(rgb_floats) < 3
                ):
                    pixels[out] = 0
                    pixels[out + 1] = 0
                    pixels[out + 2] = 0
                else:
                    pixels[out] = _clamp_byte(float(rgb_floats[0]))
                    pixels[out + 1] = _clamp_byte(float(rgb_floats[1]))
                    pixels[out + 2] = _clamp_byte(float(rgb_floats[2]))
                out += 3
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: inline image %s per-pixel to_rgb failed: %s",
                type(colour_space).__name__,
                exc,
            )
            return None
        return Image.frombytes("RGB", (width, height), bytes(pixels))

    # ------------------------------------------------------------------
    # text operators (BT/ET, Tf, Tc/Tw/TL/Tz/Ts, Td/TD/Tm/T*, Tj/TJ/'/")
    # ------------------------------------------------------------------

    def _op_begin_text(self, _op: Any, _operands: list[COSBase]) -> None:
        # PDF spec §9.4.1: BT initialises text matrix and text line matrix
        # to the identity. Font/size/etc. carry over from previous BT.
        self._gs.text_matrix = _IDENTITY
        self._gs.text_line_matrix = _IDENTITY
        # Text rendering modes 4..7 accumulate glyph outlines for the
        # next ET to intersect into the GS clip — start fresh per spec
        # PDF 32000-1 §9.3.6 ("the clipping path … is established at the
        # end of the text object that initiated it").
        self._text_clip_paths = []

    def _op_end_text(self, _op: Any, _operands: list[COSBase]) -> None:
        # PDF 32000-1 §9.3.6: at ET, if any glyph was shown under a Tr
        # mode in {4, 5, 6, 7}, the union of those glyph outlines becomes
        # an addition to the current clipping path. We intersect with any
        # existing GS clip so subsequent paint operators are clipped to
        # the union of all such glyph outlines.
        if self._text_clip_paths:
            self._commit_text_clip()
        self._text_clip_paths = []

    def _commit_text_clip(self) -> None:
        """Rasterise the union of accumulated text-clip paths into an
        alpha mask and intersect with the active GS clip. Called at
        ``ET`` whenever the BT/ET block invoked a clipping ``Tr`` mode
        (4..7)."""
        if self._image is None or not self._text_clip_paths:
            return
        try:
            import skia  # type: ignore[import-not-found]  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: skia unavailable for text clip commit: %s", exc)
            return
        width_px, height_px = self._image.size
        # Union all paths into one composite path (skia handles overlapping
        # subpaths via the non-zero / even-odd rule on the resulting
        # `addPath`-merged outline). PDF text-clip uses the non-zero rule
        # per upstream PageDrawer.endText -> Type3PageDrawer behaviour.
        union = skia.Path()
        for sub in self._text_clip_paths:
            union.addPath(sub)
        union.setFillType(skia.PathFillType.kWinding)
        bounds = union.getBounds()
        if (
            bounds.width() <= 0.0
            or bounds.height() <= 0.0
            or not (math.isfinite(bounds.width())
                    and math.isfinite(bounds.height()))
        ):
            return
        # Rasterise directly — the path is already in device pixels so
        # we do not need the page CTM here.
        row_bytes = width_px * 4
        pixels = bytearray(width_px * height_px * 4)
        info = skia.ImageInfo.Make(
            width_px, height_px,
            skia.kRGBA_8888_ColorType,
            skia.kUnpremul_AlphaType,
        )
        surface = skia.Surface.MakeRasterDirect(info, pixels, row_bytes)
        if surface is None:  # pragma: no cover - skia always succeeds
            return
        canvas = surface.getCanvas()
        paint = skia.Paint(
            Color=skia.ColorSetARGB(255, 255, 255, 255),
            Style=skia.Paint.kFill_Style,
            AntiAlias=True,
        )
        canvas.drawPath(union, paint)
        surface.flushAndSubmit()
        rgba = Image.frombytes(
            "RGBA", (width_px, height_px), bytes(pixels),
        )
        new_clip = rgba.split()[3]
        existing = self._gs.clip_mask
        if existing is not None:
            new_clip = ImageChops.multiply(existing, new_clip)
        self._gs.clip_mask = new_clip

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
        if not isinstance(font_dict, COSDictionary):
            self._font_cache[cache_key] = font_dict
            return font_dict
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

    def _op_set_text_rendering_mode(
        self, _op: Any, operands: list[COSBase]
    ) -> None:
        """``Tr`` — set the text rendering mode (PDF 32000-1 §9.3.6 /
        Table 106). Operand is an integer in 0..7; values outside that
        range are clamped (mirrors upstream
        ``SetTextRenderingMode.process`` which calls
        ``RenderingMode.fromInt`` with a try/catch and falls back to
        ``FILL`` on out-of-range, but PDFBox swallows the
        IndexOutOfBoundsException with a debug log)."""
        if not operands:
            return
        mode = int(_to_float(operands[0]))
        if mode < 0:
            mode = 0
        elif mode > 7:
            mode = 7
        self._gs.text_rendering_mode = mode

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

        # Type 3 fonts (PDF 32000-1 §9.6.5): each glyph is a /CharProcs
        # content stream painted in glyph space, then mapped through
        # /FontMatrix into text space. Route to the dedicated handler so
        # the TTF / Type1 / Type1C branches below don't have to learn the
        # charproc protocol.
        from pypdfbox.pdmodel.font.pd_type3_font import (  # noqa: PLC0415
            PDType3Font,
        )

        if isinstance(font, PDType3Font):
            self._show_type3_string(font, data)
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
        program is available, falling back to the bundled Liberation
        substitute's UPEM for non-embedded Standard 14 references.

        Routes through ``font._get_type1_font()`` (PFB) or
        ``font._get_cff_font()`` (CFF) — whichever exists. When neither
        embedded program is present *and* ``/BaseFont`` resolves to one of
        the 14 Standard PostScript names with a Liberation substitute
        mapped (Helvetica / Times-Roman / Courier families), the
        Liberation TTF's UPEM is returned so the caller can drive the
        Type 1 path-fill branch over
        :meth:`PDType1Font.get_glyph_path`'s Liberation-backed outlines.
        Symbol / ZapfDingbats have no Liberation equivalent, so this
        returns ``None`` for them and the caller falls back to the
        placeholder rectangle.
        """
        from pypdfbox.pdmodel.font.pd_type1_font import (  # noqa: PLC0415
            PDType1Font,
        )
        from pypdfbox.pdmodel.font.pd_type1c_font import (  # noqa: PLC0415
            PDType1CFont,
        )

        if isinstance(font, PDType1CFont):
            cff_program = font._get_cff_font()  # noqa: SLF001
            if cff_program is not None:
                return cff_program.units_per_em
            # Falls through to the Liberation branch below — PDType1CFont
            # is a subclass of PDType1Font so the isinstance check there
            # would match too if we didn't return early.
        if isinstance(font, PDType1Font):
            type1_program = font._get_type1_font()  # noqa: SLF001
            if type1_program is not None:
                return type1_program.units_per_em
            # No embedded program — try the Liberation substitute when the
            # font is one of the Standard 14.
            from pypdfbox.pdmodel.font.standard14_fonts import (  # noqa: PLC0415
                Standard14Fonts,
            )

            base_font = font.get_name()
            if base_font is None:
                return None
            substitute = Standard14Fonts.get_substitute_ttf(base_font)
            if substitute is None:
                return None
            try:
                return int(substitute.get_units_per_em())
            except Exception:  # noqa: BLE001
                return None
        return None

    def _resolve_font_program(self, font: Any) -> Any | None:
        """Return a :class:`FontBoxFont` program for ``font``, falling back
        through the substitution chain when the PDF didn't embed a program.

        Implements the resolution order from PDF 32000-1 §9.8 / §9.10:

        1. Embedded program — ``/FontFile`` (Type 1), ``/FontFile2``
           (TrueType) or ``/FontFile3`` (CFF / OpenType). Returned via
           the existing ``_get_*`` helpers when present.
        2. :class:`FontMappers` lookup by PostScript name + descriptor
           flags (Wave 30). Resolves Standard 14 references and any
           system-font substitution the active mapper provides.
        3. Style-only fallback by descriptor flags — Helvetica for
           proportional, Courier for fixed-pitch, italic / bold variants
           when those flags are set. The default
           :class:`DefaultFontMapper` already implements this last leg as
           the universal-fallback contract on
           :meth:`get_font_box_font`, so the call in step 2 always
           returns *something* unless the mapper has been replaced.

        Returns ``None`` only when every step fails (no embedded program,
        no mapper match, and the active mapper opted out of fallback).
        Cached per-font to avoid re-walking the mapper for every glyph.
        """
        key = id(font)
        if key in self._font_program_cache:
            return self._font_program_cache[key]

        # Step 1 — embedded program. Reuse the existing detectors so any
        # caller-side caching they do (TTF parse cache etc.) is preserved.
        ttf, _glyph_set = self._get_ttf_glyph_set(font)
        if ttf is not None:
            self._font_program_cache[key] = ttf
            return ttf

        # Type1 / Type1C — pull the embedded program directly. ``ttf``
        # was None above, so this is only hit for Type1 / CFF fonts.
        try:
            from pypdfbox.pdmodel.font.pd_type1_font import (  # noqa: PLC0415
                PDType1Font,
            )
            from pypdfbox.pdmodel.font.pd_type1c_font import (  # noqa: PLC0415
                PDType1CFont,
            )

            if isinstance(font, PDType1CFont):
                cff_program = font._get_cff_font()  # noqa: SLF001
                if cff_program is not None:
                    self._font_program_cache[key] = cff_program
                    return cff_program
            elif isinstance(font, PDType1Font):
                type1_program = font._get_type1_font()  # noqa: SLF001
                if type1_program is not None:
                    self._font_program_cache[key] = type1_program
                    return type1_program
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: embedded Type1/CFF probe failed: %s", exc)

        # Step 2 / 3 — FontMappers substitution chain.
        try:
            from pypdfbox.fontbox.font_mappers import (  # noqa: PLC0415
                FontMappers,
            )

            base_font = (
                font.get_name() if hasattr(font, "get_name") else None
            )
            descriptor = (
                font.get_font_descriptor()
                if hasattr(font, "get_font_descriptor")
                else None
            )
            mapper = FontMappers.instance()
            mapping = mapper.get_font_box_font(base_font or "", descriptor)
        except Exception as exc:  # noqa: BLE001
            _log.debug(
                "rendering: FontMappers lookup failed for %r: %s", font, exc
            )
            mapping = None

        substitute = mapping.get_font() if mapping is not None else None
        self._font_program_cache[key] = substitute
        return substitute

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
        glyph_to_device = _matmul(self._gs.ctm, glyph_to_device)
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
        # Walk the substitution chain (PDF 32000-1 §9.8 / §9.10) to upgrade
        # the placeholder advance with metrics from a Standard 14 / system
        # fallback when the PDFont itself couldn't supply a width for
        # ``code``. ``_font_width_units`` returns 500.0 as a hard default
        # for fonts with no ``get_glyph_width`` accessor; ``PDType1Font``
        # without an embedded program and without a Standard 14 BaseFont
        # match returns ``0.0`` from step 4 of its lookup. Both are signs
        # the caller has nothing better, so route through the FontMappers
        # fallback for a real metric.
        if advance_units == 500.0 or advance_units <= 0.0:
            substitute = self._resolve_font_program(font)
            if substitute is not None:
                with contextlib.suppress(Exception):
                    upgraded = self._fallback_advance_units(
                        substitute, code, advance_units
                    )
                    if upgraded > 0.0:
                        advance_units = upgraded
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

    @staticmethod
    def _fallback_advance_units(
        substitute: Any, code: int, default_units: float
    ) -> float:
        """Return ``substitute``'s advance width for ``code`` in 1/1000-em
        PDF units, or ``default_units`` when the lookup can't be resolved.

        ``substitute`` is a :class:`FontBoxFont` (typically a
        :class:`Standard14FontWrapper` for Type1 / Standard 14 fallbacks
        or a real :class:`TrueTypeFont` when a system font was matched).
        Both expose ``get_width(name)`` returning advance in font units —
        AFM widths are already in 1/1000-em, TTF widths need scaling by
        ``1000 / units_per_em``. We sniff the source by checking for
        ``get_units_per_em``.
        """
        # Map ``code`` to a glyph name via the standard PostScript
        # encoding. The default mapper always returns a Standard 14
        # wrapper, whose ``get_width`` keys on PostScript glyph names
        # (``"A"``, ``"space"``, ``".notdef"``, …) — so a code-to-name
        # round trip is unavoidable.
        from pypdfbox.fontbox.encoding.standard_encoding import (  # noqa: PLC0415
            StandardEncoding,
        )

        glyph_name = StandardEncoding.INSTANCE.get_name(code)
        if glyph_name == ".notdef":
            return default_units
        try:
            width = float(substitute.get_width(glyph_name))
        except Exception:  # noqa: BLE001
            return default_units
        if width <= 0.0:
            return default_units
        # TTF / system-font path — scale design units to 1/1000-em.
        upem = getattr(substitute, "get_units_per_em", None)
        if callable(upem):
            try:
                units = int(upem())
            except Exception:  # noqa: BLE001
                units = 0
            if units > 0:
                return width * (1000.0 / units)
        return width

    def _maybe_warn_standard14(self, font: Any) -> None:
        """Emit a one-time debug log for Standard 14 fonts with no bundled
        substitute available.

        All 14 canonical Standard PostScript names now resolve through a
        bundled substitute (Liberation for the Helvetica / Times-Roman /
        Courier branches, DejaVu Sans for Symbol / ZapfDingbats — see
        :meth:`Standard14Fonts.get_substitute_ttf`), so reaching this
        branch indicates either a substitute resource missing from the
        installed package or a Type 1 draw path that bypassed the
        upstream-symmetric outline branch — both worth a debug breadcrumb.
        """
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
        if base_font is None or not Standard14Fonts.contains_name(base_font):
            return
        # When a substitute exists, this draw path is a bug — the Type 1
        # branch above should have caught it. Skip the warn so we don't
        # generate noise for any well-mapped Standard 14 name.
        if Standard14Fonts.get_substitute_ttf(base_font) is not None:
            return
        self._warned_standard14_fonts.add(key)
        _log.debug(
            "rendering: %s is a Standard 14 font with no bundled "
            "substitute available; using placeholder rectangle "
            "(unexpected after Wave 1305 — substitute TTF resource "
            "may be missing from the installed package)",
            base_font,
        )

    @staticmethod
    def _build_aggdraw_path_from_commands(
        commands: list[_PathSegment], scale: float
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
        if callable(method):
            try:
                return int(method(code, ttf))
            except TypeError:
                # Some implementations ignore the ttf arg (signature may
                # be ``(code)`` only on subclasses).
                return int(method(code))
        public = getattr(font, "code_to_gid", None)
        if callable(public):
            try:
                return int(public(code))
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: code_to_gid failed for %d: %s", code, exc)
        cmap = ttf.get_unicode_cmap_subtable()
        if cmap is not None:
            return int(cmap.get_glyph_id(code))
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
        transform.

        Back-compat wrapper around :meth:`_paint_glyph_path` for the
        fill-only call sites. Routes through the mode-aware helper so any
        active ``Tr`` (text rendering mode) picks up the matching paint
        dispatch without the caller having to change.
        """
        self._paint_glyph_path(path, ctm, rgb)

    def _paint_glyph_path(
        self,
        path: aggdraw.Path,
        ctm: _Matrix,
        fill_rgb: tuple[int, int, int],
    ) -> None:
        """Paint ``path`` according to the current text rendering mode
        (PDF 32000-1 §9.3.6 / Table 106).

        ``path`` lives in glyph-local em coordinates and is mapped to the
        device by ``ctm`` (the per-glyph affine already folds in font
        size + horizontal scaling + rise + text matrix + page CTM).

        Mode dispatch:

        * 0 / 4 — fill (modes 4..7 also accumulate the glyph outline
          into :attr:`_text_clip_paths` so ``ET`` intersects the union
          into the GS clip);
        * 1 / 5 — stroke (uses ``stroke_rgb`` + ``line_width``);
        * 2 / 6 — fill *then* stroke;
        * 3 / 7 — invisible (no paint; still records the clip for 7).
        """
        mode = self._gs.text_rendering_mode
        do_fill = mode in (0, 2, 4, 6)
        do_stroke = mode in (1, 2, 5, 6)
        do_clip = mode in (4, 5, 6, 7)

        if do_clip:
            self._accumulate_text_clip_path(path, ctm)

        if not (do_fill or do_stroke):
            return  # modes 3 / 7 — invisible (clip-only for 7).

        clip_mask = self._gs.clip_mask
        if clip_mask is None:
            self._paint_glyph_path_direct(
                path, ctm, fill_rgb,
                do_fill=do_fill, do_stroke=do_stroke,
            )
        else:
            self._paint_glyph_path_through_clip(
                path, ctm, fill_rgb,
                do_fill=do_fill, do_stroke=do_stroke, clip_mask=clip_mask,
            )

    def _paint_glyph_path_direct(
        self,
        path: aggdraw.Path,
        ctm: _Matrix,
        fill_rgb: tuple[int, int, int],
        *,
        do_fill: bool,
        do_stroke: bool,
    ) -> None:
        """Paint ``path`` directly onto the canvas (no through-clip)."""
        assert self._draw is not None
        brush = aggdraw.Brush(fill_rgb) if do_fill else None
        pen = self._build_stroke_pen(ctm) if do_stroke else None
        self._draw.settransform(_to_pil_affine(ctm))
        try:
            self._draw.path(path, pen, brush)
        finally:
            self._draw.settransform()

    def _paint_glyph_path_through_clip(
        self,
        path: aggdraw.Path,
        ctm: _Matrix,
        fill_rgb: tuple[int, int, int],
        *,
        do_fill: bool,
        do_stroke: bool,
        clip_mask: Any,
    ) -> None:
        """Paint ``path`` onto a fresh transparent layer then composite
        through the active GS clip mask."""
        assert self._image is not None
        assert self._draw is not None
        self._draw.flush()
        layer = Image.new("RGBA", self._image.size, (0, 0, 0, 0))
        layer_draw = aggdraw.Draw(layer)
        layer_draw.setantialias(True)
        layer_draw.settransform(_to_pil_affine(ctm))
        brush = aggdraw.Brush(fill_rgb) if do_fill else None
        pen = self._build_stroke_pen(ctm) if do_stroke else None
        layer_draw.path(path, pen, brush)
        layer_draw.settransform()
        layer_draw.flush()
        layer_alpha = layer.split()[3]
        combined = ImageChops.multiply(layer_alpha, clip_mask)
        rgb_layer = layer.convert("RGB")
        self._image.paste(rgb_layer, (0, 0), combined)
        self._draw = aggdraw.Draw(self._image)
        self._draw.setantialias(True)

    def _build_stroke_pen(self, ctm: _Matrix) -> aggdraw.Pen:
        """Return an :class:`aggdraw.Pen` configured from the current GS
        stroke colour + line width.

        The line width on the GS is in **user space** (per PDF 32000-1
        §8.4.3.2). The per-glyph ``ctm`` we settransform onto the canvas
        before stroking carries the glyph-local-to-device affine — its
        scale is roughly ``font_size × page_scale``. Since skia strokes
        the path *before* the inverse of the canvas transform is applied,
        the effective stroke width in device pixels is
        ``pen.width × ctm_scale``. To land in device pixels at the GS
        line width, we therefore divide the user-space line width by the
        glyph-local-to-user portion of the transform (``ctm_scale /
        page_scale``) — which simplifies to using only the
        page-to-device scale for the pen width.

        The aggdraw shim's pen surface tops out at colour + width;
        line-cap / line-join / miter-limit / dash-pattern are carried on
        the GS for parity-test bookkeeping but the shim doesn't apply
        them at stroke time. Downstream tooling can still read them via
        the public PDExtendedGraphicsState getters.
        """
        ctm_scale = self._approx_scale(ctm)
        page_scale = self._approx_scale(self._full_ctm())
        # ``ctm_scale <= 0.0`` is a pathological / degenerate text matrix —
        # fall back to the page scale only (stroke ends up at user-space
        # width interpreted in glyph-local units, which is still better
        # than dividing by zero).
        ratio = page_scale if ctm_scale <= 0.0 else page_scale / ctm_scale
        width_px = max(0.5, self._gs.line_width * ratio)
        return aggdraw.Pen(self._gs.stroke_rgb, width=width_px)

    def _accumulate_text_clip_path(
        self, path: aggdraw.Path, ctm: _Matrix,
    ) -> None:
        """Bake ``path`` (glyph-local em coords) through ``ctm`` into a
        device-space ``skia.Path`` and append to :attr:`_text_clip_paths`.

        Text rendering modes 4..7 (PDF 32000-1 §9.3.6) add each glyph's
        outline to the clipping path; the spec says the clip update is
        deferred until ``ET``. We accumulate raw skia paths here and
        commit the union in :meth:`_op_end_text`.
        """
        try:
            import skia  # type: ignore[import-not-found]  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            _log.debug("rendering: skia unavailable for text clip: %s", exc)
            return
        try:
            sk_path: Any = path._sk  # noqa: SLF001
        except AttributeError:
            return
        # aggdraw's PIL-style affine: (a, b, c, d, e, f) means
        # x' = a*x + b*y + c ; y' = d*x + e*y + f. Map to skia's MakeAll.
        a, b, c, d, e, f = _to_pil_affine(ctm)
        matrix = skia.Matrix.MakeAll(a, b, c, d, e, f, 0.0, 0.0, 1.0)
        transformed = skia.Path()
        sk_path.transform(matrix, transformed)
        self._text_clip_paths.append(transformed)

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

    # ------------------------------------------------------------------
    # Type 3 font (charproc) rendering — PDF 32000-1 §9.6.5
    # ------------------------------------------------------------------

    def _op_type3_d0(self, _op: Any, operands: list[COSBase]) -> None:
        """``wx wy d0`` — sets the glyph advance for an *uncoloured* Type 3
        glyph. The charproc must not specify colour after ``d0`` (it
        inherits the calling context's colour). The lite renderer records
        the advance on the engine so callers can override the ``/Widths``
        value (PDFBox parity); painting otherwise proceeds normally.
        """
        if len(operands) < 2:
            return
        self._type3_d0_wx = _to_float(operands[0])
        # wy (operand 1) is reserved as 0 per spec.

    def _op_type3_d1(self, _op: Any, operands: list[COSBase]) -> None:
        """``wx wy llx lly urx ury d1`` — sets the glyph advance and
        bounding box for a *coloured* Type 3 glyph. Per PDF 32000-1
        §9.6.5.3 the bbox MUST tightly enclose the glyph; the renderer
        treats it as a clip so any stray paint outside the bbox is
        suppressed (matches upstream ``Type3PageDrawer.processType3Stream``
        glyph-bounds clipping). Painting otherwise proceeds with the
        charproc's own colour.
        """
        if len(operands) < 6:
            return
        self._type3_d1_wx = _to_float(operands[0])
        # Operand 1 (wy) is reserved.
        llx = _to_float(operands[2])
        lly = _to_float(operands[3])
        urx = _to_float(operands[4])
        ury = _to_float(operands[5])
        # Degenerate / inverted bboxes: skip the clip (PDFBox ignores them
        # — the painted glyph still shows up).
        if urx <= llx or ury <= lly:
            return
        # Build a rectangle subpath in glyph-space coords; the active CTM
        # already folds /FontMatrix + text_local + page_ctm, so the rect
        # lands in the right place after the engine's transform.
        prev_subpaths = self._subpaths
        prev_current_subpath = self._current_subpath
        prev_current_point = self._current_point
        prev_pending_clip = self._pending_clip
        self._subpaths = []
        self._current_subpath = None
        self._pending_clip = None
        self._start_subpath(llx, lly)
        assert self._current_subpath is not None
        self._current_subpath.append(("L", urx, lly))
        self._current_subpath.append(("L", urx, ury))
        self._current_subpath.append(("L", llx, ury))
        self._current_subpath.append(("Z",))
        self._pending_clip = "W"
        # Apply the clip immediately so the rest of the charproc paints
        # clipped to the declared bounds.
        self._apply_pending_clip(default_even_odd=False)
        # Restore the page-level path state so the charproc's own path
        # construction starts from a clean slate.
        self._subpaths = prev_subpaths
        self._current_subpath = prev_current_subpath
        self._current_point = prev_current_point
        self._pending_clip = prev_pending_clip

    def _show_type3_string(self, font: Any, data: bytes) -> None:
        """Render a Tj / TJ string against a :class:`PDType3Font` by
        recursively driving each glyph's /CharProcs content stream.

        Type 3 fonts always use single-byte codes (PDF 32000-1 §9.6.5):
        ``/CharProcs`` is a name -> content-stream map, looked up via the
        font's ``/Encoding``. The charproc paints in glyph space; the
        glyph -> user transform is ``FontMatrix * text_local`` where
        ``text_local`` already folds in font_size + horizontal scale +
        rise, exactly as the TTF / Type1 path constructs it. The
        non-stroking colour from the page-level graphics state seeds the
        charproc's painting ops (``f`` / ``F`` / ``B`` etc.).
        """
        font_size = self._gs.text_font_size
        h_scale = self._gs.text_horizontal_scaling / 100.0
        font_matrix = font.get_font_matrix()
        # Per the spec, the glyph advance for a Type 3 code at code-point
        # ``c`` is ``W * font_matrix[0]`` user-space units at unit
        # font-size. Pre-compute the multiplier to match the existing
        # ``_show_string`` advance formula (which expects 1/1000-em units):
        #   advance_units = W * font_matrix[0] * 1000
        width_to_advance_units = float(font_matrix[0]) * 1000.0

        encoding = None
        with contextlib.suppress(Exception):
            encoding = font.get_encoding_typed()
        first_char = font.get_first_char()
        if first_char < 0:
            first_char = 0
        widths = font.get_widths()

        for code in data:
            # Glyph name lookup via /Encoding; fall back to .notdef when
            # the font carries no typed encoding (real-world Type 3 fonts
            # always declare one, but we guard for malformed PDFs).
            glyph_name = ".notdef"
            if encoding is not None:
                with contextlib.suppress(Exception):
                    resolved = encoding.get_name(int(code))
                    if resolved is not None:
                        glyph_name = resolved

            charproc = None
            with contextlib.suppress(Exception):
                charproc = font.get_char_proc(glyph_name)

            # Reset the d0/d1 metric overrides; the charproc dispatch will
            # populate them if the glyph stream contains those operators.
            self._type3_d0_wx = None
            self._type3_d1_wx = None
            if charproc is not None:
                self._render_type3_charproc(font, charproc, font_matrix)

            # Advance — /Widths is indexed by (code - FirstChar). When the
            # entry is missing or zero, use 0.0 (the upstream fallback
            # for Type 3 — there's no implicit metric source). ``d0`` /
            # ``d1`` inside the charproc override the /Widths value
            # (PDFBox parity, PDF 32000-1 §9.6.5.3); ``d1`` takes
            # precedence over ``d0`` when both somehow appear.
            advance_units = 0.0
            idx = int(code) - first_char
            if 0 <= idx < len(widths):
                advance_units = widths[idx] * width_to_advance_units
            if self._type3_d1_wx is not None:
                advance_units = self._type3_d1_wx * width_to_advance_units
            elif self._type3_d0_wx is not None:
                advance_units = self._type3_d0_wx * width_to_advance_units

            wordspace = self._gs.text_wordspace if code == 0x20 else 0.0
            tx = (
                (advance_units / 1000.0) * font_size
                + self._gs.text_charspace
                + wordspace
            ) * h_scale
            trans: _Matrix = (1.0, 0.0, 0.0, 1.0, tx, 0.0)
            self._gs.text_matrix = _matmul(trans, self._gs.text_matrix)

    def _render_type3_charproc(
        self,
        font: Any,
        charproc: COSStream,
        font_matrix: list[float],
    ) -> None:
        """Run a Type 3 charproc through the engine's dispatch so its
        path-painting ops drop fills/strokes onto the canvas, scaled by
        the font's /FontMatrix into text space and positioned by the
        active text matrix.

        Restores graphics state, current path, and resources around the
        charproc so it cannot leak its own state into the surrounding
        page. ``d0`` / ``d1`` (glyph metric setters) are silently ignored
        — the lite renderer doesn't model coloured-vs-uncoloured Type 3
        distinctions; the paint always uses the current non-stroking
        colour. Mirrors PDFBox's ``PageDrawer.processType3Stream``.
        """
        font_size = self._gs.text_font_size
        h_scale = self._gs.text_horizontal_scaling / 100.0
        rise = self._gs.text_rise
        # text_local mirrors the matrix used by ``_draw_glyph`` — applied
        # *after* /FontMatrix so glyph-space units flow through font
        # matrix -> 1-em text space -> font-size-scaled user space.
        text_local: _Matrix = (
            font_size * h_scale, 0.0,
            0.0, font_size,
            0.0, rise,
        )
        fm: _Matrix = (
            float(font_matrix[0]),
            float(font_matrix[1]),
            float(font_matrix[2]),
            float(font_matrix[3]),
            float(font_matrix[4]),
            float(font_matrix[5]),
        )
        # glyph_to_user = font_matrix * text_local * text_matrix —
        # composes through ``_matmul``'s "apply m1 first" convention.
        glyph_to_user = _matmul(fm, text_local)
        glyph_to_user = _matmul(glyph_to_user, self._gs.text_matrix)

        # Save graphics state so the charproc can freely emit q/Q,
        # colour-set ops, etc. without escaping the glyph scope.
        self._push_gs()
        # Stash and reset the current path so charproc path-construction
        # ops don't merge into a half-built page path.
        prev_subpaths = self._subpaths
        prev_current_subpath = self._current_subpath
        prev_current_point = self._current_point
        prev_pending_clip = self._pending_clip
        self._subpaths = []
        self._current_subpath = None
        self._current_point = (0.0, 0.0)
        self._pending_clip = None
        # Switch resources to the font's own /Resources for the duration
        # of the charproc — required because charprocs may reference
        # XObjects / patterns / nested fonts via the font's own dict.
        prev_resources = self._resources
        try:
            font_resources = font.get_resources()
            if font_resources is not None:
                self._resources = font_resources

            # Fold the glyph -> user transform onto the CTM and run the
            # charproc bytes through the same dispatch loop a Form
            # XObject uses. Path painting ops will fill with the current
            # non-stroking colour (seeded by the surrounding rg / k / g),
            # so the rectangle / polygon glyph drops onto the page in
            # the right pixels and right colour without further wiring.
            self._gs.ctm = _matmul(glyph_to_user, self._gs.ctm)
            try:
                data = charproc.to_byte_array()
            except Exception as exc:  # noqa: BLE001
                _log.debug("rendering: cannot read Type 3 charproc: %s", exc)
                data = b""
            if data:
                with contextlib.suppress(Exception):
                    self._process_form_bytes(data)
        finally:
            self._resources = prev_resources
            self._subpaths = prev_subpaths
            self._current_subpath = prev_current_subpath
            self._current_point = prev_current_point
            self._pending_clip = prev_pending_clip
            self._pop_gs()


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
    "gs": PDFRenderer._op_set_graphics_state_parameters,
    # colour
    "RG": PDFRenderer._op_set_stroke_rgb,
    "rg": PDFRenderer._op_set_fill_rgb,
    "G": PDFRenderer._op_set_stroke_gray,
    "g": PDFRenderer._op_set_fill_gray,
    "K": PDFRenderer._op_set_stroke_cmyk,
    "k": PDFRenderer._op_set_fill_cmyk,
    # pattern + shading colour selection
    "CS": PDFRenderer._op_set_stroke_color_space,
    "cs": PDFRenderer._op_set_fill_color_space,
    "SCN": PDFRenderer._op_set_stroke_color_n,
    "scn": PDFRenderer._op_set_fill_color_n,
    # PDF 32000-1 §8.6.8 — SC / sc are SCN/scn restricted to non-special
    # colour spaces. Same operand shape (numeric components only), same
    # handler. Missing entries silently dropped every sc / SC in
    # real-world PDFs, leaving the colour at its previous value (default
    # black) — confirmed by wave-1384 audit (e.g. poems-beads + BidiSample
    # whose page-fill rectangle paints stayed black).
    "SC": PDFRenderer._op_set_stroke_color_n,
    "sc": PDFRenderer._op_set_fill_color_n,
    "sh": PDFRenderer._op_shading_fill,
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
    "Tr": PDFRenderer._op_set_text_rendering_mode,
    "Td": PDFRenderer._op_text_move,
    "TD": PDFRenderer._op_text_move_set_leading,
    "Tm": PDFRenderer._op_text_matrix,
    "T*": PDFRenderer._op_text_next_line,
    "Tj": PDFRenderer._op_show_text,
    "TJ": PDFRenderer._op_show_text_array,
    "'": PDFRenderer._op_show_text_line,
    '"': PDFRenderer._op_show_text_line_with_spacing,
    # Type 3 font glyph-metric setters (PDF 32000-1 §9.6.5.3).
    "d0": PDFRenderer._op_type3_d0,
    "d1": PDFRenderer._op_type3_d1,
}


# Painting operators that draw new pixels at the group level; used by
# :meth:`PDFRenderer.process_operator` to fire a knockout snapshot reset
# before each top-level child paint inside a ``/K true`` transparency
# group (PDF spec §11.4.7.3).
_KNOCKOUT_PAINT_OPS: frozenset[str] = frozenset({
    # path painting
    "S", "s", "f", "F", "f*", "B", "B*", "b", "b*",
    # shading + XObject (image / form) painting
    "sh", "Do",
    # inline image
    "BI",
    # text show
    "Tj", "TJ", "'", '"',
})


__all__ = ["PDFRenderer"]
