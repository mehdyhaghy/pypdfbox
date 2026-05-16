"""Style/icon resolver for debugger tree nodes.

Ported from ``org.apache.pdfbox.debugger.ui.PDFTreeCellRenderer``.

In Swing, the renderer subclasses ``DefaultTreeCellRenderer`` and returns a
fully styled ``Component``. In Tkinter, the ``ttk.Treeview`` renders text via
its model; per-cell icons / colours are applied through tags. We therefore
expose the renderer as a pure-data helper:

* :func:`render_value(node)` -> display string for the row.
* :func:`style_for(node)` -> ``{"icon": <icon-name>, "indirect": bool}`` so the
  consumer can ``tree.tag_configure(...)`` / set an item image.

The class is kept (with the upstream name) because :mod:`PDFTreeCellRenderer`
appears in upstream public APIs of the debugger; the ``__call__`` operator
mirrors the original ``getTreeCellRendererComponent`` shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)

from .array_entry import ArrayEntry
from .document_entry import DocumentEntry
from .map_entry import MapEntry
from .page_entry import PageEntry
from .xref_entries import XrefEntries
from .xref_entry import XrefEntry

#: Logical icon names. The consumer maps these to actual ``PhotoImage``
#: instances via :class:`pypdfbox.debugger.ui.high_resolution_image_icon`.
ICON_ARRAY = "array"
ICON_BOOLEAN = "boolean"
ICON_DICT = "dict"
ICON_HEX = "hex"
ICON_INDIRECT = "indirect"
ICON_INTEGER = "integer"
ICON_NAME = "name"
ICON_NULL = "null"
ICON_REAL = "real"
ICON_STREAM_DICT = "stream-dict"
ICON_STRING = "string"
ICON_PDF = "pdf"
ICON_PAGE = "page"

#: Directory that holds the icon PNGs bundled with the debugger. Mirrors
#: upstream's classpath location ``/org/apache/pdfbox/debugger/``.
RESOURCES_DIR: Path = Path(__file__).resolve().parent / "resources"


def _is_iso_control(c: str) -> bool:
    """Match Java's ``Character.isISOControl``."""
    code = ord(c)
    return 0 <= code <= 0x1F or 0x7F <= code <= 0x9F


def _has_control(text: str) -> bool:
    return any(_is_iso_control(c) for c in text)


