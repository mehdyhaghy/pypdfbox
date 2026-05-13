"""Hand-written tests for ``pypdfbox.debugger.ui.PDFTreeCellRenderer``."""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.debugger.ui import PDFTreeCellRenderer
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.pdf_tree_cell_renderer import (
    ICON_ARRAY,
    ICON_BOOLEAN,
    ICON_DICT,
    ICON_HEX,
    ICON_INTEGER,
    ICON_NAME,
    ICON_NULL,
    ICON_REAL,
    ICON_STRING,
    render_value,
    style_for,
)


def test_boolean_render_and_icon() -> None:
    assert render_value(COSBoolean.TRUE) == "true"
    assert render_value(COSBoolean.FALSE) == "false"
    assert style_for(COSBoolean.TRUE)["icon"] == ICON_BOOLEAN


def test_integer_render() -> None:
    val = COSInteger(42)
    assert render_value(val) == "42"
    assert style_for(val)["icon"] == ICON_INTEGER


def test_float_render() -> None:
    val = COSFloat(3.5)
    assert render_value(val) == "3.5"
    assert style_for(val)["icon"] == ICON_REAL


def test_string_render_plain() -> None:
    val = COSString("hello")
    assert render_value(val) == "hello"
    assert style_for(val)["icon"] == ICON_STRING


def test_string_render_control_chars_as_hex() -> None:
    val = COSString("\x01ctrl")
    rendered = render_value(val)
    assert rendered.startswith("<") and rendered.endswith(">")
    assert style_for(val)["icon"] == ICON_HEX


def test_name_render() -> None:
    val = COSName.get_pdf_name("Type")
    assert render_value(val) == "Type"
    assert style_for(val)["icon"] == ICON_NAME


def test_none_and_cosnull_render_blank() -> None:
    assert render_value(None) == ""
    assert render_value(COSNull.NULL) == ""
    assert style_for(None)["icon"] == ICON_NULL


def test_dictionary_render_size() -> None:
    d = COSDictionary()
    d.set_string("Foo", "bar")
    assert render_value(d) == "(1)"
    assert style_for(d)["icon"] == ICON_DICT


def test_array_render_size() -> None:
    a = COSArray()
    a.add(COSInteger(1))
    a.add(COSInteger(2))
    assert render_value(a) == "(2)"
    assert style_for(a)["icon"] == ICON_ARRAY


def test_map_entry_render_combines_key_and_value() -> None:
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Subtype"))
    entry.set_value(COSName.get_pdf_name("Widget"))
    assert render_value(entry) == "Subtype:  Widget"


def test_array_entry_render_combines_index_and_value() -> None:
    entry = ArrayEntry()
    entry.set_index(3)
    entry.set_value(COSInteger(7))
    assert render_value(entry) == "3:  7"


def test_dictionary_postfix_includes_type_and_subtype() -> None:
    inner = COSDictionary()
    inner.set_name("Type", "Annot")
    inner.set_name("Subtype", "Widget")
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Field"))
    entry.set_value(inner)
    rendered = render_value(entry)
    assert "/T:Annot" in rendered
    assert "/S:Widget" in rendered


def test_renderer_callable_returns_dict() -> None:
    renderer = PDFTreeCellRenderer()
    val = COSInteger(5)
    result = renderer(val)
    assert result["text"] == "5"
    assert result["icon"] == ICON_INTEGER
    assert result["indirect"] is False


# ---- additional dictionary postfix branches ------------------------------


def test_dictionary_postfix_includes_widget_name() -> None:
    """A field-widget annotation surfaces the ``/T`` field name in postfix."""
    inner = COSDictionary()
    inner.set_name(COSName.get_pdf_name("Type"), "Annot")
    inner.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    inner.set_string(COSName.get_pdf_name("T"), "FieldA")
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("X"))
    entry.set_value(inner)
    rendered = render_value(entry)
    assert "Name: FieldA" in rendered


def test_dictionary_postfix_only_s_when_no_subtype() -> None:
    inner = COSDictionary()
    inner.set_name(COSName.get_pdf_name("Type"), "Action")
    inner.set_name(COSName.get_pdf_name("S"), "URI")
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("A"))
    entry.set_value(inner)
    rendered = render_value(entry)
    # Both /T: and /S: should appear once each.
    assert "/T:Action" in rendered
    assert "/S:URI" in rendered


def test_dictionary_postfix_pattern_type() -> None:
    inner = COSDictionary()
    inner.set_int(COSName.get_pdf_name("PatternType"), 2)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("P"))
    entry.set_value(inner)
    rendered = render_value(entry)
    assert "/PatternType:2" in rendered


