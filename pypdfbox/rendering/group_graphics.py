"""Composite-graphics adapter used by ``PageDrawer`` for transparency groups.

Mirrors ``org.apache.pdfbox.rendering.GroupGraphics``.

Upstream subclasses AWT's ``Graphics2D`` so a transparency group can
intercept every painting call and write to both a colour bitmap *and* a
parallel "group" bitmap that tracks the touched pixels (used for the
isolation / knockout decisions in §11.4.6 of the PDF spec). The Python
port can't extend ``Graphics2D``; instead we expose a flat class with
the same method names so the renderer can dispatch through it.

Painting primitives are backed by Pillow's :class:`ImageDraw.Draw` so
the group records visible side effects on a parallel ``PIL.Image`` and
can be composited back onto the parent canvas when the group ends.
"""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageChops, ImageDraw


class GroupGraphics:
    """Drop-in adapter mirroring ``java.awt.Graphics2D`` for groups.

    The adapter owns two PIL buffers (mirroring upstream's
    ``BufferedImage`` pair):

    - ``image``      : the colour buffer that receives painted pixels
    - ``group_image``: a single-channel "touched" buffer used for the
                       group's compositing alpha at end-of-group

    Both are optional — when callers only want the state-tracking
    surface (e.g. for parity tests that inspect ``get_color``) the
    buffers stay ``None`` and the painting primitives degrade to
    no-ops.
    """

    def __init__(self, image: Any | None = None, group_image: Any | None = None) -> None:
        self._image = image
        self._group_image = group_image
        self._color: Any = None
        self._font: Any = None
        self._paint: Any = None
        self._stroke: Any = None
        self._composite: Any = None
        self._transform: Any = None
        self._clip: Any = None
        self._background: Any = None
        self._rendering_hints: dict[Any, Any] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _draw(self) -> ImageDraw.ImageDraw | None:
        """Return a PIL drawing context bound to the colour buffer, or
        ``None`` when the buffer isn't attached."""
        if self._image is None:
            return None
        return ImageDraw.Draw(self._image)

    def _stroke_color(self) -> Any:
        """Resolve the active stroke colour: paint wins over color,
        matching AWT's precedence (set_paint overrides set_color)."""
        if self._paint is not None and isinstance(self._paint, (tuple, list, str)):
            return self._paint
        return self._color if self._color is not None else (0, 0, 0)

    # ------------------------------------------------------------------
    # Raster operations
    # ------------------------------------------------------------------

    def clear_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Clear a rectangle to the background color."""
        draw = self._draw()
        if draw is None:
            return
        bg = self._background or (0, 0, 0, 0)
        draw.rectangle((x, y, x + width, y + height), fill=bg)

    def clip_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Intersect the clip with a rectangle."""
        new_rect = (int(x), int(y), int(x + width), int(y + height))
        if self._clip is None:
            self._clip = new_rect
            return
        # Intersection of two rects: max of left/top, min of right/bottom.
        if isinstance(self._clip, tuple) and len(self._clip) == 4:
            left, top, right, bottom = self._clip
            self._clip = (
                max(left, new_rect[0]),
                max(top, new_rect[1]),
                min(right, new_rect[2]),
                min(bottom, new_rect[3]),
            )
        else:
            self._clip = new_rect

    def copy_area(self, x: int, y: int, width: int, height: int, dx: int, dy: int) -> None:
        """Copy a screen rectangle by ``(dx, dy)``."""
        if self._image is None:
            return
        crop = self._image.crop((x, y, x + width, y + height))
        self._image.paste(crop, (x + dx, y + dy))

    def create(self) -> GroupGraphics:
        """Return a shallow copy of this graphics context."""
        clone = GroupGraphics(self._image, self._group_image)
        clone._color = self._color
        clone._font = self._font
        clone._paint = self._paint
        clone._stroke = self._stroke
        clone._composite = self._composite
        clone._transform = self._transform
        clone._clip = self._clip
        clone._background = self._background
        clone._rendering_hints = dict(self._rendering_hints)
        return clone

    def dispose(self) -> None:
        """Release any held resources. PIL buffers self-finalise so
        this drops the references and clears state."""
        self._image = None
        self._group_image = None
        self._clip = None
        self._rendering_hints.clear()

    # ------------------------------------------------------------------
    # Shape draw / fill
    # ------------------------------------------------------------------

    def draw_arc(
        self, x: int, y: int, width: int, height: int, start_angle: int, arc_angle: int
    ) -> None:
        draw = self._draw()
        if draw is None:
            return
        # AWT angles are counter-clockwise; PIL's are clockwise from 3
        # o'clock. Convert by flipping signs.
        end = start_angle + arc_angle
        bbox = (x, y, x + width, y + height)
        draw.arc(bbox, start=-end, end=-start_angle, fill=self._stroke_color())

    def draw_image(self, *args: Any, **kwargs: Any) -> bool:
        """Paste a PIL image onto the buffer. Accepts ``(image, x, y)``
        and ``(image, (x, y))`` shapes (the eight upstream overloads
        collapse to these two)."""
        if self._image is None or not args:
            return True
        source = args[0]
        if not hasattr(source, "size"):
            return True
        if len(args) >= 3:
            x, y = int(args[1]), int(args[2])
        elif len(args) == 2 and isinstance(args[1], tuple):
            x, y = int(args[1][0]), int(args[1][1])
        else:
            x, y = 0, 0
        try:
            self._image.paste(source, (x, y))
        except (ValueError, OSError):
            return False
        return True

    def draw_line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        draw.line((x1, y1, x2, y2), fill=self._stroke_color())

    def draw_oval(self, x: int, y: int, width: int, height: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        draw.ellipse((x, y, x + width, y + height), outline=self._stroke_color())

    def draw_polygon(self, x_points: list[int], y_points: list[int], n_points: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        pts = list(zip(x_points[:n_points], y_points[:n_points], strict=False))
        if len(pts) >= 2:
            draw.polygon(pts, outline=self._stroke_color())

    def draw_polyline(self, x_points: list[int], y_points: list[int], n_points: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        pts = list(zip(x_points[:n_points], y_points[:n_points], strict=False))
        if len(pts) >= 2:
            draw.line(pts, fill=self._stroke_color())

    def draw_round_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        arc_width: int,
        arc_height: int,
    ) -> None:
        draw = self._draw()
        if draw is None:
            return
        radius = max(0, (int(arc_width) + int(arc_height)) // 4)
        draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=radius,
            outline=self._stroke_color(),
        )

    def draw_string(self, *args: Any, **kwargs: Any) -> None:
        """Draw a text string. Accepts ``(text, x, y)``."""
        draw = self._draw()
        if draw is None or len(args) < 3:
            return
        text, x, y = args[0], args[1], args[2]
        draw.text((int(x), int(y)), str(text), fill=self._stroke_color())

    def fill_arc(
        self, x: int, y: int, width: int, height: int, start_angle: int, arc_angle: int
    ) -> None:
        draw = self._draw()
        if draw is None:
            return
        end = start_angle + arc_angle
        draw.pieslice(
            (x, y, x + width, y + height),
            start=-end,
            end=-start_angle,
            fill=self._stroke_color(),
        )

    def fill_oval(self, x: int, y: int, width: int, height: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        draw.ellipse((x, y, x + width, y + height), fill=self._stroke_color())

    def fill_polygon(self, x_points: list[int], y_points: list[int], n_points: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        pts = list(zip(x_points[:n_points], y_points[:n_points], strict=False))
        if len(pts) >= 3:
            draw.polygon(pts, fill=self._stroke_color())

    def fill_rect(self, x: int, y: int, width: int, height: int) -> None:
        draw = self._draw()
        if draw is None:
            return
        draw.rectangle((x, y, x + width, y + height), fill=self._stroke_color())

    def fill_round_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        arc_width: int,
        arc_height: int,
    ) -> None:
        draw = self._draw()
        if draw is None:
            return
        radius = max(0, (int(arc_width) + int(arc_height)) // 4)
        draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=radius,
            fill=self._stroke_color(),
        )

    def fill(self, s: Any) -> None:
        """Fill the supplied shape. ``s`` may be a 4-tuple bbox or an
        iterable of ``(x, y)`` polygon vertices."""
        draw = self._draw()
        if draw is None or s is None:
            return
        if isinstance(s, tuple) and len(s) == 4 and all(isinstance(v, (int, float)) for v in s):
            draw.rectangle(s, fill=self._stroke_color())
            return
        try:
            pts = [(float(p[0]), float(p[1])) for p in s]
        except (TypeError, ValueError, IndexError):
            return
        if len(pts) >= 3:
            draw.polygon(pts, fill=self._stroke_color())

    def draw(self, s: Any) -> None:
        """Stroke the supplied shape."""
        draw = self._draw()
        if draw is None or s is None:
            return
        if isinstance(s, tuple) and len(s) == 4 and all(isinstance(v, (int, float)) for v in s):
            draw.rectangle(s, outline=self._stroke_color())
            return
        try:
            pts = [(float(p[0]), float(p[1])) for p in s]
        except (TypeError, ValueError, IndexError):
            return
        if len(pts) >= 2:
            draw.line(pts, fill=self._stroke_color())

    def draw_glyph_vector(self, g: Any, x: float, y: float) -> None:
        """Render a glyph vector. PIL has no glyph-vector primitive;
        we delegate to ``draw_string`` when the vector exposes a
        ``get_text`` / ``__str__`` representation."""
        if g is None:
            return
        text = ""
        getter = getattr(g, "get_text", None)
        if callable(getter):
            try:
                text = str(getter())
            except Exception:  # noqa: BLE001
                text = ""
        if not text:
            text = str(g)
        self.draw_string(text, x, y)

    def draw_renderable_image(self, img: Any, xform: Any) -> None:
        """Draw a ``RenderableImage`` — delegate to ``draw_image``."""
        self.draw_image(img)

    def draw_rendered_image(self, img: Any, xform: Any) -> None:
        """Draw a ``RenderedImage`` — delegate to ``draw_image``."""
        self.draw_image(img)

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------

    def get_clip(self) -> Any:
        return self._clip

    def get_clip_bounds(self) -> Any:
        return self._clip

    def get_color(self) -> Any:
        return self._color

    def get_font(self) -> Any:
        return self._font

    def get_font_metrics(self, f: Any) -> Any:
        """Return font metrics for ``f``. PIL's ``ImageFont`` exposes
        ``getbbox`` / ``getlength`` — return the font directly so the
        caller can use that API; ``None`` means "no font attached"."""
        return f or self._font

    def set_clip(self, *args: Any) -> None:
        if len(args) == 1:
            self._clip = args[0]
        else:
            self._clip = args

    def set_color(self, c: Any) -> None:
        self._color = c

    def set_font(self, font: Any) -> None:
        self._font = font

    def set_paint_mode(self) -> None:
        """Restore default paint mode. The lite backend always
        composites in source-over mode; this is recorded for
        introspection by clearing any XOR mode state."""
        self._composite = None

    def set_xor_mode(self, c1: Any) -> None:
        """Enable XOR mode against ``c1``."""
        self._composite = ("xor", c1)

    def translate(self, x: float, y: float) -> None:
        """Translate the transform."""
        if self._transform is None:
            self._transform = (1.0, 0.0, 0.0, 1.0, float(x), float(y))
            return
        a, b, c, d, e, f = self._transform
        self._transform = (a, b, c, d, e + a * x + c * y, f + b * x + d * y)

    def add_rendering_hints(self, hints: dict[Any, Any]) -> None:
        self._rendering_hints.update(hints)

    def clip(self, s: Any) -> None:
        """Intersect the clip with a shape."""
        if isinstance(s, tuple) and len(s) == 4:
            left, top, right, bottom = (int(v) for v in s)
            self.clip_rect(left, top, right - left, bottom - top)
        else:
            self._clip = s

    def get_background(self) -> Any:
        return self._background

    def get_composite(self) -> Any:
        return self._composite

    def get_device_configuration(self) -> Any:
        return None

    def get_font_render_context(self) -> Any:
        return None

    def get_paint(self) -> Any:
        return self._paint

    def get_rendering_hint(self, key: Any) -> Any:
        return self._rendering_hints.get(key)

    def get_rendering_hints(self) -> dict[Any, Any]:
        return dict(self._rendering_hints)

    def get_stroke(self) -> Any:
        return self._stroke

    def get_transform(self) -> Any:
        return self._transform

    def hit(self, rect: Any, s: Any, on_stroke: bool) -> bool:
        """Hit-test ``s`` against ``rect``. Returns True when the
        rect's center falls inside ``s`` (4-tuple bbox)."""
        if not isinstance(rect, tuple) or len(rect) != 4:
            return False
        if not isinstance(s, tuple) or len(s) != 4:
            return False
        rx, ry, rw, rh = rect
        cx, cy = rx + rw / 2.0, ry + rh / 2.0
        sl, st, sr, sb = s
        return sl <= cx <= sr and st <= cy <= sb

    def rotate(self, *args: Any) -> None:
        """Rotate the transform. ``rotate(theta)`` or ``rotate(theta, x, y)``."""
        import math  # noqa: PLC0415

        if not args:
            return
        theta = float(args[0])
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        rot = (cos_t, sin_t, -sin_t, cos_t, 0.0, 0.0)
        if len(args) >= 3:
            self.translate(args[1], args[2])
            self._compose(rot)
            self.translate(-args[1], -args[2])
        else:
            self._compose(rot)

    def scale(self, sx: float, sy: float) -> None:
        """Scale the transform."""
        self._compose((float(sx), 0.0, 0.0, float(sy), 0.0, 0.0))

    def set_background(self, color: Any) -> None:
        self._background = color

    def set_composite(self, comp: Any) -> None:
        self._composite = comp

    def set_paint(self, paint: Any) -> None:
        self._paint = paint

    def set_rendering_hint(self, hint_key: Any, hint_value: Any) -> None:
        self._rendering_hints[hint_key] = hint_value

    def set_rendering_hints(self, hints: dict[Any, Any]) -> None:
        self._rendering_hints = dict(hints)

    def set_stroke(self, stroke: Any) -> None:
        self._stroke = stroke

    def set_transform(self, t: Any) -> None:
        self._transform = t

    def shear(self, shx: float, shy: float) -> None:
        """Shear the transform."""
        self._compose((1.0, float(shy), float(shx), 1.0, 0.0, 0.0))

    def transform(self, t: Any) -> None:
        """Compose with another transform."""
        if t is None:
            return
        if not isinstance(t, tuple) or len(t) != 6:
            return
        self._compose(t)

    def _compose(
        self, m: tuple[float, float, float, float, float, float]
    ) -> None:
        if self._transform is None:
            self._transform = m
            return
        a1, b1, c1, d1, e1, f1 = self._transform
        a2, b2, c2, d2, e2, f2 = m
        self._transform = (
            a1 * a2 + c1 * b2,
            b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2,
            b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1,
            b1 * e2 + d1 * f2 + f1,
        )

    # ------------------------------------------------------------------
    # Compositing
    # ------------------------------------------------------------------

    def composite_onto(self, target: Image.Image) -> None:
        """Composite this group's colour buffer onto ``target`` through
        its own alpha channel (PDF §11.4.5 normal-mode blend). Used by
        ``PageDrawer.show_transparency_group`` to flush the group's
        result back to the parent canvas at end-of-group.
        """
        if self._image is None or target is None:
            return
        source = self._image
        if source.mode != "RGBA":
            source = source.convert("RGBA")
        if target.mode == "RGB":
            # ``Image.alpha_composite`` requires both operands to be
            # RGBA — composite into a temporary buffer and paste back.
            tmp = target.convert("RGBA")
            composed = Image.alpha_composite(tmp, source)
            target.paste(composed.convert("RGB"), (0, 0))
        elif target.mode == "RGBA":
            composed = Image.alpha_composite(target, source)
            target.paste(composed, (0, 0))
        else:
            # Generic fallback — paste through alpha so the group's
            # transparent pixels don't overwrite the target.
            alpha = source.split()[-1]
            target.paste(source.convert(target.mode), (0, 0), alpha)

    def backdrop_removal(self) -> None:
        """Run the transparency-group backdrop-removal step.

        Mirrors upstream's private helper that subtracts the captured
        backdrop from the group bitmap (§11.4.5.3 of the PDF spec).
        With a known backdrop, we subtract its RGB from the group
        buffer pixel-by-pixel to recover the group's own contribution.
        """
        if (
            self._image is None
            or self._background is None
            or self._image.mode not in {"RGB", "RGBA"}
        ):
            return
        try:
            backdrop_rgb = tuple(int(v) for v in self._background[:3])
        except (TypeError, ValueError):
            return
        # Construct a constant backdrop image and difference it against
        # the group buffer. ``ImageChops.subtract`` saturates at 0 so
        # this is the §11.4.5.3 "remove backdrop" arithmetic with
        # graceful underflow behaviour.
        backdrop = Image.new(self._image.mode, self._image.size, backdrop_rgb)
        if self._image.mode == "RGBA":
            rgb_part = self._image.convert("RGB")
            removed = ImageChops.subtract(rgb_part, backdrop)
            alpha = self._image.split()[-1]
            removed = removed.convert("RGBA")
            removed.putalpha(alpha)
            self._image = removed
        else:
            self._image = ImageChops.subtract(self._image, backdrop)

    def remove_backdrop(self) -> None:
        """Mirror upstream private ``removeBackdrop`` static helper —
        same operation as :meth:`backdrop_removal`, exposed under the
        upstream method name for parity callers."""
        self.backdrop_removal()


__all__ = ["GroupGraphics"]
