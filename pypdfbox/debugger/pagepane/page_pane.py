"""Tkinter widget rendering a single PDF page with debug overlays.

Ported from ``org.apache.pdfbox.debugger.pagepane.PagePane`` (PDFBox
3.0). Upstream composes a ``JPanel`` with a ``JLabel`` icon for the
rendered ``BufferedImage`` plus mouse listeners that translate cursor
positions into PDF user space and surface link/widget metadata in the
status bar.

Tk port choices:

- ``JPanel`` + ``BorderFactory`` → ``ttk.Frame`` + ``pack`` geometry.
- ``BufferedImage`` displayed via ``JLabel.setIcon(ImageIcon)`` → PIL
  ``Image`` → ``ImageTk.PhotoImage`` shown on a ``tk.Canvas`` via
  ``create_image``.
- ``MouseListener`` / ``MouseMotionListener`` → ``canvas.bind("<Motion>", ...)``
  and ``"<Button-1>"``.
- ``Graphics2D.draw`` overlay → :class:`DebugTextOverlay.render_to`
  draws via ``PIL.ImageDraw`` *on the rendered image* before it's
  converted to a ``PhotoImage``.
- The ``ZoomMenu`` / ``RotationMenu`` / ``ViewMenu`` singletons live in
  sibling modules. We duck-type the lookup so tests can run before
  those modules land.
"""

from __future__ import annotations

import contextlib
import logging
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from pypdfbox.debugger.pagepane.debug_text_overlay import DebugTextOverlay

if TYPE_CHECKING:
    from PIL.Image import Image as PilImage

    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel import PDDocument, PDPage

_LOG = logging.getLogger(__name__)


