"""Tkinter widget rendering a font-encoding table.

Tkinter port of ``org.apache.pdfbox.debugger.fontencodingpane.FontEncodingView``.

Swing original is a ``JPanel`` with a ``GridBagLayout`` holding:

* a header panel of ``key: value`` ``JLabel``s, and
* a ``JTable`` with custom ``GlyphCellRenderer`` that draws either a
  scaled ``GeneralPath`` or a ``BufferedImage`` of the glyph.

The pypdfbox port uses ``ttk.Frame`` + ``ttk.Treeview`` for the table.
Treeview can show a single ``PhotoImage`` per row via the ``image=``
keyword, so each glyph cell becomes a generated PIL image rendered with
:func:`PIL.ImageDraw.Draw`. ``ImageTk.PhotoImage`` references are kept
alive on the frame to defeat Tk's aggressive image GC.
"""

from __future__ import annotations

import contextlib
import logging
import tkinter as tk
from collections.abc import Mapping, Sequence
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from pypdfbox.debugger.fontencodingpane.font_pane import _iter_xy_pairs

if TYPE_CHECKING:
    from PIL.Image import Image as PilImage

_LOG = logging.getLogger(__name__)

# Match upstream's "No glyph" sentinel surface area; one of the three
# sentinels (``"None"`` / ``"No glyph"`` / ``".notdef"``) lands in a glyph
# cell when the row carries no renderable outline.
NO_GLYPH_TEXTS: frozenset[str] = frozenset({"None", "No glyph", ".notdef"})

# Default cell dimensions for the rendered glyph thumbnails. Swing's
# JTable uses ``setRowHeight(40)`` and lets columns auto-size; we pick a
# matching height and a reasonable square width so Tk Treeview row icons
# look right.
_CELL_WIDTH: int = 40
_CELL_HEIGHT: int = 40


