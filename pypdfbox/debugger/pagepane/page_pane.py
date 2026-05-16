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
        self.init_ui()
        self.init_rect_map()
        self._initialized = True

    def get_panel(self) -> ttk.Frame:
        """Return the top-level :class:`ttk.Frame` container."""
        return self._panel

    # ------------------------------------------------------------------
    # UI / rect-map construction (public — matches upstream surface)
    # ------------------------------------------------------------------

    def init_ui(self) -> None:
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
        self.start_rendering()

    def init_rect_map(self) -> None:
        """Re-build the click-resolution rect map from scratch.

        Mirrors upstream's ``initRectMap()``. Calls the field collector
        first (upstream order), then the link collector. Always wipes
        :attr:`_rect_map` before re-populating so successive calls don't
        double-map widgets/links.
        """
        self._rect_map.clear()
        try:
            # Dispatch via the underscore-prefixed back-compat names so
            # tests monkeypatching ``_collect_link_locations`` /
            # ``_collect_field_locations`` continue to observe their
            # patched implementation.
            self._collect_field_locations()
            self._collect_link_locations()
        except OSError as exc:
            _LOG.error("collecting rect map failed: %s", exc)

    def collect_link_locations(self) -> None:
        """Walk every link annotation on the page and record its rect
        in :attr:`_rect_map` via :meth:`collect_link_location`. Mirrors
        upstream's ``collectLinkLocations()``.
        """
        try:
            annotations = self._page.get_annotations()
        except (AttributeError, OSError):
            return
        # Local import — avoid pulling annotation machinery at module
        # load time.
        try:
            from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (  # noqa: PLC0415
                PDAnnotationLink,
            )
        except ImportError:
            return
        for annotation in annotations:
            if not isinstance(annotation, PDAnnotationLink):
                continue
            self.collect_link_location(annotation)

    def collect_link_location(self, link_annotation: Any) -> None:
        """Record one link annotation in :attr:`_rect_map`.

        Mirrors upstream's ``collectLinkLocation(PDAnnotationLink)``.
        Stores the link's user-space ``/Rect`` (unchanged — upstream does
        no screen-space transform here; the hover handler applies the
        zoom/rotation transform when checking ``rect.contains``) keyed by
        the rectangle object, with a label of ``"URI: <uri>"`` for
        ``PDActionURI`` and ``"Page destination: <n>"`` for go-to /
        named-destination actions resolving to a known page number.
        """
        rect = link_annotation.get_rectangle()
        if rect is None:
            return
        try:
            from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (  # noqa: PLC0415
                PDActionGoTo,
            )
            from pypdfbox.pdmodel.interactive.action.pd_action_uri import (  # noqa: PLC0415
                PDActionURI,
            )
            from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (  # noqa: PLC0415
                PDNamedDestination,
            )
            from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: PLC0415
                PDPageDestination,
            )
        except ImportError:
            # Action/destination machinery isn't loadable — fall back to
            # the URI-only path used by the original code.
            PDActionGoTo = None  # noqa: N806
            PDNamedDestination = None  # noqa: N806
            PDPageDestination = None  # noqa: N806
            try:
                from pypdfbox.pdmodel.interactive.action.pd_action_uri import (  # noqa: PLC0415
                    PDActionURI,
                )
            except ImportError:
                return
        try:
            action = link_annotation.get_action()
        except (AttributeError, OSError):
            return
        if isinstance(action, PDActionURI):
            uri = action.get_uri()
            self._rect_map[rect] = f"URI: {uri}"
            return
        if PDActionGoTo is None or PDPageDestination is None:
            return
        destination = None
        try:
            if isinstance(action, PDActionGoTo):
                destination = action.get_destination()
            else:
                getter = getattr(link_annotation, "get_destination", None)
                destination = getter() if getter is not None else None
            if PDNamedDestination is not None and isinstance(
                destination, PDNamedDestination
            ):
                catalog = self._document.get_document_catalog()
                resolver = getattr(catalog, "find_named_destination_page", None)
                if resolver is not None:
                    destination = resolver(destination)
        except (AttributeError, OSError) as exc:
            _LOG.error("resolving link destination failed: %s", exc)
        if isinstance(destination, PDPageDestination):
            try:
                page_num = destination.retrieve_page_number()
            except (AttributeError, OSError):
                return
            if page_num != -1:
                self._rect_map[rect] = f"Page destination: {page_num + 1}"

    def collect_field_locations(self) -> None:
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

    def start_rendering(self) -> None:
        """Kick off the rendering pipeline for the current page.

        Mirrors upstream ``PagePane.startRendering()`` (private). Upstream
        delegates to ``new RenderWorker().execute()`` so the page renders
        off the EDT; the Tk port runs synchronously because :class:`RenderWorker`
        below also executes synchronously (see its docstring). The underscore-
        prefixed alias :py:meth:`_start_rendering` is retained for callers
        / tests that used the original name.
        """
        if self._page_index < 0:
            return
        try:
            image = self._render_image()
        except (OSError, RuntimeError, ImportError) as exc:
            _LOG.error("page render failed: %s", exc)
            return
        self._draw_debug_overlays(image)
        self._present_image(image)

    def start_extracting(self) -> None:
        """Run the PDF text stripper for the current page and surface the result.

        Mirrors upstream ``PagePane.startExtracting()`` (private): builds
        a :class:`PDFTextStripper`, restricts it to the current page,
        applies the *sort by position* / *ignore content stream space
        glyphs* toggles from :class:`TextStripperMenu`, and feeds the
        extracted text into a :class:`TextDialog`. The upstream version
        also positions the dialog and sets its size; we omit the screen-
        sizing math because the Tk port's :class:`TextDialog` manages
        its own geometry. Errors are logged and swallowed (upstream
        catches ``IOException``).
        """
        if self._page_index < 0:
            return
        try:
            from pypdfbox.debugger.ui.text_dialog import TextDialog  # noqa: PLC0415
            from pypdfbox.debugger.ui.text_stripper_menu import (  # noqa: PLC0415
                TextStripperMenu,
            )
            from pypdfbox.text.pdf_text_stripper import PDFTextStripper  # noqa: PLC0415
        except ImportError as exc:
            _LOG.error("text extraction dependencies missing: %s", exc)
            return
        try:
            stripper = PDFTextStripper()
            stripper.set_start_page(self._page_index + 1)
            stripper.set_end_page(self._page_index + 1)
            sorted_getter = getattr(TextStripperMenu, "is_sorted", None)
            if sorted_getter is not None:
                with contextlib.suppress(Exception):
                    stripper.set_sort_by_position(bool(sorted_getter()))
            ignore_getter = getattr(TextStripperMenu, "is_ignore_spaces", None)
            if ignore_getter is not None:
                setter = getattr(
                    stripper, "set_ignore_content_stream_space_glyphs", None
                )
                if setter is not None:
                    with contextlib.suppress(Exception):
                        setter(bool(ignore_getter()))
            text = stripper.get_text(self._document)
        except OSError as exc:
            _LOG.error("text extraction failed: %s", exc)
            return
        instance_getter = getattr(TextDialog, "instance", None)
        dialog = instance_getter() if instance_getter is not None else None
        if dialog is None:
            return
        setter = getattr(dialog, "set_text", None)
        if setter is not None:
            with contextlib.suppress(Exception):
                setter(text)
        visible_setter = getattr(dialog, "set_visible", None)
        if visible_setter is not None:
            with contextlib.suppress(Exception):
                visible_setter(True)

    # Back-compat private alias.
    _start_rendering = start_rendering

    def _render_image(self) -> PilImage:
        # Lazy import — pulls the full rendering stack on first use.
        from pypdfbox.rendering import PDFRenderer  # noqa: PLC0415

        renderer = PDFRenderer(self._document)
        # Mirror upstream: PDFRenderer.setSubsamplingAllowed is gated on
        # ViewMenu.isAllowSubsampling(). Use a duck-typed setter so the
        # renderer doesn't have to expose one.
        subsampling = _resolve_allow_subsampling()
        setter = getattr(renderer, "set_subsampling_allowed", None)
        if setter is not None:
            with contextlib.suppress(TypeError, ValueError):
                setter(subsampling)
        scale = _resolve_zoom_scale()
        image_type = _resolve_image_type()
        destination = _resolve_render_destination()
        # Thread the resolved destination through the four-arg
        # ``render_image`` overload (mirrors upstream's
        # ``renderImage(int, float, ImageType, RenderDestination)``);
        # passing ``None`` defers to the renderer-level default so this
        # call site no longer has to mutate ``set_default_destination``.
        return renderer.render_image(
            self._page_index,
            scale=scale,
            image_type=image_type,
            destination=destination,
        )

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
        # ``init_rect_map`` clears + repopulates atomically; no separate
        # clear needed here.
        self.init_rect_map()
        self.start_rendering()

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

    # ------------------------------------------------------------------
    # Back-compat private aliases (wave 1308 promoted these to public)
    # ------------------------------------------------------------------

    # Tests written against the original underscore-prefixed names keep
    # working; the public surface above matches upstream PagePane.
    _init_ui = init_ui
    _init_rect_map = init_rect_map
    _collect_link_locations = collect_link_locations
    _collect_link_location = collect_link_location
    _collect_field_locations = collect_field_locations


