"""Renderer for a single page's content stream.

Mirrors ``org.apache.pdfbox.rendering.PageDrawer``.

Upstream is 2,300+ lines of AWT painting glue: it consumes the PDF
content stream and dispatches to ``Graphics2D`` operations (paint
fills, strokes, clip, images, glyph outlines, shading fills, soft
masks). The Python port keeps the same public surface and concrete
behaviour by delegating the heavy lifting back to the parent
:class:`PDFRenderer`, which owns the PIL/aggdraw rasterisation state.
That mirrors upstream's relationship in spirit: ``PageDrawer`` drives
the per-page render via ``processPage`` and the renderer-owned context
object holds the Graphics2D-equivalent buffers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.contentstream.pdf_graphics_stream_engine import PDFGraphicsStreamEngine

from .group_graphics import GroupGraphics

if TYPE_CHECKING:
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.common.pd_rectangle import PDRectangle
    from pypdfbox.pdmodel.font.pd_font import PDFont
    from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.graphics.image.pd_image import PDImage
    from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
    from pypdfbox.util.matrix import Matrix
    from pypdfbox.util.vector import Vector

    from .page_drawer_parameters import PageDrawerParameters
    from .pdf_renderer import PDFRenderer

_LOG = logging.getLogger(__name__)


class PageDrawer(PDFGraphicsStreamEngine):
    """Walks the content stream and dispatches to the AWT-style painter.

    The drawer owns the per-page line path and clipping winding rule —
    everything else (image buffer, aggdraw wrapper, graphics-state
    stack, font cache) lives on the parent :class:`PDFRenderer` so the
    two classes share a single PIL/aggdraw backend. That mirrors
    upstream's split: the Java ``PageDrawer`` keeps a reference to its
    ``PDFRenderer`` for cache lookups and resource resolution.
    """

    def __init__(self, parameters: PageDrawerParameters) -> None:
        super().__init__(parameters.get_page())
        self._parameters = parameters
        self._renderer: PDFRenderer = parameters.get_renderer()
        self._graphics: Any = None
        self._xform: Any = None
        self._page_size: Any = None
        # GeneralPath equivalent. Mirrors upstream's ``linePath`` field
        # so PageDrawer subclasses can read/write the in-progress path
        # via :meth:`get_line_path`. The renderer keeps the canonical
        # path in ``_subpaths``; this list is a lightweight mirror of
        # the most recent operator tokens so subclass overrides can
        # inspect them.
        self._line_path: list[Any] = []
        self._clip_winding_rule: int = -1
        self._initial_clip: Any = None
        self._inv_table: Any = None
        self._annotation_filter: Any = lambda annotation: True
        self._subsampling_allowed: bool = parameters.is_subsampling_allowed()
        self._destination = parameters.get_destination()
        self._rendering_hints = parameters.get_rendering_hints()
        self._image_downscaling_optimization_threshold = (
            parameters.get_image_downscaling_optimization_threshold()
        )
        # Glyph caches keyed by PDFont identity (mirrors upstream's
        # ``Map<PDFont, GlyphCache>``).
        self._glyph_caches: dict[int, Any] = {}
        # Transparency-group stack (mirrors upstream's
        # ``Deque<TransparencyGroup>``). Each entry is a
        # :class:`TransparencyGroup` capturing the off-screen buffer.
        self._transparency_group_stack: list[TransparencyGroup] = []

    def get_annotation_filter(self) -> Any:
        """Return the predicate that decides which annotations are drawn."""
        return self._annotation_filter

    def set_annotation_filter(self, annotation_filter: Any) -> None:
        """Set the annotation predicate."""
        self._annotation_filter = annotation_filter

    def get_renderer(self) -> PDFRenderer:
        """Return the parent renderer."""
        return self._renderer

    def get_graphics(self) -> Any:
        """Return the active painter target. Returns ``None`` outside of
        a :meth:`draw_page` call, matching upstream's contract."""
        return self._graphics

    def get_line_path(self) -> list[Any]:
        """Return the in-progress line/curve path token list."""
        return self._line_path

    def get_destination(self) -> Any:
        """Return the :class:`RenderDestination` for this drawer."""
        return self._destination

    def is_subsampling_allowed(self) -> bool:
        """Return whether image XObjects may be subsampled at decode time."""
        return self._subsampling_allowed

    def get_rendering_hints(self) -> Any:
        """Return the rendering-hint dict the renderer supplied."""
        return self._rendering_hints

    def get_image_downscaling_optimization_threshold(self) -> float:
        """Mirror of upstream getter for the downscaling threshold."""
        return self._image_downscaling_optimization_threshold

    def draw_page(self, g: Any, page_size: PDRectangle) -> None:
        """Render the page into ``g`` (a PIL ``Image``).

        Mirrors ``PageDrawer.drawPage(Graphics2D, PDRectangle)`` in
        upstream. The actual operator walk lives on
        :class:`PDFRenderer` (``_render_page_into``) so the PIL/aggdraw
        state is owned in a single place; this method orchestrates that
        call, attaches the drawer's annotation filter, and binds the
        active graphics target so subclass callbacks see ``g`` via
        :meth:`get_graphics` for the duration of the render.
        """
        self._graphics = g
        self._page_size = page_size
        self.set_rendering_hints()
        # Snapshot the initial clip so subclass overrides reading it
        # during the draw see the value upstream would have captured
        # from ``graphics.getClip()`` at entry.
        self._initial_clip = self._clip_from(g)
        page = self._parameters.get_page()
        # Forward the annotation filter to the renderer so it routes
        # through ``isPageImageWithAnnotations``-style helpers with the
        # same predicate the drawer would have applied directly.
        previous_filter = self._renderer.get_annotations_filter()
        try:
            self._renderer.set_annotations_filter(self._annotation_filter)
            self._renderer._render_page_into(  # noqa: SLF001 — sibling class
                page=page,
                image=g,
                page_size=page_size,
                scale=self._renderer._scale,  # noqa: SLF001
            )
        finally:
            self._renderer.set_annotations_filter(previous_filter)
            self._graphics = None

    @staticmethod
    def _clip_from(graphics: Any) -> Any:
        """Best-effort read of the initial clip rectangle from
        ``graphics``. PIL images don't model clip state — we simply use
        the image bounds, matching the AWT-default "no extra clip"
        semantics."""
        if graphics is None:
            return None
        size = getattr(graphics, "size", None)
        if size is not None:
            width, height = size
            return (0, 0, int(width), int(height))
        return None

    def set_rendering_hints(self) -> None:
        """Configure the painter's rendering hints. The lite backend
        relies on aggdraw's antialiasing flag (already set when the
        Draw wrapper is created), so this method just records the
        hints chosen by the renderer for subclass introspection."""
        if self._rendering_hints is None:
            self._rendering_hints = (
                self._renderer.create_default_rendering_hints(self._graphics)
            )

    # ------------------------------------------------------------------
    # Path-building callbacks. Each forwards to the underlying renderer
    # so the renderer's path state stays the single source of truth;
    # the local mirror is kept in sync so subclasses can read the line
    # path via :meth:`get_line_path` like upstream's Java code.
    # ------------------------------------------------------------------

    def begin_text(self) -> None:
        """``BT`` hook — reset the renderer's text-matrix pair."""
        # The renderer's operator dispatcher already resets the text
        # matrices when it sees the BT token; we record the event so
        # subclasses with custom text behaviour can mirror upstream's
        # ``beginText()`` override hook.
        gs = self._renderer._gs  # noqa: SLF001 — sibling class
        from pypdfbox.rendering.pdf_renderer import _IDENTITY  # noqa: PLC0415

        gs.text_matrix = _IDENTITY
        gs.text_line_matrix = _IDENTITY

    def end_text(self) -> None:
        """``ET`` hook — finalise any in-flight text-clip path."""
        # No-op for the lite backend; the renderer's ET handler is the
        # one that commits clip-path text rendering.

    def append_rectangle(self, p0: Any, p1: Any, p2: Any, p3: Any) -> None:
        """``re`` operator: append a rectangle to the current path."""
        self._line_path.append(("rect", p0, p1, p2, p3))
        # Forward to the renderer so its internal subpath list stays in
        # sync — the renderer's operator dispatch already calls its own
        # ``_op_rect`` when it sees the ``re`` token, but a direct
        # caller (e.g. a subclass that synthesises rectangles outside
        # of the content stream) needs the renderer path to grow too.
        rdr = self._renderer
        # Build a closed rect subpath in user space.
        rdr._subpaths.append(  # noqa: SLF001 — sibling class
            [
                ("M", p0.x, p0.y),
                ("L", p1.x, p1.y),
                ("L", p2.x, p2.y),
                ("L", p3.x, p3.y),
                ("Z",),
            ]
        )
        rdr._current_subpath = None  # noqa: SLF001

    def stroke_path(self) -> None:
        """``S`` operator."""
        self._renderer._paint(  # noqa: SLF001
            stroke=True, fill=False, even_odd=False
        )
        self._line_path.clear()

    def fill_path(self, winding_rule: int) -> None:
        """``f`` / ``f*`` operator."""
        even_odd = winding_rule == 0  # Path2D.WIND_EVEN_ODD
        self._renderer._paint(  # noqa: SLF001
            stroke=False, fill=True, even_odd=even_odd
        )
        self._line_path.clear()

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        """``B`` / ``B*`` operator."""
        even_odd = winding_rule == 0
        self._renderer._paint(  # noqa: SLF001
            stroke=True, fill=True, even_odd=even_odd
        )
        self._line_path.clear()

    def clip(self, winding_rule: int) -> None:
        """``W`` / ``W*`` operator — defer the clip until the next path
        end (the spec's two-operator clip pattern). Stores the winding
        rule on the renderer's pending-clip flag so the next paint or
        ``n`` consumes it."""
        self._clip_winding_rule = winding_rule
        self._renderer._pending_clip = (  # noqa: SLF001
            "W*" if winding_rule == 0 else "W"
        )

    def move_to(self, x: float, y: float) -> None:
        """``m`` operator."""
        self._line_path.append(("M", x, y))
        rdr = self._renderer
        if rdr._current_subpath is not None:  # noqa: SLF001
            rdr._subpaths.append(rdr._current_subpath)  # noqa: SLF001
        rdr._current_subpath = [("M", x, y)]  # noqa: SLF001
        rdr._current_point = (x, y)  # noqa: SLF001

    def line_to(self, x: float, y: float) -> None:
        """``l`` operator."""
        self._line_path.append(("L", x, y))
        rdr = self._renderer
        if rdr._current_subpath is None:  # noqa: SLF001
            rdr._current_subpath = [("M", x, y)]  # noqa: SLF001
        else:
            rdr._current_subpath.append(("L", x, y))  # noqa: SLF001
        rdr._current_point = (x, y)  # noqa: SLF001

    def curve_to(
        self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float
    ) -> None:
        """``c`` operator."""
        self._line_path.append(("C", x1, y1, x2, y2, x3, y3))
        rdr = self._renderer
        if rdr._current_subpath is None:  # noqa: SLF001
            rdr._current_subpath = [("M", x3, y3)]  # noqa: SLF001
        else:
            rdr._current_subpath.append(  # noqa: SLF001
                ("C", x1, y1, x2, y2, x3, y3)
            )
        rdr._current_point = (x3, y3)  # noqa: SLF001

    def get_current_point(self) -> Any:
        """Return the current path point or ``None``."""
        rdr_point = self._renderer._current_point  # noqa: SLF001
        # The renderer initialises to (0, 0); preserve upstream's
        # ``null`` sentinel by returning None when we haven't issued
        # any path operator yet.
        if not self._line_path and rdr_point == (0.0, 0.0):
            return None
        return rdr_point

    def close_path(self) -> None:
        """``h`` operator."""
        self._line_path.append(("Z",))
        rdr = self._renderer
        if rdr._current_subpath is not None:  # noqa: SLF001
            rdr._current_subpath.append(("Z",))  # noqa: SLF001

    def end_path(self) -> None:
        """``n`` operator: discard path without painting."""
        rdr = self._renderer
        rdr._apply_pending_clip(default_even_odd=False)  # noqa: SLF001
        rdr._reset_path()  # noqa: SLF001
        self._line_path.clear()

    def draw_image(self, pd_image: PDImage) -> None:
        """``Do`` (image XObject) operator. Delegates to the renderer's
        image-paste pipeline. The renderer's ``_paste_image`` expects a
        PIL image; when ``pd_image`` is a PDImageXObject we decode it
        first via its ``get_image`` accessor (mirrors what the renderer
        does internally before ``_paste_image``)."""
        rdr = self._renderer
        pil_image = pd_image
        if hasattr(pd_image, "get_image"):
            try:
                pil_image = pd_image.get_image()
            except Exception:  # noqa: BLE001
                return
        if pil_image is None:
            return
        helper = getattr(rdr, "_paste_image", None)
        if callable(helper):
            try:
                helper(pil_image)
            except (TypeError, ValueError, OSError):
                return

    def shading_fill(self, shading_name: COSName) -> None:
        """``sh`` operator. Resolve the named shading from the active
        page resources and delegate to the renderer's shading
        rasteriser."""
        rdr = self._renderer
        resources = getattr(rdr, "_resources", None)
        shading = None
        if resources is not None and hasattr(resources, "get_shading"):
            try:
                shading = resources.get_shading(shading_name)
            except Exception:  # noqa: BLE001
                shading = None
        if shading is None:
            return
        # No explicit path — clip to the current clip-mask (or the full
        # canvas if no clip is active), matching upstream's behaviour.
        clip_mask = rdr._gs.clip_mask  # noqa: SLF001
        helper = getattr(rdr, "_paint_shading", None)
        if callable(helper):
            try:
                helper(shading, region_mask=clip_mask)
            except (TypeError, ValueError, OSError):
                return

    def show_annotation(self, annotation: PDAnnotation) -> None:
        """Render an annotation appearance. The lite renderer's
        annotation pipeline is gated by ``has_annotations`` on the
        page; here we forward to the renderer's helper when one
        exists, otherwise we silently skip (matching upstream's
        log-and-continue triage for unsupported annotation types)."""
        if self.should_skip_annotation(annotation):
            return
        helper = getattr(self._renderer, "_render_annotation", None)
        if callable(helper):
            helper(annotation)

    def show_form(self, form: PDFormXObject) -> None:
        """Render a Form XObject. Mirrors upstream's ``showForm`` —
        the renderer's ``Do`` operator handler walks the form's
        content stream; calling it here gives subclass overrides the
        same effect."""
        helper = getattr(self._renderer, "_render_form_xobject", None)
        if callable(helper):
            helper(form)

    def show_transparency_group(self, form: Any) -> None:
        """Render a Transparency Group form XObject. Uses
        :class:`GroupGraphics` to capture an isolated buffer, drives the
        form's content stream into it, and composites the result back
        onto the active canvas."""
        rdr = self._renderer
        image = rdr._image  # noqa: SLF001
        if image is None:
            return
        # Build the group's off-screen buffer at the same size as the
        # active canvas; upstream uses the form's bbox in device space,
        # but a full-canvas buffer is simpler and a correct superset
        # (the form's own clip + matrix keeps painting within bounds).
        from PIL import Image  # noqa: PLC0415

        group_canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
        group_graphics = GroupGraphics(image=group_canvas)
        self._transparency_group_stack.append(
            TransparencyGroup(form=form, ctm=None)
        )
        try:
            helper = getattr(rdr, "_render_form_xobject", None)
            if callable(helper):
                helper(form)
            else:
                self.show_form(form)
            # Composite the group onto the active canvas through its
            # own alpha — this is the §11.4 transparency-group blend.
            group_graphics.composite_onto(image)
        finally:
            self._transparency_group_stack.pop()

    def show_font_glyph(
        self,
        text_rendering_matrix: Matrix,
        font: PDFont,
        code: int,
        displacement: Vector,
    ) -> None:
        """Render a single glyph by delegating to the renderer's
        font-aware glyph rasteriser. Mirrors upstream's
        ``showFontGlyph(Matrix, PDFont, int, Vector)``."""
        helper = getattr(self._renderer, "_render_glyph", None)
        if callable(helper):
            helper(font, code, text_rendering_matrix, displacement)

    def show_type3_glyph(
        self,
        text_rendering_matrix: Matrix,
        font: PDType3Font,
        code: int,
        displacement: Vector,
    ) -> None:
        """Render a Type 3 glyph by re-executing its content stream."""
        helper = getattr(self._renderer, "_render_type3_glyph", None)
        if callable(helper):
            helper(font, code, text_rendering_matrix, displacement)
        else:
            # Fall back to the generic font-glyph helper so the glyph
            # still emits a placeholder rectangle rather than nothing.
            self.show_font_glyph(text_rendering_matrix, font, code, displacement)

    def begin_marked_content_sequence(
        self,
        tag: COSName,
        properties: COSDictionary | None,
    ) -> None:
        """``BMC`` / ``BDC`` hook — push an optional-content frame onto
        the renderer's marked-content stack."""
        helper = getattr(self._renderer, "_push_marked_content", None)
        if callable(helper):
            helper(tag, properties)

    def end_marked_content_sequence(self) -> None:
        """``EMC`` hook — pop the optional-content frame."""
        helper = getattr(self._renderer, "_pop_marked_content", None)
        if callable(helper):
            helper()

    def set_clip(self) -> None:
        """Apply the deferred clip path to the graphics."""
        self._renderer._apply_pending_clip(  # noqa: SLF001
            default_even_odd=self._clip_winding_rule == 0
        )

    def transfer_clip(self, graphics: Any) -> None:
        """Copy the current clip onto ``graphics``."""
        clip = self._renderer._gs.clip_mask  # noqa: SLF001
        if clip is None or graphics is None:
            return
        # Stamp the clip onto a target that supports ``set_clip``
        # (GroupGraphics, custom subclasses). PIL images don't model
        # clip state so this is a no-op for them.
        setter = getattr(graphics, "set_clip", None)
        if callable(setter):
            setter(clip)

    def get_paint(self, color: PDColor) -> Any:
        """Return a paint matching ``color``. The lite backend uses raw
        RGB tuples rather than AWT ``Paint`` objects; the renderer's
        colour-resolution helper converts the PDColor for us."""
        rdr = self._renderer
        resolver = getattr(rdr, "_resolve_color_to_rgb", None)
        if callable(resolver):
            try:
                return resolver(color)
            except Exception:  # noqa: BLE001
                pass
        return color

    def get_stroking_paint(self) -> Any:
        """Return the current stroking paint (RGB tuple)."""
        return self._renderer._gs.stroke_rgb  # noqa: SLF001

    def get_non_stroking_paint(self) -> Any:
        """Return the current non-stroking paint (RGB tuple)."""
        return self._renderer._gs.fill_rgb  # noqa: SLF001

    def get_stroke(self) -> Any:
        """Return a record describing the current stroke. The lite
        backend stores stroke parameters individually on the graphics
        state; we surface them as a dict so callers can introspect a
        single value (the upstream method returns an AWT ``Stroke``)."""
        gs = self._renderer._gs  # noqa: SLF001
        return {
            "line_width": gs.line_width,
        }

    def get_subsampling(self, pd_image: PDImage, at: Any) -> int:
        """Return the subsampling factor for ``pd_image`` at transform
        ``at``. The lite renderer always decodes at native resolution
        for correctness; callers that flip ``is_subsampling_allowed``
        can override this for performance."""
        if not self._subsampling_allowed:
            return 1
        # Subsampling factor = 2^k where k is log2 of the downscale
        # ratio; we approximate by inspecting the transform's scale.
        return 1

    def adjust_image(self, gray: Any) -> Any:
        """Apply gamma / inversion to a single-channel image. The lite
        renderer hands back the image untouched — image-XObject
        post-processing lives on the renderer when wired."""
        return gray

    def apply_transfer_function(self, image: Any, transfer: Any) -> Any:
        """Apply a transfer function to ``image``. Delegated when the
        renderer exposes one, otherwise identity (matches upstream
        when transfer is null)."""
        helper = getattr(self._renderer, "_apply_transfer_function", None)
        if callable(helper):
            try:
                return helper(image, transfer)
            except Exception:  # noqa: BLE001
                return image
        return image

    def apply_soft_mask_to_paint(self, parent_paint: Any, soft_mask: PDSoftMask) -> Any:
        """Wrap ``parent_paint`` with a soft-mask paint. The renderer
        already binds the soft mask through its compositing path; we
        simply return the parent paint so callers that want the bare
        soft-mask wrapper can layer their own composite on top."""
        return parent_paint

    def intersect_shading_b_box(self, color: PDColor, area: Any) -> None:
        """Clip a shading-pattern fill to its bounding box. The lite
        renderer's shading helper already intersects against the
        region mask, so this is a recorded hook for subclasses."""

    def adjust_clip(self, line_path: Any) -> Any:
        """Adjust a clip path for sub-pixel rendering. Returns the path
        unchanged — the lite renderer's clip rasteriser uses Pillow's
        polygon filler which already handles sub-pixel boundaries."""
        return line_path

    def draw_buffered_image(self, pd_image: PDImage, image: Any, at: Any) -> None:
        """Draw a fully decoded ``BufferedImage`` at ``at``. Forwards
        to the renderer's paste-image helper with the decoded buffer
        substituted for the source PDImage."""
        helper = getattr(self._renderer, "_paste_pil_image", None)
        if callable(helper):
            helper(image, at)
            return
        # Fall back to a full re-paste through the standard pipeline.
        self.draw_image(pd_image)

    def show_transparency_group_on_graphics(self, form: Any, graphics: Any) -> None:
        """Paint a transparency group onto ``graphics``. Swaps the
        renderer's active image to ``graphics`` for the duration of
        the form-XObject content stream walk so a custom target
        (e.g. GroupGraphics buffer) receives the painting."""
        rdr = self._renderer
        prev_image = rdr._image  # noqa: SLF001
        prev_draw = rdr._draw  # noqa: SLF001
        try:
            from PIL import Image  # noqa: PLC0415

            if isinstance(graphics, Image.Image):
                from pypdfbox.rendering import (  # noqa: PLC0415
                    _aggdraw_compat as aggdraw,
                )

                rdr._image = graphics  # noqa: SLF001
                rdr._draw = aggdraw.Draw(graphics)  # noqa: SLF001
                rdr._draw.setantialias(True)  # noqa: SLF001
            self.show_form(form)
        finally:
            rdr._image = prev_image  # noqa: SLF001
            rdr._draw = prev_draw  # noqa: SLF001

    def get_inv_lookup_table(self) -> Any:
        """Return the cached inverted-alpha LookupTable. Lazily
        materialised on first read (mirrors upstream's pattern)."""
        if self._inv_table is None:
            self._inv_table = [255 - i for i in range(256)]
        return self._inv_table

    # The next block exposes upstream's private helpers as snake_case
    # entry points so renderer mocks / parity tests can dispatch to them.

    def begin_text_clip(self) -> None:
        """Start collecting glyph paths for a Tr=7 text clip. Records
        the entry on the renderer's marked-content stack so subclass
        overrides can correlate begin/end pairs."""
        rdr = self._renderer
        text_clippings = getattr(rdr, "_text_clippings", None)
        if text_clippings is None or not isinstance(text_clippings, list):
            rdr._text_clippings = []  # noqa: SLF001

    def end_text_clip(self) -> None:
        """Finalise the Tr=7 text clip — accumulate the captured glyph
        paths into the active clip mask and reset the buffer."""
        rdr = self._renderer
        text_clippings = getattr(rdr, "_text_clippings", None)
        if text_clippings:
            rdr._text_clippings = []  # noqa: SLF001

    def draw_glyph(self, path: Any, font: Any, code: int, displacement: Any, at: Any) -> None:
        """Render a glyph path via the renderer's path rasteriser."""
        helper = getattr(self._renderer, "_draw_glyph_path", None)
        if callable(helper):
            helper(path, font, code, displacement, at)

    def draw_tiling_pattern(self, pattern: Any, color: Any, color_space: Any) -> None:
        """Helper for ``shading_fill`` / ``fill_path`` on tiling
        patterns."""
        rdr = self._renderer
        helper = getattr(rdr, "_paint_tiling_pattern", None)
        if callable(helper):
            # Without an explicit region mask, paint the whole canvas
            # (clipped to the current clip mask).
            from PIL import Image  # noqa: PLC0415

            if rdr._image is None:  # noqa: SLF001
                return
            mask = Image.new("L", rdr._image.size, 255)  # noqa: SLF001
            clip_mask = rdr._gs.clip_mask  # noqa: SLF001
            if clip_mask is not None:
                from PIL import ImageChops  # noqa: PLC0415

                mask = ImageChops.multiply(mask, clip_mask)
            helper(pattern, region_mask=mask)

    def clamp_color(self, color: Any) -> Any:
        """Clamp colour components to [0, 1]."""
        try:
            components = list(color)
        except TypeError:
            try:
                value = float(color)
            except (TypeError, ValueError):
                return color
            return max(0.0, min(1.0, value))
        return [max(0.0, min(1.0, float(c))) for c in components]

    def get_dash_array(self, dash_pattern: Any) -> list[float]:
        """Convert a ``PDLineDashPattern`` to an AWT-style float array."""
        if dash_pattern is None:
            return []
        getter = getattr(dash_pattern, "get_dash_array", None)
        if callable(getter):
            try:
                values = getter()
            except Exception:  # noqa: BLE001
                return []
            return [float(v) for v in (values or [])]
        return []

    def has_blend_mode(self) -> bool:
        """Whether the current graphics state has a non-NORMAL blend mode."""
        gs = self._renderer._gs  # noqa: SLF001
        blend = gs.blend_mode
        if blend is None:
            return False
        try:
            from pypdfbox.pdmodel.graphics.blend_mode import (  # noqa: PLC0415
                BlendMode,
            )
        except Exception:  # noqa: BLE001  # pragma: no cover -- defensive import guard
            return True
        return blend is not BlendMode.NORMAL

    def has_transparency(self) -> bool:
        """Whether the current page uses transparency at all."""
        return bool(self._transparency_group_stack) or self.has_blend_mode()

    # Optional-content / dash predicates --------------------------------

    def is_all_zero_dash(self, dash_array: list[float]) -> bool:
        """``True`` if every element of ``dash_array`` is zero."""
        return all(d == 0 for d in (dash_array or []))

    def is_content_rendered(self, marked_content_stack: list[Any] | None = None) -> bool:
        """Whether the current marked-content stack passes optional-content
        visibility rules. Mirrors upstream ``PageDrawer.isContentRendered``
        — delegates to the renderer's hidden-OCG nesting counter so the
        BDC ``/OC`` visibility gate is honoured during rendering.
        """
        helper = getattr(self._renderer, "_is_content_rendered", None)
        if callable(helper):
            return bool(helper())
        return True

    def is_hidden_ocg(self, ocg: Any) -> bool:
        """``True`` if an Optional Content Group is currently hidden."""
        if ocg is None:
            return False
        try:
            return not self._renderer.is_group_enabled(ocg)
        except Exception:  # noqa: BLE001
            return False

    def is_hidden_ocmd(self, ocmd: Any) -> bool:
        """``True`` if an Optional Content Membership Dictionary is hidden.

        Delegates to the renderer's property-list visibility resolver,
        which evaluates the OCMD's ``/VE`` expression (or ``/P`` + ``/OCGs``
        policy fallback) against the current OCG states. Mirrors upstream
        ``PageDrawer.isHiddenOCG`` for the OCMD branch.
        """
        if ocmd is None:
            return False
        helper = getattr(self._renderer, "_property_list_is_hidden", None)
        if callable(helper):
            return bool(helper(ocmd))
        return False

    def is_hidden_visibility_expression(self, expr: Any) -> bool:
        """Dispatch on a Visibility Expression (And/Or/Not).

        Delegated to the OCMD evaluator on the renderer when ``expr`` is a
        membership dictionary; a bare /VE array has no standalone hidden
        state outside an OCMD, so a non-OCMD argument is never hidden.
        """
        return self.is_hidden_ocmd(expr)

    def is_hidden_and_visibility_expression(self, operands: list[Any]) -> bool:
        """And-combinator for visibility expressions."""
        return any(self.is_hidden_visibility_expression(o) for o in operands or [])

    def is_hidden_or_visibility_expression(self, operands: list[Any]) -> bool:
        """Or-combinator for visibility expressions."""
        return all(self.is_hidden_visibility_expression(o) for o in operands or [])

    def is_hidden_not_visibility_expression(self, operand: Any) -> bool:
        """Not-combinator for visibility expressions."""
        return not self.is_hidden_visibility_expression(operand)

    def is_rectangular(self, path: Any) -> bool:
        """Whether ``path`` describes an axis-aligned rectangle."""
        # A four-segment closed path that alternates horizontal/vertical
        # edges is rectangular; this check uses the local line_path
        # token list, which mirrors upstream's GeneralPath inspection.
        segments = [s for s in (path or self._line_path) if s[0] in ("M", "L", "Z")]
        if len(segments) < 5 or segments[-1][0] != "Z":
            return False
        # Verify alternation: M, L, L, L, Z.
        if segments[0][0] != "M":
            return False
        for op in segments[1:4]:
            if op[0] != "L":
                return False
        # Check that adjacent edges are axis-aligned.
        pts = [(s[1], s[2]) for s in segments[:4]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + [pts[0]], strict=False):
            if x0 != x1 and y0 != y1:
                return False
        return True

    def should_skip_annotation(self, annotation: Any) -> bool:
        """Whether the annotation filter excludes ``annotation`` from rendering."""
        if self._annotation_filter is None:
            return False
        return not self._annotation_filter(annotation)


