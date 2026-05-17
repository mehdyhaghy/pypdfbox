"""Wave 1341 coverage-boost tests for
``pypdfbox.debugger.ui.pdf_tree_cell_renderer``.

Targets the still-uncovered branches in the wave-1332 snapshot:

* :meth:`PDFTreeCellRenderer.lookup_icon_with_overlay` *instance method*
  ``overlay is None`` branch (lines 156-164) — the existing helpers test
  the module-level function. The instance form re-implements the same
  logic and was previously unreachable from tests.
* :func:`_to_tree_object` "nested resolves to empty" path (line 217):
  a ``MapEntry`` whose ``get_value()`` is ``None`` produces an empty
  nested rendering and falls through to ``return key``.
* :func:`_to_tree_object` xref-dictionary carve-out (line 235): a
  dictionary with ``/Type /XRef`` renders as the empty string rather
  than ``"(N)"``.
* :func:`_to_tree_object` final ``return str(node_value)`` fallthrough
  (line 241) for an arbitrary non-COS value.
* :func:`_lookup_icon` ArrayEntry recursion (line 318).
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.debugger.ui import OverlayIcon, PDFTreeCellRenderer
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.pdf_tree_cell_renderer import (
    ICON_INDIRECT,
    ICON_INTEGER,
    _lookup_icon,
    render_value,
)

# ---------- instance lookup_icon_with_overlay (node form) -----------------


def test_instance_lookup_icon_with_overlay_returns_overlay_icon_for_indirect_entry() -> None:
    """The instance method's ``overlay is None`` branch wraps an indirect
    non-stream value in an :class:`OverlayIcon` carrying ``ICON_INDIRECT``.
    """
    inner = COSInteger(42)
    cos_obj = COSObject(5, 0, resolved=inner)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("K"))
    entry.set_value(inner)
    entry.set_item(cos_obj)
    renderer = PDFTreeCellRenderer()
    icon = renderer.lookup_icon_with_overlay(entry)
    assert isinstance(icon, OverlayIcon)
    assert ICON_INDIRECT in icon.get_overlays()


def test_instance_lookup_icon_with_overlay_returns_plain_icon_for_direct_value() -> None:
    """Direct values flow through unchanged (no OverlayIcon wrapping)."""
    renderer = PDFTreeCellRenderer()
    icon = renderer.lookup_icon_with_overlay(COSInteger(7))
    assert icon == ICON_INTEGER


def test_instance_lookup_icon_with_overlay_image_form_composes_images() -> None:
    """The image-form call (overlay supplied) alpha-composites two PIL
    images and returns the composite. Mirrors the module-level
    function's image-form behaviour.
    """
    from PIL import Image

    base = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    overlay = Image.new("RGBA", (4, 4), (0, 0, 255, 128))
    renderer = PDFTreeCellRenderer()
    out = renderer.lookup_icon_with_overlay(base, overlay)
    # Result is a PIL image — the composite of red base + half-transparent
    # blue overlay.
    assert out.size == (4, 4)
    assert out.mode == "RGBA"


# ---------- render_value: empty nested -> bare key fallback --------------


def test_render_value_map_entry_with_none_value_returns_bare_key() -> None:
    """A MapEntry whose value renders to ``""`` (here: a ``None`` value)
    falls through to ``return key`` rather than the ``"key:  nested"``
    form.
    """
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("BareKey"))
    entry.set_value(None)
    assert render_value(entry) == "BareKey"


def test_render_value_array_entry_with_none_value_returns_bare_index() -> None:
    """Same fallback for ArrayEntry: empty nested -> bare index string."""
    entry = ArrayEntry()
    entry.set_index(3)
    entry.set_value(None)
    assert render_value(entry) == "3"


# ---------- render_value: xref dictionary carve-out ----------------------


def test_render_value_xref_dictionary_renders_as_empty_string() -> None:
    """A dictionary with ``/Type /XRef`` is treated specially — its
    rendering is the empty string (not ``"(N)"``).
    """
    xref = COSDictionary()
    xref.set_item(COSName.get_pdf_name("Type"), COSName.XREF)
    assert render_value(xref) == ""


# ---------- render_value: final fallback through str() -------------------


def test_render_value_unknown_object_falls_through_to_str() -> None:
    """An object that is none of COSBoolean/COSFloat/COSInteger/COSString/
    COSName/COSNull/COSDictionary/COSArray/DocumentEntry/XrefEntries/
    XrefEntry/MapEntry/ArrayEntry hits the final ``return str(node_value)``.
    """

    class _Custom:
        def __str__(self) -> str:
            return "custom-string-repr"

    assert render_value(_Custom()) == "custom-string-repr"


# ---------- _lookup_icon: ArrayEntry recursion ---------------------------


def test_lookup_icon_for_array_entry_recurses_into_value() -> None:
    """An ArrayEntry whose value is a COSInteger resolves to the integer icon."""
    entry = ArrayEntry()
    entry.set_index(0)
    entry.set_value(COSInteger(99))
    assert _lookup_icon(entry) == ICON_INTEGER