class PagePane:
    """Display the page number and a page rendering with debug overlays.

    Mirrors upstream's ``PagePane`` constructor signature: takes the
    ``PDDocument``, a ``COSDictionary`` for the page (allowing orphan
    pages to be displayed) and a status-bar widget for cursor feedback.
    """

    def __init__(
        self,
        master: tk.Misc | None,
        document: PDDocument,
        page_dict: COSDictionary,
        statuslabel: tk.Widget | None = None,
    ) -> None:
        # Lazy imports — pdmodel may not be on the import path during
        # unit tests of the dispatcher's static surface.
        from pypdfbox.pdmodel import PDPage  # noqa: PLC0415

        self._document = document
        self._page: PDPage = PDPage(page_dict)
        self._statuslabel = statuslabel
        try:
            self._page_index: int = document.get_pages().index_of(self._page)
        except (AttributeError, ValueError):
            # Orphan page (not in the document's page tree). Upstream
            # surfaces this via ``pageIndex = -1`` and prints a friendly
            # label.
            self._page_index = -1
        self._label_text: str = ""
        self._current_uri: str = ""
        # ``rect_map`` mirrors upstream's ``Map<PDRectangle,String>`` —
        # built lazily in :meth:`init` from link annotations and field
        # widgets so the status bar can describe what the cursor hovers.
        self._rect_map: dict[Any, str] = {}

        self._panel = ttk.Frame(master)
        self._page_label_widget: ttk.Label | None = None
        self._canvas: tk.Canvas | None = None
        self._photo_image: Any = None  # PIL.ImageTk.PhotoImage (lazy import)
        self._image: PilImage | None = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Build the UI; mirrors upstream's ``init()``.

        Called immediately after construction so tests can assert against
        a populated widget tree.
        """
        self._init_ui()
        self._init_rect_map()
        self._initialized = True

    def get_panel(self) -> ttk.Frame:
        """Return the top-level :class:`ttk.Frame` container."""
        return self._panel

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        if self._page_index < 0:
            page_label_text = "Page number not found (may be an orphan page)"
        else:
            page_label_text = f"Page {self._page_index + 1}"
        label_widget = ttk.Label(
            self._panel,
            text=page_label_text,
            anchor="center",
            font=("TkFixedFont", 16),
        )
        label_widget.pack(side="top", pady=(5, 10))
        self._page_label_widget = label_widget

        canvas = tk.Canvas(
            self._panel, highlightthickness=0, borderwidth=0, background="white"
        )
        canvas.pack(side="top", expand=True, fill="both")
        canvas.bind("<Motion>", self._on_mouse_moved)
        canvas.bind("<Leave>", self._on_mouse_exited)
        canvas.bind("<Button-1>", self._on_mouse_clicked)
        self._canvas = canvas

        # Kick off rendering immediately so that `set_page(...)` is not
        # strictly required before the user sees a page. Tests that
        # don't want rendering can pass an empty page (no contents).
        self._start_rendering()

    def _init_rect_map(self) -> None:
        try:
            self._collect_field_locations()
            self._collect_link_locations()
        except OSError as exc:
            _LOG.error("collecting rect map failed: %s", exc)

    def _collect_link_locations(self) -> None:
        try:
            annotations = self._page.get_annotations()
        except (AttributeError, OSError):
            return
        # Local imports — avoid pulling annotation/action machinery at
        # module load time.
        try:
            from pypdfbox.pdmodel.interactive.action.pd_action_uri import (  # noqa: PLC0415
                PDActionURI,
            )
            from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (  # noqa: PLC0415
                PDAnnotationLink,
            )
        except ImportError:
            return
        for annotation in annotations:
            if not isinstance(annotation, PDAnnotationLink):
                continue
            rect = annotation.get_rectangle()
            if rect is None:
                continue
            action = annotation.get_action()
            if isinstance(action, PDActionURI):
                uri = action.get_uri()
                self._rect_map[rect] = f"URI: {uri}"

    def _collect_field_locations(self) -> None:
        try:
            catalog = self._document.get_document_catalog()
            acroform = catalog.get_acro_form()
        except (AttributeError, OSError):
            return
        if acroform is None:
            return
        try:
            annotations = self._page.get_annotations()
        except (AttributeError, OSError):
            annotations = []
        dictionary_set = {a.get_cos_object() for a in annotations}
        try:
            fields = acroform.get_field_tree()
        except AttributeError:
            return
        for field in fields:
            try:
                widgets = field.get_widgets()
            except AttributeError:
                continue
            for widget in widgets:
                try:
                    widget_dict = widget.get_cos_object()
                except AttributeError:
                    continue
                if widget_dict not in dictionary_set:
                    continue
                rect = widget.get_rectangle()
                if rect is None:
                    continue
                try:
                    name = field.get_fully_qualified_name()
                    value = field.get_value_as_string()
                except AttributeError:
                    name, value = "<field>", ""
                self._rect_map[rect] = f"Field name: {name}, value: {value}"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _start_rendering(self) -> None:
        if self._page_index < 0:
            return
        try:
            image = self._render_image()
        except (OSError, RuntimeError, ImportError) as exc:
            _LOG.error("page render failed: %s", exc)
            return
        self._draw_debug_overlays(image)
        self._present_image(image)

    def _render_image(self) -> PilImage:
        # Lazy import — pulls the full rendering stack on first use.
        from pypdfbox.rendering import PDFRenderer  # noqa: PLC0415

        renderer = PDFRenderer(self._document)
        scale = _resolve_zoom_scale()
        return renderer.render_image(self._page_index, scale=scale)

    def _draw_debug_overlays(self, image: PilImage) -> None:
        """Paint debug overlays onto ``image`` in place when enabled."""
        view_menu = _safe_get_view_menu()
        show_text_stripper = _safe_call(view_menu, "is_show_text_stripper", False)
        show_text_stripper_beads = _safe_call(
            view_menu, "is_show_text_stripper_beads", False
        )
        show_font_bbox = _safe_call(view_menu, "is_show_font_bbox", False)
        show_glyph_bounds = _safe_call(view_menu, "is_show_glyph_bounds", False)
        if not any(
            (
                show_text_stripper,
                show_text_stripper_beads,
                show_font_bbox,
                show_glyph_bounds,
            )
        ):
            return
        try:
            from PIL import ImageDraw  # noqa: PLC0415
        except ImportError:  # pragma: no cover - PIL declared in deps
            return
        draw = ImageDraw.Draw(image)
        overlay = DebugTextOverlay(
            self._document,
            self._page_index,
            scale=_resolve_zoom_scale(),
            show_text_stripper=show_text_stripper,
            show_text_stripper_beads=show_text_stripper_beads,
            show_font_bbox=show_font_bbox,
            show_glyph_bounds=show_glyph_bounds,
        )
        overlay.render_to(draw)

    def _present_image(self, image: PilImage) -> None:
        rotation = _resolve_rotation()
        if rotation:
            try:
                from pypdfbox.debugger.ui.image_util import ImageUtil  # noqa: PLC0415

                image = ImageUtil.get_rotated_image(image, rotation)
            except (ImportError, ValueError):
                pass
        try:
            from PIL import ImageTk  # noqa: PLC0415
        except ImportError:  # pragma: no cover - PIL declared in deps
            return
        if self._canvas is None:
            return
        self._image = image
        photo = ImageTk.PhotoImage(image)
        # Hold a strong reference; Tkinter doesn't keep one and the GC
        # will otherwise drop the texture.
        self._photo_image = photo
        # Clear any previous image content then place the new one.
        self._canvas.delete("rendered_page")
        self._canvas.create_image(
            0, 0, anchor="nw", image=photo, tags=("rendered_page",)
        )
        self._canvas.config(width=image.width, height=image.height)

    # ------------------------------------------------------------------
    # Public surface used by callers / sibling menus
    # ------------------------------------------------------------------

    def set_page(self, page: PDPage) -> None:
        """Replace the rendered page and re-render.

        Mirrors how upstream rebuilds the icon when zoom/rotation
        changes; here we expose it as an explicit setter so the host
        application can swap the visible page without rebuilding the
        widget.
        """
        self._page = page
        try:
            self._page_index = self._document.get_pages().index_of(page)
        except (AttributeError, ValueError):
            self._page_index = -1
        self._rect_map.clear()
        self._init_rect_map()
        self._start_rendering()

    def get_image(self) -> PilImage | None:
        """Return the most recently rendered ``PIL.Image``, if any."""
        return self._image

    # ------------------------------------------------------------------
    # Mouse handlers
    # ------------------------------------------------------------------

    def _on_mouse_moved(self, event: tk.Event[Any]) -> None:
        """Translate cursor pixel position into PDF user-space and update
        the status label. Mirrors upstream's ``mouseMoved``."""
        crop_box = self._page.get_crop_box()
        height = float(crop_box.get_height())
        width = float(crop_box.get_width())
        offset_x = float(crop_box.get_lower_left_x())
        offset_y = float(crop_box.get_lower_left_y())
        zoom_scale = _resolve_zoom_scale()
        if zoom_scale == 0:
            zoom_scale = 1.0
        x = event.x / zoom_scale
        y = event.y / zoom_scale
        rotation = (_resolve_rotation() + self._page.get_rotation()) % 360
        if rotation == 90:
            x1 = int(y + offset_x)
            y1 = int(x + offset_y)
        elif rotation == 180:
            x1 = int(width - x + offset_x)
            y1 = int(y - offset_y)
        elif rotation == 270:
            x1 = int(width - y + offset_x)
            y1 = int(height - x + offset_y)
        else:
            x1 = int(x + offset_x)
            y1 = int(height - y + offset_y)
        text = f"x: {x1}, y: {y1}"

        self._current_uri = ""
        cursor = ""
        for rect, label in self._rect_map.items():
            try:
                hit = rect.contains(x1, y1)
            except (AttributeError, TypeError):
                continue
            if hit:
                text += f", {label}"
                if label.startswith("URI: "):
                    self._current_uri = label[5:]
                    cursor = "hand2"
                break
        if self._canvas is not None:
            with contextlib.suppress(tk.TclError):
                self._canvas.configure(cursor=cursor)
        self._set_status(text)

    def _on_mouse_clicked(self, _event: tk.Event[Any]) -> None:
        """Open the link target if the user clicked over a URI rect."""
        if not self._current_uri:
            return
        try:
            webbrowser.open(self._current_uri)
        except (OSError, RuntimeError) as exc:  # pragma: no cover - desktop env
            _LOG.error("open link %s failed: %s", self._current_uri, exc)

    def _on_mouse_exited(self, _event: tk.Event[Any]) -> None:
        self._set_status(self._label_text)

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str) -> None:
        if self._statuslabel is None:
            return
        with contextlib.suppress(tk.TclError):
            self._statuslabel.configure(text=text)