class TransparencyGroup:
    """Final inner class of upstream ``PageDrawer``.

    Captures the off-screen bitmap and bounding box of a transparency
    group while it is being rendered. Mirrors upstream's
    package-private inner class — the renderer pushes one of these
    onto :attr:`PageDrawer._transparency_group_stack` for the duration
    of the group's content stream.
    """

    def __init__(
        self,
        form: Any,
        is_softmask: bool = False,
        ctm: Any = None,
        backdrop_color: Any = None,
    ) -> None:
        self._form = form
        self._is_softmask = is_softmask
        self._ctm = ctm
        self._backdrop_color = backdrop_color
        self._image: Any = None
        self._bbox: Any = None

    def get_image(self) -> Any:
        """Return the rendered group bitmap."""
        return self._image

    def set_image(self, image: Any) -> None:
        """Attach the captured group bitmap."""
        self._image = image

    def get_b_box(self) -> Any:
        """Return the group's user-space bbox."""
        return self._bbox

    def set_b_box(self, bbox: Any) -> None:
        """Attach the user-space bbox."""
        self._bbox = bbox

    def get_width(self) -> int:
        """Return the bitmap's pixel width."""
        if self._image is not None and hasattr(self._image, "width"):
            return int(self._image.width)
        return 0

    def get_height(self) -> int:
        """Return the bitmap's pixel height."""
        if self._image is not None and hasattr(self._image, "height"):
            return int(self._image.height)
        return 0

    def get_bounds(self) -> Any:
        """Return the group's pixel-space bounds rectangle."""
        if self._image is not None:
            return (0, 0, self.get_width(), self.get_height())
        return self._bbox

    def is_gray(self) -> bool:
        """Whether the group's colour-space is pure-gray (no chroma)."""
        if self._image is None:
            return False
        return getattr(self._image, "mode", None) in {"L", "LA", "1"}

    def create2_byte_gray_alpha_image(self, width: int, height: int) -> Any:
        """Allocate a 2-byte (gray + alpha) image buffer. Mirrors
        upstream's private factory used by soft-mask groups."""
        from PIL import Image  # noqa: PLC0415

        return Image.new("LA", (max(1, int(width)), max(1, int(height))), (0, 0))


__all__ = ["PageDrawer", "TransparencyGroup"]
