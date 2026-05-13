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
