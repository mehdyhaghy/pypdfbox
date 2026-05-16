"""Encoding pane for Type 0 (composite) fonts.

Ported from ``org.apache.pdfbox.debugger.fontencodingpane.Type0Font``.

A Type 0 font's descendant CIDFont is either CIDFontType0 (CFF) or
CIDFontType2 (TrueType). When ``/CIDToGIDMap`` is present (CIDFontType2)
the pane renders a ``(CID, GID, unicode, glyph)`` table; otherwise it
walks every code with a glyph and renders ``(code, CID, GID, unicode,
glyph)``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.debugger.fontencodingpane.font_encoding_view import FontEncodingView
from pypdfbox.debugger.fontencodingpane.font_pane import FontPane

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDCIDFont, PDFont, PDType0Font

_LOG = logging.getLogger(__name__)

NO_GLYPH: str = "No glyph"

_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")


class Type0Font(FontPane):
    """CID -> GID + Unicode breakdown for a Type 0 composite font."""

    def __init__(
        self,
        descendant_font: PDCIDFont,
        parent_font: PDType0Font,
        master: tk.Misc | None = None,
    ) -> None:
        """Build the pane.

        :param descendant_font: a :class:`PDCIDFont` (Type0 or Type2).
        :param parent_font: the wrapping :class:`PDType0Font`.
        :param master: parent Tk widget for the view.
        """
        self._descendant_font = descendant_font
        self._parent_font = parent_font
        self._total_available_glyphs = 0

        cid_to_gid = self.read_cid_to_gid_map(descendant_font, parent_font)
        attributes: dict[str, str] = {"Font": str(descendant_font.get_name())}

        if cid_to_gid is not None:
            attributes["CIDs"] = str(len(cid_to_gid))
            attributes["Embedded"] = str(bool(descendant_font.is_embedded()))
            attributes["Encoding"] = self.get_encoding_name(parent_font)
            self._view: FontEncodingView | None = FontEncodingView(
                master,
                cid_to_gid,
                attributes,
                ["CID", "GID", "Unicode Character", "Glyph"],
                self.get_y_bounds(cid_to_gid, 3),
            )
        else:
            tab = self.read_map(descendant_font, parent_font)
            attributes["CIDs"] = str(len(tab))
            attributes["Glyphs"] = str(self._total_available_glyphs)
            attributes["Standard 14"] = str(bool(parent_font.is_standard14()))
            attributes["Embedded"] = str(bool(descendant_font.is_embedded()))
            attributes["Encoding"] = self.get_encoding_name(parent_font)
            self._view = FontEncodingView(
                master,
                tab,
                attributes,
                ["Code", "CID", "GID", "Unicode Character", "Glyph"],
                self.get_y_bounds(tab, 4),
            )

    # ---- FontPane ----------------------------------------------------------

    def get_panel(self) -> tk.Misc:
        """Return the view widget. Upstream returns a 300x500 stub when
        construction failed; pypdfbox builds a fresh ``ttk.Frame`` in
        that case so callers still get a valid widget.
        """
        if self._view is not None:
            return self._view.get_panel()
        return _empty_frame()

    @property
    def view(self) -> FontEncodingView | None:
        return self._view

    @property
    def total_available_glyphs(self) -> int:
        return self._total_available_glyphs

    # ---- helpers -----------------------------------------------------------

    def read_map(
        self, descendant_font: PDCIDFont, parent_font: PDType0Font
    ) -> list[list[Any]]:
        """Mirror upstream ``readMap`` — one row per code with a glyph."""
        rows: list[list[Any]] = []
        for code in range(65535):
            try:
                if not descendant_font.has_glyph(code):
                    continue
            except OSError:
                continue
            cid = self._safe_call(descendant_font.code_to_cid, code)
            gid = self._safe_call(descendant_font.code_to_gid, code)
            try:
                unicode_char = parent_font.to_unicode(code)
            except OSError:
                unicode_char = None
            try:
                path = descendant_font.get_path(code)
            except OSError:
                path = []
            rows.append([code, cid, gid, unicode_char, path])
            if _path_non_empty(path):
                self._total_available_glyphs += 1
        return rows

    def read_cid_to_gid_map(
        self, font: PDCIDFont, parent_font: PDFont
    ) -> list[list[Any]] | None:
        """Mirror upstream ``readCIDToGIDMap`` — parse ``/CIDToGIDMap``
        as a 16-bit big-endian array of GIDs, indexed by CID.
        Returns ``None`` when the entry is absent / not a stream.
        """
        cos_dict: COSDictionary = font.get_cos_object()
        entry = cos_dict.get_dictionary_object(_CID_TO_GID_MAP)
        if not isinstance(entry, COSStream):
            return None
        try:
            map_bytes = bytes(entry.to_byte_array())
        except (AttributeError, OSError):
            try:
                with entry.create_input_stream() as stream:
                    map_bytes = stream.read()
            except (AttributeError, OSError):
                return None

        num_entries = len(map_bytes) // 2
        rows: list[list[Any]] = []
        offset = 0
        for index in range(num_entries):
            gid = (map_bytes[offset] & 0xFF) << 8 | (map_bytes[offset + 1] & 0xFF)
            unicode_char: Any = None
            if gid != 0:
                try:
                    unicode_char = parent_font.to_unicode(index)
                except OSError:
                    unicode_char = None
            try:
                path = font.get_path(index)
            except OSError:
                path = []
            rows.append([index, gid, unicode_char, path])
            if _path_non_empty(path):
                self._total_available_glyphs += 1
            offset += 2
        return rows

    @staticmethod
    def _safe_call(fn: Any, code: int) -> Any:
        try:
            return fn(code)
        except OSError:
            return None

    @staticmethod
    def get_encoding_name(font: PDFont) -> str:
        """Mirror upstream ``getEncodingName(PDFont)``."""
        cos_dict = font.get_cos_object()
        encoding_name = cos_dict.get_name_as_string(_ENCODING)
        if encoding_name is None:
            return type(cos_dict).__name__
        return encoding_name

    # Back-compat aliases for the previously private helpers.
    _get_encoding_name = get_encoding_name
    _read_cid_to_gid_map = read_cid_to_gid_map
    _read_map = read_map


def _path_non_empty(path: Any) -> bool:
    """Return ``True`` when ``path`` contains at least one segment."""
    if path is None or isinstance(path, str):
        return False
    try:
        return any(True for _ in path)
    except TypeError:
        return False


def _empty_frame() -> tk.Misc:
    """Build a 300x500 stub frame mirroring upstream's empty fallback."""
    from tkinter import ttk

    frame = ttk.Frame(width=300, height=500)
    return frame
