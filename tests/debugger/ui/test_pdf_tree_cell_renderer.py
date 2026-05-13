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