class FontEncodingView(ttk.Frame):
    """A header + treeview frame summarising a font's encoding."""

    def __init__(
        self,
        master: tk.Misc | None,
        table_data: Sequence[Sequence[Any]],
        header_attributes: Mapping[str, str] | None,
        column_names: Sequence[str],
        y_bounds: tuple[float, float] | None,
    ) -> None:
        """Build the view.

        :param master: parent widget (``None`` uses Tk's implicit default).
        :param table_data: 2-d sequence of rows; the *last* column carries
            the glyph (a path-like outline, a PIL image, ``None`` or one
            of the ``NO_GLYPH_TEXTS`` sentinels).
        :param header_attributes: ordered mapping of ``label -> value``
            rendered above the table. ``None`` or empty omits the header.
        :param column_names: column titles. The last entry is used as the
            glyph-thumbnail column header.
        :param y_bounds: shared ``(min_y, max_y)`` for vector-path glyphs;
            ``None`` disables vector rendering (Type3 fonts use raster
            images directly).
        """
        super().__init__(master)

        self._table_data: list[list[Any]] = [list(row) for row in table_data]
        self._header_attributes: dict[str, str] = (
            dict(header_attributes) if header_attributes else {}
        )
        self._column_names: list[str] = list(column_names)
        self._y_bounds: tuple[float, float] | None = y_bounds

        # Tkinter aggressively garbage-collects ``PhotoImage`` instances
        # that aren't referenced from the widget tree, which would erase
        # every glyph in the table. Stash references here.
        self._photo_refs: list[Any] = []
        self._tree: ttk.Treeview | None = None
        self._header_frame: ttk.Frame | None = None

        self._create_view()

    # ---- public surface ----------------------------------------------------

    def get_panel(self) -> FontEncodingView:
        """Return this frame.

        Upstream returns the contained ``JPanel`` from ``getPanel()``.
        Here the frame *is* the view, so we return ``self``.
        """
        return self

    @property
    def tree(self) -> ttk.Treeview | None:
        """The underlying ``ttk.Treeview`` (``None`` until built)."""
        return self._tree

    # ---- internals ---------------------------------------------------------

    def _create_view(self) -> None:
        with contextlib.suppress(tk.TclError):
            self.configure(width=300, height=500)

        self._header_frame = self._build_header(self._header_attributes)
        if self._header_frame is not None:
            self._header_frame.pack(fill="x", padx=4, pady=(4, 0))

        self._tree = self._build_table()
        self._tree.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_header(
        self, attributes: Mapping[str, str]
    ) -> ttk.Frame | None:
        if not attributes:
            return None
        frame = ttk.Frame(self)
        for row, (key, value) in enumerate(attributes.items()):
            label = ttk.Label(frame, text=f"{key}: {value}")
            label.grid(row=row, column=0, sticky="w", padx=2, pady=1)
        return frame

    def _build_table(self) -> ttk.Treeview:
        # Use the first column as the implicit ``#0`` column so its rows
        # carry the row text/image directly. The remaining columns become
        # ``ttk.Treeview`` "columns" with ``values=`` per row.
        first_name, *rest = self._column_names
        tree = ttk.Treeview(self, columns=rest, show="tree headings")
        tree.heading("#0", text=first_name)
        tree.column("#0", anchor="w", width=80)
        for name in rest:
            tree.heading(name, text=name)
            tree.column(name, anchor="w", width=120)

        # ``ttk.Style`` row-height bump so glyph thumbnails aren't cropped.
        with contextlib.suppress(tk.TclError):
            style = ttk.Style(tree)
            style.configure("Treeview", rowheight=_CELL_HEIGHT)

        for row in self._table_data:
            self._insert_row(tree, row)
        return tree

    def _insert_row(
        self, tree: ttk.Treeview, row: Sequence[Any]
    ) -> None:
        if not row:
            return
        head_value, *tail = row
        head_text = _render_cell_text(head_value)
        if not tail:
            tree.insert("", "end", text=head_text)
            return

        # The glyph thumbnail (if any) lives in the *last* table column.
        # That column's value becomes a label string ("[glyph]") whenever
        # a rendered image is available so Treeview still has a value to
        # show — the image is set via ``tags`` + per-row image attachment
        # below.
        glyph_value = tail[-1]
        body_values = [_render_cell_text(v) for v in tail[:-1]]
        photo = self._render_glyph(glyph_value)
        if photo is not None:
            body_values.append("")
            tree.insert(
                "", "end", text=head_text, values=body_values, image=photo
            )
        else:
            body_values.append(_render_cell_text(glyph_value))
            tree.insert("", "end", text=head_text, values=body_values)

    def _render_glyph(self, value: Any) -> Any | None:
        """Return a ``PhotoImage`` thumbnail for ``value`` or ``None``."""
        if value is None or isinstance(value, str):
            return None
        try:
            from PIL import Image, ImageTk
        except ImportError:  # pragma: no cover - dependency declared
            _LOG.warning("Pillow not available — skipping glyph thumbnails")
            return None

        # 1) If we were handed a PIL image already (Type3 raster path),
        #    just resize-and-wrap it.
        if hasattr(value, "size") and callable(getattr(value, "resize", None)):
            try:
                resized = value.resize(
                    (_CELL_WIDTH, _CELL_HEIGHT), Image.LANCZOS
                )
            except Exception:  # noqa: BLE001 - defensive
                return None
            photo = ImageTk.PhotoImage(resized)
            self._photo_refs.append(photo)
            return photo

        # 2) Otherwise treat ``value`` as a path-like outline and rasterise.
        image = _rasterise_path(value, self._y_bounds)
        if image is None:
            return None
        photo = ImageTk.PhotoImage(image)
        self._photo_refs.append(photo)
        return photo


