"""Overlay showing text-extraction bounding boxes for a single page.

Ported from
``org.apache.pdfbox.debugger.pagepane.DebugTextOverlay`` (PDFBox 3.0).
Upstream subclasses ``PDFTextStripper`` and walks the page through
``writeText`` so that ``writeString`` / ``showGlyph`` fire as side-effect
hooks — each callback draws a debug rectangle onto the supplied
``Graphics2D``. In Python we keep the same subclass shape but plumb a
:class:`PIL.ImageDraw.ImageDraw` instead of ``Graphics2D``; the consumer
(``PagePane``) creates the draw context on the PIL side and hands it in.

Behavioural notes:

- Glyph bounds (the cyan rectangles upstream draws from ``showGlyph``)
  require a fully reified ``getNormalizedPath`` on every vector font, a
  surface our font port does not yet expose. The hook is wired so the
  overlay collects glyph bounds when they are available; otherwise it
  silently skips them (matching upstream's ``return`` on a ``null``
  bbox). See ``CHANGES.md``.
- Upstream applies an ``AffineTransform`` ``scale·flipY·trans`` directly
  to ``Graphics2D``; PIL's draw context only paints in pixel coordinates,
  so this port pre-transforms each rectangle from user-space to image
  pixel space before calling ``draw.rectangle``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pypdfbox.text.pdf_text_stripper import PDFTextStripper

if TYPE_CHECKING:
    from PIL.ImageDraw import ImageDraw as PilImageDraw

    from pypdfbox.pdmodel import PDDocument, PDPage
    from pypdfbox.text.text_position import TextPosition

_LOG = logging.getLogger(__name__)


@dataclass
class DebugRectangle:
    """A single overlay rectangle scheduled for draw.

    ``coords`` is in PIL image pixel space (``x0, y0, x1, y1``). ``color``
    is a PIL-acceptable string ("red", "blue", "green", "cyan") that maps
    1:1 to upstream's ``Color.RED`` / ``Color.BLUE`` / ``Color.GREEN`` /
    ``Color.CYAN`` literals.
    """

    coords: tuple[float, float, float, float]
    color: str
    width: float = 0.5


@dataclass
class _DebugRectCollector:
    """In-memory collector for produced rectangles.

    Decoupling collection from drawing lets headless tests assert that
    the overlay produced *some* rectangles for a synthetic page even
    when no PIL draw context is wired.
    """

    rectangles: list[DebugRectangle] = field(default_factory=list)


class DebugTextOverlay:
    """Draws an overlay showing the locations of text found by
    :class:`PDFTextStripper` and a couple of font-aware heuristics.

    Mirrors the upstream final inner class
    ``DebugTextOverlay.DebugTextStripper`` by routing the hook callbacks
    through a private :class:`PDFTextStripper` subclass.
    """

    def __init__(
        self,
        document: PDDocument,
        page_index: int,
        scale: float,
        show_text_stripper: bool,
        show_text_stripper_beads: bool,
        show_font_bbox: bool,
        show_glyph_bounds: bool,
    ) -> None:
        self._document = document
        self._page_index = page_index
        self._scale = float(scale)
        self._show_text_stripper = bool(show_text_stripper)
        self._show_text_stripper_beads = bool(show_text_stripper_beads)
        self._show_font_bbox = bool(show_font_bbox)
        self._show_glyph_bounds = bool(show_glyph_bounds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_to(self, draw: PilImageDraw | None) -> list[DebugRectangle]:
        """Render the overlay onto ``draw``.

        ``draw`` may be ``None`` — useful in headless tests that only care
        about the *list* of rectangles the overlay produced. Returns the
        collected rectangles in draw order so callers can inspect them.
        """
        page = self._document.get_page(self._page_index)
        stripper = DebugTextStripper(overlay=self)
        rectangles = stripper.strip_page(
            self._document, page, self._page_index, self._scale
        )
        if draw is not None:
            for rect in rectangles:
                try:
                    draw.rectangle(
                        rect.coords, outline=rect.color, width=max(1, int(rect.width))
                    )
                except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                    _LOG.error("ImageDraw.rectangle failed: %s", exc)
        return rectangles

    # ------------------------------------------------------------------
    # Inspection helpers (used by tests)
    # ------------------------------------------------------------------

    @property
    def show_text_stripper(self) -> bool:
        return self._show_text_stripper

    @property
    def show_text_stripper_beads(self) -> bool:
        return self._show_text_stripper_beads

    @property
    def show_font_bbox(self) -> bool:
        return self._show_font_bbox

    @property
    def show_glyph_bounds(self) -> bool:
        return self._show_glyph_bounds


class DebugTextStripper(PDFTextStripper):
    """``PDFTextStripper`` subclass that records rectangles per glyph run.

    Upstream paints directly via the supplied ``Graphics2D``; here we
    collect ``DebugRectangle`` instances so the outer overlay can paint
    them onto a :class:`PIL.ImageDraw.ImageDraw` (or expose them in a
    test).
    """

    def __init__(self, overlay: DebugTextOverlay) -> None:
        super().__init__()
        self._overlay = overlay
        self._collector = _DebugRectCollector()
        self._crop_box_height: float = 0.0
        self._crop_box_lower_left_x: float = 0.0
        self._crop_box_lower_left_y: float = 0.0

    # ---- public ------------------------------------------------------

    def strip_page(
        self,
        document: PDDocument,
        page: PDPage,
        page_index: int,
        scale: float,
    ) -> list[DebugRectangle]:
        """Walk the page through the stripper, collecting rectangles."""
        crop_box = page.get_crop_box()
        self._crop_box_height = float(crop_box.get_height())
        self._crop_box_lower_left_x = float(crop_box.get_lower_left_x())
        self._crop_box_lower_left_y = float(crop_box.get_lower_left_y())

        self.set_start_page(page_index + 1)
        self.set_end_page(page_index + 1)

        # Drive the text-extraction pipeline; we ignore the textual
        # output and rely on the per-glyph hooks for the overlay.
        try:
            self.get_text(document)
        except OSError as exc:
            _LOG.error("text extraction failed: %s", exc)

        # Beads (article threads): drawn in green. Upstream paints them
        # *after* the text walk; we do the same.
        if self._overlay.show_text_stripper_beads:
            self._collect_thread_beads(page)

        return list(self._collector.rectangles)

    # ---- hooks -------------------------------------------------------

    def write_string(  # type: ignore[override]
        self,
        text: str,
        text_positions: Sequence[TextPosition],
        sink: Any,
    ) -> None:
        """Per-run hook fired by the stripper.

        Mirrors upstream's ``writeString(String, List<TextPosition>)``
        override: emits a red rectangle (text-stripper "heuristic height")
        for each ``TextPosition`` when ``show_text_stripper`` is enabled,
        and a blue rectangle (font bbox-based height) when
        ``show_font_bbox`` is enabled.
        """
        for tp in text_positions:
            if self._overlay.show_text_stripper:
                self._collect_text_stripper_rect(tp)
            if self._overlay.show_font_bbox:
                self._collect_font_bbox_rect(tp)
        # Delegate to the default writer so the textual output also flows
        # (matches upstream's ``super.writeString(...)`` chain inside
        # ``writeText`` — though the production overlay throws the output
        # at a dummy ``Writer``, we still want :meth:`process_text_position`
        # to fire for downstream subclasses).
        super().write_string(text, list(text_positions), sink)

    def show_glyph(  # type: ignore[override]
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        """Per-glyph hook fired by the stream engine.

        Upstream draws a cyan glyph-bbox rectangle here. Our path
        depends on ``PDVectorFont.get_normalized_path`` which is not
        universally available in the font port; we attempt a best-effort
        rectangle from the glyph's font bounding box and skip when no
        bbox is reachable.
        """
        super().show_glyph(text_rendering_matrix, font, code, displacement)
        if not self._overlay.show_glyph_bounds or font is None:
            return
        try:
            bbox = font.get_bounding_box()
        except (AttributeError, OSError, ValueError):
            return
        if bbox is None:
            return
        # Place the glyph rectangle at the rendering origin; the
        # text-rendering matrix gives us a translate component on most
        # paths. When the matrix can't be decoded we fall back to (0, 0)
        # which is still useful for tests checking that the hook fired.
        tx = 0.0
        ty = 0.0
        try:
            tx = float(text_rendering_matrix.get_translate_x())
            ty = float(text_rendering_matrix.get_translate_y())
        except (AttributeError, TypeError):
            pass
        # bbox is in glyph-space (1/1000 em on most fonts); scale to a
        # rough pixel rectangle in image-pixel space so the result lands
        # near the glyph.
        try:
            llx = float(bbox.get_lower_left_x()) / 1000.0
            lly = float(bbox.get_lower_left_y()) / 1000.0
            urx = float(bbox.get_upper_right_x()) / 1000.0
            ury = float(bbox.get_upper_right_y()) / 1000.0
        except (AttributeError, TypeError, ValueError):
            return
        # Approximate glyph height in user-space — close enough for an
        # overlay, exact glyph-path projection lives behind the deferred
        # ``getNormalizedPath`` API.
        size = max(1.0, float(displacement_or_one(displacement)) * 1000.0)
        x0 = (tx + llx * size) * self._overlay._scale
        y0 = self._flip_y(ty + ury * size)
        x1 = (tx + urx * size) * self._overlay._scale
        y1 = self._flip_y(ty + lly * size)
        self._collector.rectangles.append(
            DebugRectangle(
                coords=_normalize_rect(x0, y0, x1, y1), color="cyan", width=0.5
            )
        )

    # ---- collection helpers ------------------------------------------

    def _collect_text_stripper_rect(self, tp: TextPosition) -> None:
        # Mirrors upstream:
        #   Rectangle2D.Float(0, 0,
        #     getWidthDirAdj() / textMatrix.scaleX,
        #     getHeightDir()   / textMatrix.scaleY)
        # then transformed by flipY · textMatrix. We do the algebra in
        # one shot — the (x, y) origin becomes ``tp.get_x()``/``tp.get_y()``
        # because the matrix is already applied to those by the
        # underlying engine.
        try:
            x = float(tp.get_x())
            y = float(tp.get_y())
            width = float(tp.get_width_dir_adj())
            height = float(tp.get_height_dir())
        except (AttributeError, TypeError, ValueError):
            return
        if width <= 0 or height <= 0:
            return
        scale = self._overlay._scale
        x0 = x * scale
        y0 = self._flip_y(y)
        x1 = (x + width) * scale
        y1 = self._flip_y(y - height)
        self._collector.rectangles.append(
            DebugRectangle(
                coords=_normalize_rect(x0, y0, x1, y1), color="red", width=0.5
            )
        )

    def _collect_font_bbox_rect(self, tp: TextPosition) -> None:
        try:
            font = tp.get_font()
        except AttributeError:
            return
        if font is None:
            return
        try:
            bbox = font.get_bounding_box()
        except (AttributeError, OSError, ValueError):
            return
        if bbox is None:
            return
        try:
            x = float(tp.get_x())
            y = float(tp.get_y())
            font_size = float(tp.get_font_size())
            llx = float(bbox.get_lower_left_x()) / 1000.0
            lly = float(bbox.get_lower_left_y()) / 1000.0
            urx = float(bbox.get_upper_right_x()) / 1000.0
            ury = float(bbox.get_upper_right_y()) / 1000.0
        except (AttributeError, TypeError, ValueError):
            return
        scale = self._overlay._scale
        x0 = (x + llx * font_size) * scale
        y0 = self._flip_y(y + ury * font_size)
        x1 = (x + urx * font_size) * scale
        y1 = self._flip_y(y + lly * font_size)
        self._collector.rectangles.append(
            DebugRectangle(
                coords=_normalize_rect(x0, y0, x1, y1), color="blue", width=0.5
            )
        )

    def _collect_thread_beads(self, page: PDPage) -> None:
        try:
            beads = page.get_thread_beads()
        except (AttributeError, OSError):
            return
        for bead in beads:
            if bead is None:
                continue
            try:
                rect = bead.get_rectangle()
            except AttributeError:
                continue
            if rect is None:
                continue
            try:
                llx = float(rect.get_lower_left_x())
                lly = float(rect.get_lower_left_y())
                urx = float(rect.get_upper_right_x())
                ury = float(rect.get_upper_right_y())
            except (AttributeError, TypeError, ValueError):
                continue
            # Translate by the crop-box origin and flip y, then scale.
            scale = self._overlay._scale
            tx = self._crop_box_lower_left_x
            ty = self._crop_box_lower_left_y
            x0 = (llx - tx) * scale
            x1 = (urx - tx) * scale
            y0 = self._flip_y(ury - ty)
            y1 = self._flip_y(lly - ty)
            self._collector.rectangles.append(
                DebugRectangle(
                    coords=_normalize_rect(x0, y0, x1, y1), color="green", width=0.5
                )
            )

    # ---- upstream-shape static helpers ------------------------------
    #
    # Upstream Java nests ``transform`` and ``calculateGlyphBounds`` as
    # methods of ``DebugTextOverlay.DebugTextStripper`` (the inner
    # class). The Python port keeps the implementations as module-level
    # functions (re-usable without instantiating the stripper), but also
    # re-exposes them as ``@staticmethod``s on this class for parity-tool
    # detection and upstream-shape spelling. Thin delegations — logic
    # lives in the module-level helpers below.

    @staticmethod
    def transform(
        shape: Sequence[tuple[float, float]],
        at: tuple[float, float, float, float, float, float],
    ) -> list[tuple[float, float]]:
        """Class-surface alias for :func:`transform` (upstream-shape)."""
        return transform(shape, at)

    @staticmethod
    def calculate_glyph_bounds(
        at: tuple[float, float, float, float, float, float],
        font: Any,
        code: int,
        displacement: Any,
    ) -> list[tuple[float, float]] | None:
        """Class-surface alias for :func:`calculate_glyph_bounds`."""
        return calculate_glyph_bounds(at, font, code, displacement)

    # ---- coordinate helpers -----------------------------------------

    def _flip_y(self, y: float) -> float:
        """Flip a user-space y value into PIL image-pixel space.

        PIL's origin is top-left; PDF user space is bottom-left. The
        overlay's image is the crop-box rendered at ``scale``, so the
        height in pixels is ``crop_box_height * scale``.
        """
        return (self._crop_box_height - float(y)) * self._overlay._scale


def displacement_or_one(displacement: Any) -> float:
    """Return ``displacement.get_x()`` if available, else ``1.0``."""
    try:
        return float(displacement.get_x())
    except (AttributeError, TypeError, ValueError):
        return 1.0


# ---------------------------------------------------------------------------
# AffineTransform helpers (upstream ``transform`` / ``calculateGlyphBounds``)
# ---------------------------------------------------------------------------
#
# Upstream stores transforms as ``java.awt.geom.AffineTransform`` and shapes
# as ``java.awt.Shape``. The python port has neither — we represent:
#
#  - an affine transform as the 6-tuple ``(sx, hy, hx, sy, tx, ty)`` returned
#    by :meth:`Matrix.create_affine_transform` (Java ``AffineTransform``
#    constructor order);
#  - a shape as a ``list[tuple[float, float]]`` of corner points (the same
#    representation :meth:`PDRectangle.to_general_path` and
#    :meth:`PDRectangle.transform` already produce).
#
# This keeps :func:`transform` and :func:`calculate_glyph_bounds` aligned
# with the surrounding codebase and lets the helpers compose with
# :class:`pypdfbox.util.matrix.Matrix` without dragging in an AWT shim.


def _concatenate_at(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    """Compose two affine transforms in Java ``AffineTransform.concatenate``
    order — the result first applies ``b`` and then ``a``.

    Each tuple is ``(sx, hy, hx, sy, tx, ty)`` matching
    :meth:`Matrix.create_affine_transform`. Pure helper, kept private.
    """
    a0, a1, a2, a3, a4, a5 = a
    b0, b1, b2, b3, b4, b5 = b
    return (
        a0 * b0 + a2 * b1,
        a1 * b0 + a3 * b1,
        a0 * b2 + a2 * b3,
        a1 * b2 + a3 * b3,
        a0 * b4 + a2 * b5 + a4,
        a1 * b4 + a3 * b5 + a5,
    )


def _bounds2d(points: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Return the axis-aligned bounding box ``(llx, lly, urx, ury)`` of a
    list of ``(x, y)`` points. Mirrors Java's ``Shape.getBounds2D``.
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def transform(
    shape: Sequence[tuple[float, float]],
    at: tuple[float, float, float, float, float, float],
) -> list[tuple[float, float]]:
    """Apply an affine transform ``at`` to ``shape``.

    Mirrors upstream's ``AffineTransform.createTransformedShape(Shape)``
    used throughout ``DebugTextOverlay``. ``at`` is a 6-float tuple in Java
    ``AffineTransform`` order — ``(sx, hy, hx, sy, tx, ty)`` — i.e. the
    same order returned by :meth:`Matrix.create_affine_transform`. ``shape``
    is a sequence of ``(x, y)`` corner points (the representation produced
    by :meth:`PDRectangle.to_general_path` and used everywhere else in the
    pypdfbox port).

    Returns a new list of transformed points; the input is not mutated.
    """
    sx, hy, hx, sy, tx, ty = at
    return [(sx * x + hx * y + tx, hy * x + sy * y + ty) for x, y in shape]


def calculate_glyph_bounds(
    at: tuple[float, float, float, float, float, float],
    font: Any,
    code: int,
    displacement: Any,
) -> list[tuple[float, float]] | None:
    """Compute the transformed glyph bounding box for ``code`` under ``font``.

    Mirrors upstream's ``DebugTextStripper.calculateGlyphBounds(AffineTransform,
    PDFont, int, Vector)``. Parameter order matches upstream exactly.

    ``at`` is the text rendering matrix as a 6-tuple Java AT; ``font`` is
    any object exposing ``get_font_matrix`` (and either the Type3 surface
    via ``get_char_proc`` / ``get_bounding_box`` or the vector-font surface
    via ``get_normalized_path``). Returns the four transformed corners of
    the glyph's axis-aligned bounding box, or ``None`` when the glyph has
    no resolvable bbox.

    **Upstream deviation.** Java reaches for a real ``GeneralPath`` via
    ``PDVectorFont.getNormalizedPath`` to compute a tight visual bbox; the
    pypdfbox font port exposes ``get_normalized_path`` but its return type
    is not uniform across font subclasses (some return a sequence of
    contour tuples, others a Type1c ``GlyphPath``). To stay implementation
    agnostic we accept the loss and fall back to ``font.get_bounding_box``
    when ``get_normalized_path`` is not available — the resulting rect is
    looser than upstream's per-glyph path but matches it for monospace /
    bbox-based outlines, which is what the overlay uses it for.
    """
    if font is None:
        return None

    # at = at · font_matrix    (Java: at.concatenate(font.getFontMatrix()...))
    try:
        fm = list(font.get_font_matrix())
    except (AttributeError, TypeError, ValueError):
        fm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    if len(fm) >= 6:
        at = _concatenate_at(at, (fm[0], fm[1], fm[2], fm[3], fm[4], fm[5]))

    # Type3 fonts have a per-glyph bbox routed through PDType3CharProc.
    from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

    if isinstance(font, PDType3Font):
        try:
            char_proc = font.get_char_proc(code)
        except (AttributeError, TypeError, ValueError):
            return None
        if char_proc is None:
            return None
        try:
            font_bbox = font.get_bounding_box()
            glyph_bbox = char_proc.get_glyph_bbox()
        except (AttributeError, OSError, ValueError):
            return None
        if glyph_bbox is None:
            return None
        # PDFBOX-3850: clamp the glyph bbox to the font bbox so out-of-range
        # entries don't blow up the overlay.
        if font_bbox is not None:
            try:
                glyph_bbox.set_lower_left_x(
                    max(font_bbox.get_lower_left_x(), glyph_bbox.get_lower_left_x())
                )
                glyph_bbox.set_lower_left_y(
                    max(font_bbox.get_lower_left_y(), glyph_bbox.get_lower_left_y())
                )
                glyph_bbox.set_upper_right_x(
                    min(font_bbox.get_upper_right_x(), glyph_bbox.get_upper_right_x())
                )
                glyph_bbox.set_upper_right_y(
                    min(font_bbox.get_upper_right_y(), glyph_bbox.get_upper_right_y())
                )
            except (AttributeError, TypeError, ValueError):
                pass
        rect_points = glyph_bbox.to_general_path()
    else:
        # Non-Type3 path: prefer a real glyph path when the font exposes
        # ``get_normalized_path`` and the result is a non-empty point list,
        # otherwise fall back to the font's bounding box. See the docstring
        # for the upstream-deviation rationale.
        path_points: Sequence[tuple[float, float]] | None = None
        get_norm = getattr(font, "get_normalized_path", None)
        if callable(get_norm):
            try:
                raw_path = get_norm(code)
            except (AttributeError, OSError, ValueError, TypeError):
                raw_path = None
            if raw_path is not None:
                # Accept either a flat list of 2-tuples or a sequence of
                # ``(op, *args)`` contour tuples — extract just the (x, y)
                # pairs we can use for a bbox.
                pts: list[tuple[float, float]] = []
                for item in raw_path:
                    if (
                        isinstance(item, tuple)
                        and len(item) == 2
                        and isinstance(item[0], (int, float))
                    ):
                        pts.append((float(item[0]), float(item[1])))
                if pts:
                    path_points = pts

        if path_points is None:
            try:
                bbox = font.get_bounding_box()
            except (AttributeError, OSError, ValueError):
                return None
            if bbox is None:
                return None
            try:
                path_points = [
                    (bbox.get_lower_left_x(), bbox.get_lower_left_y()),
                    (bbox.get_upper_right_x(), bbox.get_lower_left_y()),
                    (bbox.get_upper_right_x(), bbox.get_upper_right_y()),
                    (bbox.get_lower_left_x(), bbox.get_upper_right_y()),
                ]
            except (AttributeError, TypeError, ValueError):
                return None

        # Stretch non-embedded glyph if its advance width differs from
        # what's recorded in the PDF (mirrors upstream PDFBOX-3450 fix).
        try:
            stretch_needed = (
                not font.is_embedded()
                and not font.is_vertical()
                and not font.is_standard14()
                and font.has_explicit_width(code)
            )
        except (AttributeError, TypeError, ValueError):
            stretch_needed = False
        if stretch_needed:
            try:
                font_width = float(font.get_width_from_font(code))
                disp_x = float(displacement.get_x()) if displacement is not None else 0.0
                pdf_width = disp_x * 1000.0
                if font_width > 0 and abs(font_width - pdf_width) > 0.0001:
                    scale_x = pdf_width / font_width
                    at = _concatenate_at(at, (scale_x, 0.0, 0.0, 1.0, 0.0, 0.0))
            except (AttributeError, TypeError, ValueError, ZeroDivisionError):
                pass

        # Java computes the bbox of the path then transforms that rect;
        # we do the same so the result is an axis-aligned 4-corner shape.
        llx, lly, urx, ury = _bounds2d(path_points)
        rect_points = [(llx, lly), (urx, lly), (urx, ury), (llx, ury)]

    return transform(rect_points, at)


def _normalize_rect(
    x0: float, y0: float, x1: float, y1: float
) -> tuple[float, float, float, float]:
    """Order corners so ``x0 <= x1`` and ``y0 <= y1`` (PIL requirement)."""
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)