def test_dictionary_postfix_shading_type() -> None:
    inner = COSDictionary()
    inner.set_int(COSName.get_pdf_name("ShadingType"), 5)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Sh"))
    entry.set_value(inner)
    rendered = render_value(entry)
    assert "/ShadingType:5" in rendered


def test_map_entry_postfix_includes_indirect_reference_label() -> None:
    """A map entry whose item is a ``COSObject`` shows ``[N gen R]``."""
    from pypdfbox.cos import COSObject

    inner = COSDictionary()
    inner.set_name(COSName.get_pdf_name("Type"), "Annot")
    inner.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    cos_obj = COSObject(5, 0, resolved=inner)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Field"))
    entry.set_value(inner)
    entry.set_item(cos_obj)
    rendered = render_value(entry)
    # Indirect-object label appears between the rendered value and postfix.
    assert "[" in rendered


# ---- additional icon branches -------------------------------------------


def test_stream_icon() -> None:
    from pypdfbox.cos import COSStream
    from pypdfbox.debugger.ui.pdf_tree_cell_renderer import ICON_STREAM_DICT

    stream = COSStream()
    assert style_for(stream)["icon"] == ICON_STREAM_DICT


def test_document_entry_icon() -> None:
    from pypdfbox.debugger.ui import DocumentEntry
    from pypdfbox.debugger.ui.pdf_tree_cell_renderer import ICON_PDF
    from pypdfbox.pdmodel import PDDocument

    doc = PDDocument()
    try:
        entry = DocumentEntry(doc, "x.pdf")
        assert style_for(entry)["icon"] == ICON_PDF
    finally:
        doc.close()


def test_page_entry_icon() -> None:
    from pypdfbox.debugger.ui import DocumentEntry, PageEntry
    from pypdfbox.debugger.ui.pdf_tree_cell_renderer import ICON_PAGE
    from pypdfbox.pdmodel import PDDocument, PDPage

    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        entry = DocumentEntry(doc, "x.pdf")
        page = entry.get_page(0)
        assert isinstance(page, PageEntry)
        assert style_for(page)["icon"] == ICON_PAGE
    finally:
        doc.close()


def test_xref_entry_icon_is_indirect() -> None:
    from pypdfbox.cos import COSObject, COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry
    from pypdfbox.debugger.ui.pdf_tree_cell_renderer import ICON_INDIRECT

    cos_obj = COSObject(7, 0, resolved=COSInteger(0))
    xe = XrefEntry(0, COSObjectKey(7, 0), 100, cos_obj)
    assert style_for(xe)["icon"] == ICON_INDIRECT


def test_cos_object_icon_is_dict() -> None:
    from pypdfbox.cos import COSObject
    from pypdfbox.debugger.ui.pdf_tree_cell_renderer import ICON_DICT

    obj = COSObject(8, 0, resolved=COSInteger(0))
    assert style_for(obj)["icon"] == ICON_DICT


def test_unknown_node_icon_returns_none() -> None:
    sentinel = object()
    assert style_for(sentinel)["icon"] is None


# ---- indirect overlay flag ----------------------------------------------


def test_indirect_overlay_for_map_entry_with_cos_object() -> None:
    from pypdfbox.cos import COSObject

    inner = COSInteger(5)
    cos_obj = COSObject(9, 0, resolved=inner)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("K"))
    entry.set_value(inner)
    entry.set_item(cos_obj)
    assert style_for(entry)["indirect"] is True


def test_indirect_overlay_suppressed_for_stream_value() -> None:
    from pypdfbox.cos import COSObject, COSStream

    inner = COSStream()
    cos_obj = COSObject(10, 0, resolved=inner)
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("S"))
    entry.set_value(inner)
    entry.set_item(cos_obj)
    # Stream icon already implies indirection — the overlay is suppressed.
    assert style_for(entry)["indirect"] is False


def test_xref_entry_indirect_overlay() -> None:
    from pypdfbox.cos import COSObject, COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry

    cos_obj = COSObject(11, 0, resolved=COSInteger(0))
    xe = XrefEntry(0, COSObjectKey(11, 0), 100, cos_obj)
    assert style_for(xe)["indirect"] is True


def test_xref_entry_renders_as_string() -> None:
    from pypdfbox.cos import COSObject, COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry

    cos_obj = COSObject(12, 0, resolved=COSInteger(0))
    xe = XrefEntry(0, COSObjectKey(12, 0), 100, cos_obj)
    # render_value uses str() for XrefEntry; non-empty result.
    rendered = render_value(xe)
    assert rendered  # truthy
