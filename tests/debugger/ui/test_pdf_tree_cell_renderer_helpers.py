"""Hand-written tests for the newly promoted ``PDFTreeCellRenderer`` helpers.

Covers the wave-1310 surface:

* :func:`get_image_url` resolves a logical icon name to a filesystem
  ``Path`` under ``pypdfbox/debugger/ui/resources/`` (or ``None`` if the
  PNG isn't bundled).
* :func:`lookup_icon_with_overlay` composes a base PIL image with an
  overlay glyph via alpha compositing.
* :func:`to_tree_postfix` emits the right-side postfix string used in
  the debugger's tree label.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.debugger.ui import PDFTreeCellRenderer
from pypdfbox.debugger.ui.pdf_tree_cell_renderer import (
    ICON_INDIRECT,
    RESOURCES_DIR,
    get_image_url,
    lookup_icon_with_overlay,
    to_tree_postfix,
)

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402 - after importorskip

# ---------------------------------------------------------------------------
# get_image_url
# ---------------------------------------------------------------------------


def test_get_image_url_returns_path_under_resources_dir(tmp_path, monkeypatch):
    """When the PNG exists on disk, ``get_image_url`` returns that ``Path``."""
    # Point RESOURCES_DIR at a temp directory we control.
    monkeypatch.setattr(
        "pypdfbox.debugger.ui.pdf_tree_cell_renderer.RESOURCES_DIR", tmp_path
    )
    (tmp_path / "dict.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    url = get_image_url("dict")
    assert url is not None
    assert url.name == "dict.png"
    assert url.is_file()


def test_get_image_url_missing_returns_none():
    """Missing icons return ``None`` (matches Java's ``null`` semantics)."""
    assert get_image_url("definitely-not-an-icon-12345") is None


def test_get_image_url_resources_dir_points_under_debugger_ui():
    """Sanity-check the default resources path location."""
    assert RESOURCES_DIR.name == "resources"
    assert RESOURCES_DIR.parent.name == "ui"


def test_renderer_get_image_url_delegates_to_module_helper():
    renderer = PDFTreeCellRenderer()
    assert renderer.get_image_url("nope-not-here") is None


# ---------------------------------------------------------------------------
# lookup_icon_with_overlay (image form)
# ---------------------------------------------------------------------------


def _solid(color: tuple[int, int, int, int], size: int = 8) -> Image.Image:
    return Image.new("RGBA", (size, size), color)


def test_lookup_icon_with_overlay_composites_two_images():
    """Overlay's opaque pixels replace the base where they sit."""
    base = _solid((255, 0, 0, 255))  # opaque red
    overlay = _solid((0, 0, 255, 255))  # opaque blue
    composite = lookup_icon_with_overlay(base, overlay)
    assert isinstance(composite, Image.Image)
    assert composite.mode == "RGBA"
    assert composite.size == base.size
    # Fully opaque overlay covers the base entirely.
    assert composite.getpixel((0, 0)) == (0, 0, 255, 255)


def test_lookup_icon_with_overlay_transparent_overlay_keeps_base():
    """A fully transparent overlay leaves the base pixels intact."""
    base = _solid((10, 20, 30, 255))
    overlay = _solid((0, 0, 0, 0))  # fully transparent
    composite = lookup_icon_with_overlay(base, overlay)
    assert composite.getpixel((0, 0)) == (10, 20, 30, 255)


def test_lookup_icon_with_overlay_resizes_overlay_to_base_size():
    """A differently sized overlay is resized to match the base."""
    base = _solid((255, 255, 255, 255), size=16)
    overlay = _solid((0, 0, 0, 255), size=4)
    composite = lookup_icon_with_overlay(base, overlay)
    assert composite.size == base.size


def test_lookup_icon_with_overlay_node_form_returns_overlay_icon_for_indirect():
    """Node-form call returns an ``OverlayIcon`` for indirect map entries."""
    from pypdfbox.cos import COSObject
    from pypdfbox.debugger.ui import OverlayIcon
    from pypdfbox.debugger.ui.map_entry import MapEntry

    inner = COSInteger(7)
    cos_obj = COSObject(3, 0, resolved=inner)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("K"))
    entry.set_value(inner)
    entry.set_item(cos_obj)
    icon = lookup_icon_with_overlay(entry)
    assert isinstance(icon, OverlayIcon)
    assert ICON_INDIRECT in icon.get_overlays()


def test_lookup_icon_with_overlay_node_form_returns_plain_icon_for_direct():
    """Direct values don't get wrapped in an ``OverlayIcon``."""
    icon = lookup_icon_with_overlay(COSInteger(1))
    # Plain icon name string for direct integers.
    assert isinstance(icon, str)


# ---------------------------------------------------------------------------
# to_tree_postfix
# ---------------------------------------------------------------------------


def test_to_tree_postfix_for_dict_includes_type_subtype():
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Annot")
    d.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    postfix = to_tree_postfix(d)
    assert "/T:Annot" in postfix
    assert "/S:Widget" in postfix


def test_to_tree_postfix_for_widget_includes_field_name():
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Annot")
    d.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    d.set_string(COSName.get_pdf_name("T"), "MyField")
    postfix = to_tree_postfix(d)
    assert "Name: MyField" in postfix


def test_to_tree_postfix_for_pattern_dict_includes_pattern_type():
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("PatternType"), 2)
    postfix = to_tree_postfix(d)
    assert "/PatternType:2" in postfix


def test_to_tree_postfix_for_shading_dict_includes_shading_type():
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("ShadingType"), 5)
    postfix = to_tree_postfix(d)
    assert "/ShadingType:5" in postfix


def test_to_tree_postfix_for_array_is_empty():
    """Arrays don't carry a postfix in the upstream renderer."""
    a = COSArray()
    a.add(COSInteger(1))
    a.add(COSInteger(2))
    a.add(COSInteger(3))
    assert to_tree_postfix(a) == ""


def test_to_tree_postfix_for_integer_is_empty():
    """Non-dictionary values produce no postfix."""
    assert to_tree_postfix(COSInteger(42)) == ""


def test_to_tree_postfix_for_none_is_empty():
    assert to_tree_postfix(None) == ""


def test_renderer_to_tree_postfix_delegates_to_module_helper():
    """The class method matches the module-level function."""
    renderer = PDFTreeCellRenderer()
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Page")
    assert renderer.to_tree_postfix(d) == to_tree_postfix(d)