# ---------------------------------------------------------------------------
# Sibling-singleton lookup helpers
# ---------------------------------------------------------------------------


def _safe_get_view_menu() -> Any:
    try:
        from pypdfbox.debugger.ui.view_menu import ViewMenu  # noqa: PLC0415
    except ImportError:
        return None
    getter = getattr(ViewMenu, "get_instance", None)
    if getter is None:
        return None
    try:
        return getter(None)
    except TypeError:
        try:
            return getter()
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001
        return None


def _safe_call(target: Any, name: str, default: Any) -> Any:
    if target is None:
        return default
    method = getattr(target, name, None)
    if method is None:
        return default
    try:
        return method()
    except Exception:  # noqa: BLE001
        return default


def _resolve_zoom_scale() -> float:
    """Best-effort lookup of the currently active zoom scale.

    Tries the singleton ``ZoomMenu.get_instance().get_page_zoom_scale()``
    surface; falls back to upstream's static ``ZoomMenu.get_zoom_scale``;
    falls back to ``1.0``. The duck-typing path keeps this module
    importable when the sibling menus haven't landed yet.
    """
    try:
        from pypdfbox.debugger.ui.zoom_menu import ZoomMenu  # noqa: PLC0415
    except ImportError:
        return 1.0
    getter = getattr(ZoomMenu, "get_instance", None)
    if getter is not None:
        try:
            inst = getter()
            scale = getattr(inst, "get_page_zoom_scale", lambda: 1.0)()
            return float(scale) if scale else 1.0
        except Exception:  # noqa: BLE001
            pass
    static_getter = getattr(ZoomMenu, "get_zoom_scale", None)
    if static_getter is not None:
        try:
            return float(static_getter())
        except Exception:  # noqa: BLE001
            pass
    return 1.0


def _resolve_rotation() -> int:
    try:
        from pypdfbox.debugger.ui.rotation_menu import RotationMenu  # noqa: PLC0415
    except ImportError:
        return 0
    static_getter = getattr(RotationMenu, "get_rotation_degrees", None)
    if static_getter is not None:
        try:
            return int(static_getter())
        except Exception:  # noqa: BLE001
            pass
    getter = getattr(RotationMenu, "get_instance", None)
    if getter is not None:
        try:
            inst = getter()
            rot = getattr(inst, "get_rotation", lambda: 0)()
            return int(rot) if rot else 0
        except Exception:  # noqa: BLE001
            pass
    return 0
