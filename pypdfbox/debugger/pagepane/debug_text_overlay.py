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
        stripper = _DebugTextStripper(overlay=self)
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


class _DebugTextStripper(PDFTextStripper):
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


def _normalize_rect(
    x0: float, y0: float, x1: float, y1: float
) -> tuple[float, float, float, float]:
    """Order corners so ``x0 <= x1`` and ``y0 <= y1`` (PIL requirement)."""
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)