# ---------------------------------------------------------------------------
# Sibling-singleton lookup helpers
# ---------------------------------------------------------------------------


def _safe_get_view_menu() -> Any:
    """Return the live ``ViewMenu`` singleton, or ``None``.

    Never instantiates the singleton: doing so would create tk objects
    attached to whatever ``Tk`` root happens to be current at the
    moment of the first render, which can race with the test harness
    and the upstream debugger main shell (which owns the singleton
    lifecycle).
    """
    try:
        from pypdfbox.debugger.ui.view_menu import ViewMenu  # noqa: PLC0415
    except ImportError:
        return None
    return getattr(ViewMenu, "_instance", None)


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

    Prefer the static ``ZoomMenu.get_zoom_scale()`` surface (matches
    upstream's ``RenderWorker``); fall back to the live instance's
    ``get_page_zoom_scale``; fall back to ``1.0``. We never instantiate
    the singleton from here — doing so would attach the underlying
    ``tk.StringVar`` to whatever ``Tk`` root happens to be current, and
    upstream relies on callers (the debugger main shell) to create the
    singleton first.
    """
    try:
        from pypdfbox.debugger.ui.zoom_menu import ZoomMenu  # noqa: PLC0415
    except ImportError:
        return 1.0
    static_getter = getattr(ZoomMenu, "get_zoom_scale", None)
    if static_getter is not None:
        try:
            return float(static_getter())
        except Exception:  # noqa: BLE001
            pass
    instance = getattr(ZoomMenu, "_instance", None)
    if instance is not None:
        try:
            scale = instance.get_page_zoom_scale()
            return float(scale) if scale else 1.0
        except Exception:  # noqa: BLE001
            pass
    return 1.0


def _resolve_rotation() -> int:
    """Look up the current rotation in degrees from the singleton.

    Like :func:`_resolve_zoom_scale`, this never instantiates the
    singleton — the menu is created by the debugger main shell.
    """
    try:
        from pypdfbox.debugger.ui.rotation_menu import RotationMenu  # noqa: PLC0415
    except ImportError:
        return 0
    instance = getattr(RotationMenu, "_instance", None)
    if instance is None:
        return 0
    static_getter = getattr(RotationMenu, "get_rotation_degrees", None)
    if static_getter is not None:
        try:
            return int(static_getter())
        except Exception:  # noqa: BLE001
            pass
    return 0


def _resolve_image_type() -> Any:
    """Look up the currently selected :class:`ImageType` from
    ``ImageTypeMenu``. Returns ``None`` when the menu hasn't been
    instantiated yet so the renderer keeps its historical RGB
    behaviour. Mirrors upstream's ``ImageTypeMenu.getImageType()``.
    """
    try:
        from pypdfbox.debugger.ui.image_type_menu import (  # noqa: PLC0415
            ImageTypeMenu,
        )
    except ImportError:
        return None
    getter = getattr(ImageTypeMenu, "get_image_type", None)
    if getter is None:
        return None
    try:
        return getter()
    except (RuntimeError, ValueError):
        # Menu not yet instantiated, or label unknown — defer to the
        # renderer's default (RGB).
        return None
    except Exception:  # noqa: BLE001
        return None


def _resolve_render_destination() -> Any:
    """Look up the currently selected :class:`RenderDestination` from
    ``RenderDestinationMenu``. Returns ``None`` when the menu hasn't
    been instantiated. Mirrors upstream's
    ``RenderDestinationMenu.getRenderDestination()``.
    """
    try:
        from pypdfbox.debugger.ui.render_destination_menu import (  # noqa: PLC0415
            RenderDestinationMenu,
        )
    except ImportError:
        return None
    getter = getattr(RenderDestinationMenu, "get_render_destination", None)
    if getter is None:
        return None
    try:
        return getter()
    except Exception:  # noqa: BLE001
        return None


def _resolve_allow_subsampling() -> bool:
    """Mirror upstream's ``ViewMenu.isAllowSubsampling()``."""
    try:
        from pypdfbox.debugger.ui.view_menu import ViewMenu  # noqa: PLC0415
    except ImportError:
        return False
    getter = getattr(ViewMenu, "is_allow_subsampling", None)
    if getter is None:
        return False
    try:
        return bool(getter())
    except Exception:  # noqa: BLE001
        return False


class RenderWorker:
    """Synchronous port of ``PagePane.RenderWorker`` (PDFBox 3.0).

    Upstream extends ``SwingWorker<BufferedImage, Integer>`` and runs the
    page render off the EDT, calling ``label.setIcon(...)`` from
    :meth:`done` when finished. Tkinter has no equivalent worker idiom in
    the stdlib (and PIL rendering is fast enough for an interactive
    debugger that the cost of an extra thread isn't worth the safety
    hazard), so this port runs synchronously.

    Surface kept compatible: :meth:`do_in_background` returns the
    rendered PIL image (after debug overlays and rotation); :meth:`done`
    presents it on the host pane's canvas. Call :meth:`execute` for the
    upstream all-in-one entry point. The worker holds a back-reference to
    its owning :class:`PagePane` so callbacks land on the right canvas.

    Behavioural deviation from upstream is documented in CHANGES.md
    (no background thread).
    """

    def __init__(self, page_pane: PagePane) -> None:
        self._page_pane = page_pane
        self._result: PilImage | None = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def execute(self) -> PilImage | None:
        """Run the worker end-to-end and return the rendered image.

        Mirrors ``SwingWorker.execute()`` — the upstream chain is
        ``execute() -> doInBackground() -> done()``.
        """
        try:
            image = self.do_in_background()
        except (OSError, RuntimeError, ImportError) as exc:
            _LOG.error("page render failed: %s", exc)
            self._result = None
            return None
        self._result = image
        self.done()
        return image

    def do_in_background(self) -> PilImage:
        """Render the page (plus overlays and rotation) and return the image.

        Mirrors the upstream protected method of the same name. Pulls
        zoom / image-type / rotation through the same singletons as
        :meth:`PagePane._start_rendering` so an out-of-band caller (e.g.
        a test) gets identical output.
        """
        pp = self._page_pane
        # Reuse the existing render pipeline so behaviour stays in lock
        # step with PagePane's inline path. The intermediate steps
        # mirror upstream's RenderWorker.doInBackground line-for-line:
        #   renderImage → DebugTextOverlay overlay → ImageUtil rotation.
        image = pp._render_image()  # noqa: SLF001 - same-module helper
        pp._draw_debug_overlays(image)  # noqa: SLF001
        rotation = _resolve_rotation()
        if rotation:
            try:
                from pypdfbox.debugger.ui.image_util import (  # noqa: PLC0415
                    ImageUtil,
                )

                image = ImageUtil.get_rotated_image(image, rotation)
            except (ImportError, ValueError):
                pass
        return image

    def done(self) -> None:
        """Hand off the rendered image to the host pane.

        Mirrors the upstream protected method. ``do_in_background`` /
        ``execute`` must have produced :attr:`_result` first; ``None``
        defers to the pane's existing canvas state.
        """
        if self._result is None:
            return
        self._page_pane._present_image(self._result)  # noqa: SLF001

    def get(self) -> PilImage | None:
        """Return the most recently produced image.

        Mirrors ``SwingWorker.get()`` (modulo the checked
        ``InterruptedException`` / ``ExecutionException`` semantics, which
        don't apply to a synchronous port).
        """
        return self._result