class PDFTreeCellRenderer:
    """Stateless renderer; instances kept for API parity with the upstream class."""

    def __call__(self, node_value: Any) -> dict[str, Any]:
        """Return the renderer hint dict for ``node_value``.

        :return: ``{"text": <display>, "icon": <icon-name>, "indirect": bool}``.
        """
        text = render_value(node_value)
        styling = style_for(node_value)
        return {"text": text, **styling}

    def get_tree_cell_renderer_component(
        self,
        tree: Any,
        node_value: Any,
        selected: bool = False,  # noqa: ARG002 - upstream signature passthrough
        expanded: bool = False,  # noqa: ARG002
        leaf: bool = False,  # noqa: ARG002
        row: int = 0,  # noqa: ARG002
        has_focus: bool = False,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Return the per-node render dict.

        Mirrors upstream's
        ``getTreeCellRendererComponent(JTree, Object, boolean, boolean,
        boolean, int, boolean)``. ``tree`` and the selection-state args
        are accepted for signature parity but unused — Tk's
        ``ttk.Treeview`` resolves visuals through tags, not per-call
        return values.
        """
        del tree  # not used; mirrors Swing's ignored ``JTree`` arg
        return self.__call__(node_value)

    def to_tree_object(self, node_value: Any) -> str:
        """Return the text representation used in the tree.

        Mirrors upstream's private ``toTreeObject(Object)``. Exposed here
        as a public method so callers (and parity tooling) can recognise
        the upstream surface.
        """
        return render_value(node_value)

    def lookup_icon(self, node_value: Any) -> str | None:
        """Return the logical icon name for ``node_value`` (``None`` = no icon).

        Mirrors upstream's private ``lookupIcon(Object)``.
        """
        return _lookup_icon(node_value)

    def to_tree_postfix(self, node_value: Any) -> str:
        """Return the right-side postfix string for ``node_value``.

        Mirrors upstream's private ``toTreePostfix(Object)``. For a
        dictionary node this emits ``/T:<type> /S:<subtype>`` fragments
        plus ``/PatternType``, ``/ShadingType`` and a widget ``Name:``
        annotation; for any other node it returns ``""``.
        """
        return _to_tree_postfix(node_value)

    def lookup_icon_with_overlay(
        self, base: Any, overlay: Any = None
    ) -> Any:
        """Compose ``base`` and ``overlay`` into a single icon.

        Mirrors upstream's private ``lookupIconWithOverlay`` but with a
        more useful Python signature. Two calling conventions are
        supported:

        * **Node form** (``overlay is None``): ``base`` is a tree node;
          we resolve its icon name + indirect-overlay flag and return an
          :class:`OverlayIcon` instance for indirect non-stream values
          (or the bare icon name otherwise). Matches the upstream Java
          ``lookupIconWithOverlay(Object)`` semantics, just returning a
          data-only object instead of a Swing ``ImageIcon``.
        * **Image form** (``overlay`` provided): ``base`` and ``overlay``
          are PIL-compatible images; we alpha-composite ``overlay`` on
          top of ``base`` and return the resulting ``PIL.Image.Image``.
          Used by the Tk renderer (and tests) to build composite icons
          out of the indirect-arrow glyph stacked on a base icon.
        """
        if overlay is None:
            icon = _lookup_icon(base)
            is_indirect, is_stream = _indirect_overlay(base)
            if is_indirect and not is_stream:
                wrapper = OverlayIcon(icon)
                wrapper.add(ICON_INDIRECT)
                return wrapper
            return icon
        return _compose_overlay(base, overlay)

    def get_image_url(self, name: str) -> Path | None:
        """Return a filesystem path for the icon file named ``name``.

        Mirrors upstream's static ``getImageUrl(String)``. Upstream
        resolves a classpath URL under
        ``/org/apache/pdfbox/debugger/<name>.png``; we resolve to a
        :class:`pathlib.Path` under
        :data:`RESOURCES_DIR`, returning ``None`` if the file isn't
        bundled (matches Java's behaviour of returning ``null`` for a
        missing classpath resource).
        """
        return get_image_url(name)


# --- pure-data helpers ----------------------------------------------------


def render_value(node_value: Any) -> str:
    """Return the text representation used for ``node_value`` in the tree."""
    return _to_tree_object(node_value)


def style_for(node_value: Any) -> dict[str, Any]:
    """Return ``{"icon": <name>, "indirect": bool}`` for ``node_value``."""
    icon = _lookup_icon(node_value)
    is_indirect, is_stream = _indirect_overlay(node_value)
    return {
        "icon": icon,
        "indirect": is_indirect and not is_stream,
    }


# --- text rendering -------------------------------------------------------


def _to_tree_object(node_value: Any) -> str:
    if isinstance(node_value, (MapEntry, ArrayEntry)):
        if isinstance(node_value, MapEntry):
            key_name = node_value.get_key()
            key = key_name.get_name() if key_name is not None else ""
        else:
            key = str(node_value.get_index())
        value = node_value.get_value()
        item = node_value.get_item()
        nested = _to_tree_object(value)
        if nested:
            result = f"{key}:  {nested}"
            if isinstance(item, COSObject):
                result += f" [{item.get_key()}]"
            result += _to_tree_postfix(value)
            return result
        return key
    if isinstance(node_value, COSBoolean):
        return "true" if node_value.get_value() else "false"
    if isinstance(node_value, COSFloat):
        return str(node_value.float_value())
    if isinstance(node_value, COSInteger):
        return str(node_value.long_value())
    if isinstance(node_value, COSString):
        text = node_value.get_string()
        if _has_control(text):
            return f"<{node_value.to_hex_string()}>"
        return text
    if isinstance(node_value, COSName):
        return node_value.get_name()
    if node_value is None or isinstance(node_value, COSNull):
        return ""
    if isinstance(node_value, COSDictionary):
        if _is_xref_dict(node_value):
            return ""
        return f"({node_value.size()})"
    if isinstance(node_value, COSArray):
        return f"({node_value.size()})"
    if isinstance(node_value, (DocumentEntry, XrefEntries, XrefEntry)):
        return str(node_value)
    return str(node_value)


def _is_xref_dict(dictionary: COSDictionary) -> bool:
    try:
        return dictionary.get_cos_name("Type") == COSName.XREF
    except Exception:  # pragma: no cover - defensive
        return False


def to_tree_postfix(node_value: Any) -> str:
    """Return the right-side postfix string for a tree node.

    Public counterpart to the private ``_to_tree_postfix`` helper. For
    ``COSDictionary`` values this emits ``/T:<type> /S:<subtype>``,
    ``/PatternType``, ``/ShadingType`` and (for widget annotations) a
    ``Name: <T>`` annotation, matching upstream's ``toTreePostfix``.
    Returns ``""`` for any other value.
    """
    return _to_tree_postfix(node_value)


def _to_tree_postfix(node_value: Any) -> str:
    if not isinstance(node_value, COSDictionary):
        return ""
    sb: list[str] = []
    dictionary = node_value
    # Widget annotation or anything with both /T and /Kids -> show /T.
    is_widget = False
    try:
        if dictionary.contains_key("Annot") or dictionary.contains_key("Type"):
            is_annot_widget = (
                dictionary.get_cos_name("Type") == COSName.get_pdf_name("Annot")
                and dictionary.get_cos_name("Subtype")
                == COSName.get_pdf_name("Widget")
            )
            is_widget = is_annot_widget or (
                dictionary.contains_key("T") and dictionary.contains_key("Kids")
            )
    except Exception:  # pragma: no cover - defensive
        is_widget = False
    if is_widget:
        name = dictionary.get_string("T")
        if name is not None:
            sb.append(f"   Name: {name} ")
    if dictionary.contains_key("Type"):
        type_name = dictionary.get_cos_name("Type")
        if type_name is not None:
            sb.append(f"   /T:{type_name.get_name()}")
    if dictionary.contains_key("Subtype"):
        subtype = dictionary.get_cos_name("Subtype")
        if subtype is not None:
            sb.append(f" /S:{subtype.get_name()}")
    if dictionary.contains_key("S"):
        subtype = dictionary.get_cos_name("S")
        if subtype is not None:
            sb.append(f" /S:{subtype.get_name()}")
    if dictionary.contains_key("PatternType"):
        pt = dictionary.get_int("PatternType", -1)
        if pt > -1:
            sb.append(f" /PatternType:{pt}")
    if dictionary.contains_key("ShadingType"):
        st = dictionary.get_int("ShadingType", -1)
        if st > -1:
            sb.append(f" /ShadingType:{st}")
    return "".join(sb)


# --- icon selection -------------------------------------------------------


def _lookup_icon(node_value: Any) -> str | None:
    if isinstance(node_value, MapEntry):
        return _lookup_icon(node_value.get_value())
    if isinstance(node_value, XrefEntry):
        return ICON_INDIRECT
    if isinstance(node_value, ArrayEntry):
        return _lookup_icon(node_value.get_value())
    if isinstance(node_value, COSBoolean):
        return ICON_BOOLEAN
    if isinstance(node_value, COSFloat):
        return ICON_REAL
    if isinstance(node_value, COSInteger):
        return ICON_INTEGER
    if isinstance(node_value, COSString):
        if _has_control(node_value.get_string()):
            return ICON_HEX
        return ICON_STRING
    if isinstance(node_value, COSName):
        return ICON_NAME
    if node_value is None or isinstance(node_value, COSNull):
        return ICON_NULL
    if isinstance(node_value, COSStream):
        return ICON_STREAM_DICT
    if isinstance(node_value, COSDictionary):
        return ICON_DICT
    if isinstance(node_value, COSArray):
        return ICON_ARRAY
    if isinstance(node_value, DocumentEntry):
        return ICON_PDF
    if isinstance(node_value, PageEntry):
        return ICON_PAGE
    if isinstance(node_value, COSObject):
        return ICON_DICT
    return None


def _indirect_overlay(node_value: Any) -> tuple[bool, bool]:
    """Return ``(is_indirect, is_stream)`` flags for the overlay decision."""
    if isinstance(node_value, (MapEntry, ArrayEntry)):
        item = node_value.get_item()
        value = node_value.get_value()
        if isinstance(item, COSObject):
            return True, isinstance(value, COSStream)
    if isinstance(node_value, XrefEntry):
        return True, False
    return False, False


# --- icon resolution / composition ---------------------------------------


def get_image_url(name: str) -> Path | None:
    """Return the on-disk path for the icon named ``name`` (or ``None``).

    Mirrors upstream's ``PDFTreeCellRenderer.getImageUrl(String)`` which
    resolves a classpath URL under
    ``/org/apache/pdfbox/debugger/<name>.png``. Returns ``None`` if the
    file isn't bundled — matches Java's behaviour of returning ``null``
    for a missing classpath resource.
    """
    candidate = RESOURCES_DIR / f"{name}.png"
    if candidate.is_file():
        return candidate
    return None


def lookup_icon_with_overlay(base: Any, overlay: Any = None) -> Any:
    """Compose ``base`` and ``overlay`` into a single icon.

    See :meth:`PDFTreeCellRenderer.lookup_icon_with_overlay` for the two
    supported calling conventions.
    """
    if overlay is None:
        icon = _lookup_icon(base)
        is_indirect, is_stream = _indirect_overlay(base)
        if is_indirect and not is_stream:
            wrapper = OverlayIcon(icon)
            wrapper.add(ICON_INDIRECT)
            return wrapper
        return icon
    return _compose_overlay(base, overlay)


def _compose_overlay(base: Any, overlay: Any) -> Any:
    """Alpha-composite ``overlay`` on top of ``base`` and return the result.

    Both arguments must be PIL ``Image`` objects (or anything that
    implements the same ``size`` / ``convert`` / ``resize`` /
    ``alpha_composite`` surface). The base is converted to RGBA, the
    overlay resized to match if needed, and the two are alpha-composited
    so the overlay's transparent pixels show the base through.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
        raise RuntimeError(
            "Pillow (PIL) is required for lookup_icon_with_overlay() with two images"
        ) from exc

    base_rgba = base.convert("RGBA") if base.mode != "RGBA" else base.copy()
    if overlay.mode != "RGBA":
        overlay_rgba = overlay.convert("RGBA")
    else:
        overlay_rgba = overlay
    if overlay_rgba.size != base_rgba.size:
        overlay_rgba = overlay_rgba.resize(base_rgba.size, Image.LANCZOS)
    base_rgba.alpha_composite(overlay_rgba)
    return base_rgba


class OverlayIcon:
    """An icon that paints other icons over a base image.

    Port of the private inner class
    ``org.apache.pdfbox.debugger.ui.PDFTreeCellRenderer.OverlayIcon``
    (PDFBox 3.0). Upstream extends ``javax.swing.ImageIcon`` and overrides
    ``paintIcon`` so the indirect-object / stream overlays compose on top
    of the base node icon. Tk has no ``ImageIcon`` hierarchy — the
    renderer is data-only — so we expose the same composition surface as
    a tiny container the Tk renderer can consult to paint a base
    ``PhotoImage`` with one or more overlays on top.
    """

    def __init__(self, base: Any) -> None:
        """Wrap ``base`` (a PIL image / Tk ``PhotoImage``-like)."""
        self._base: Any = base
        self._overlays: list[Any] = []

    def get_base(self) -> Any:
        """Return the underlying base icon (mirrors upstream ``base`` field)."""
        return self._base

    def get_overlays(self) -> list[Any]:
        """Return the list of overlay icons (in paint order)."""
        return list(self._overlays)

    def add(self, overlay: Any) -> None:
        """Append ``overlay`` to the paint queue.

        Mirrors upstream's package-private ``add(ImageIcon)``.
        """
        self._overlays.append(overlay)

    def paint_icon(self, component: Any, graphics: Any, x: int, y: int) -> None:
        """Paint the base then each overlay at ``(x, y)``.

        Mirrors upstream's ``paintIcon(Component, Graphics, int, int)``.
        ``component`` and ``graphics`` are duck-typed pass-throughs so a
        Tk caller can supply any object that exposes a ``paint_icon``
        method (e.g. a PhotoImage adapter).
        """
        self._paint_one(self._base, component, graphics, x, y)
        for overlay in self._overlays:
            self._paint_one(overlay, component, graphics, x, y)

    @staticmethod
    def _paint_one(
        icon: Any, component: Any, graphics: Any, x: int, y: int
    ) -> None:
        painter = getattr(icon, "paint_icon", None)
        if painter is not None:
            painter(component, graphics, x, y)