class GlyphCellRenderer:
    """Renders a single glyph cell as a PIL image.

    Port of the private inner class
    ``FontEncodingView.GlyphCellRenderer`` (PDFBox 3.0). Upstream
    implements ``TableCellRenderer`` and returns a ``JLabel`` carrying a
    centred ``HighResolutionImageIcon``; the PIL path is a one-to-one
    analogue — the produced ``PilImage`` is wrapped into a Tk
    ``PhotoImage`` by :meth:`FontEncodingView._render_glyph`.

    Carried as a top-level class (instead of an inline helper) for
    surface parity with the upstream debugger; it is the actual workhorse
    behind :meth:`FontEncodingView._render_glyph`.
    """

    def __init__(self, y_bounds: tuple[float, float] | None) -> None:
        """Construct the renderer with the shared y-bounds for vector glyphs.

        ``y_bounds`` is the ``(min_y, max_y)`` over the font's whole
        glyph corpus, used to render each glyph at a consistent baseline.
        ``None`` disables vector rendering (used by Type3 fonts where
        rasters are pre-baked).
        """
        self._y_bounds = y_bounds

    def get_y_bounds(self) -> tuple[float, float] | None:
        """Return the shared ``(min_y, max_y)`` glyph-space bounds."""
        return self._y_bounds

    def render_glyph(self, value: Any) -> PilImage | None:
        """Render ``value`` to a PIL image; ``None`` for sentinels / empty paths.

        Accepts:

        * an iterable of glyph segments (vector outline), or
        * a PIL ``Image`` (Type3 raster), or
        * ``None`` / a ``NO_GLYPH_TEXTS`` sentinel string (returns ``None``).

        Mirrors upstream's ``renderGlyph(GeneralPath, Rectangle2D, Rectangle)``
        + the ``BufferedImage`` branch inside
        ``getTableCellRendererComponent``.
        """
        if value is None or (isinstance(value, str) and value in NO_GLYPH_TEXTS):
            return None
        # Pre-baked image — resize and return.
        if hasattr(value, "size") and callable(getattr(value, "resize", None)):
            try:
                from PIL import Image  # noqa: PLC0415
            except ImportError:  # pragma: no cover - PIL declared in deps
                return None
            try:
                return value.resize((_CELL_WIDTH, _CELL_HEIGHT), Image.LANCZOS)
            except Exception:  # noqa: BLE001 - defensive
                return None
        # Vector path: delegate to the module-level rasteriser.
        return _rasterise_path(value, self._y_bounds)

    def get_table_cell_renderer_component(
        self,
        table: Any,
        value: Any,
        is_selected: bool = False,  # noqa: ARG002 - upstream signature parity
        has_focus: bool = False,  # noqa: ARG002
        row: int = 0,  # noqa: ARG002
        column: int = 0,  # noqa: ARG002
    ) -> PilImage | None:
        """Return the per-cell rendering.

        Mirrors upstream's
        ``getTableCellRendererComponent(JTable, Object, boolean, boolean,
        int, int)``. ``table`` and selection-state arguments are accepted
        for signature parity but not used — Tk's ``ttk.Treeview`` paints
        per-row images, not per-cell components.
        """
        del table
        return self.render_glyph(value)


def _render_cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _rasterise_path(
    path: Any, y_bounds: tuple[float, float] | None
) -> PilImage | None:
    """Rasterise a path-like glyph into a white-bg PIL image.

    The Swing original consumes ``java.awt.geom.GeneralPath`` and draws
    via ``Graphics2D.fill``. pypdfbox's glyph outlines are produced by
    fontTools' draw protocol (``moveTo`` / ``lineTo`` / ``qCurveTo`` /
    ``curveTo`` / ``closePath``) and stored as a list of segment tuples,
    so we walk those segments, flatten Bezier curves into polylines, and
    fill the resulting polygon with :func:`PIL.ImageDraw.Draw.polygon`.

    Returns ``None`` when ``path`` is empty (mirroring upstream's
    ``bounds2D.isEmpty()`` skip) or when Pillow is unavailable.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return None

    # Collect raw control points from the path. We treat every numeric
    # ``(x, y)`` pair as a vertex — good enough for a 40x40 thumbnail.
    pts: list[tuple[float, float]] = []
    try:
        items = list(path)
    except TypeError:
        return None
    for item in items:
        for pt in _iter_xy_pairs(item):
            pts.append(pt)
    if not pts:
        return None

    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    if y_bounds is not None:
        min_y, max_y = y_bounds
    else:
        min_y = min(p[1] for p in pts)
        max_y = max(p[1] for p in pts)

    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)
    scale = min(_CELL_WIDTH / span_x, _CELL_HEIGHT / span_y)
    # Center horizontally and flip y so the glyph reads right-side up.
    offset_x = (_CELL_WIDTH - span_x * scale) / 2.0
    offset_y = (_CELL_HEIGHT - span_y * scale) / 2.0

    img = Image.new("RGB", (_CELL_WIDTH, _CELL_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    transformed = [
        (
            offset_x + (x - min_x) * scale,
            _CELL_HEIGHT - offset_y - (y - min_y) * scale,
        )
        for x, y in pts
    ]
    if len(transformed) >= 3:
        try:
            draw.polygon(transformed, fill="black")
        except (TypeError, ValueError):
            # Fall back to a stroked polyline when the polygon can't be
            # filled (e.g. degenerate path).
            for i in range(len(transformed) - 1):
                draw.line(
                    [transformed[i], transformed[i + 1]], fill="black"
                )
    else:
        # Only one or two points — render as a single short stroke so the
        # cell isn't blank.
        if len(transformed) == 2:
            draw.line(transformed, fill="black")
        else:
            x, y = transformed[0]
            draw.rectangle((x, y, x + 1, y + 1), fill="black")
    return img
