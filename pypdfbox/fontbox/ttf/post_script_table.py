from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import wgl4_names
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream

_LOG = logging.getLogger(__name__)


class PostScriptTable(TTFTable):
    """``post`` — required TrueType table. Mirrors upstream."""

    TAG: str = "post"

    def __init__(self) -> None:
        super().__init__()
        self._format_type: float = 0.0
        self._italic_angle: float = 0.0
        self._underline_position: int = 0
        self._underline_thickness: int = 0
        self._is_fixed_pitch: int = 0
        self._min_mem_type42: int = 0
        self._max_mem_type42: int = 0
        self._mim_mem_type1: int = 0
        self._max_mem_type1: int = 0
        self._glyph_names: list[str] | None = None

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._format_type = data.read_32_fixed()
        self._italic_angle = data.read_32_fixed()
        self._underline_position = data.read_signed_short()
        self._underline_thickness = data.read_signed_short()
        self._is_fixed_pitch = data.read_unsigned_int()
        self._min_mem_type42 = data.read_unsigned_int()
        self._max_mem_type42 = data.read_unsigned_int()
        self._mim_mem_type1 = data.read_unsigned_int()
        self._max_mem_type1 = data.read_unsigned_int()

        if data.get_current_position() == data.get_original_data_size():
            _LOG.warning("No PostScript name data is provided for the font %s", ttf.get_name())
        elif self._format_type == 1.0:
            self._glyph_names = wgl4_names.get_all_names()
        elif self._format_type == 2.0:
            self._read_format_2(ttf, data)
        elif self._format_type == 2.5:
            self._read_format_2_5(ttf, data)
        elif self._format_type == 3.0:
            _LOG.debug("No PostScript name information is provided for the font %s", ttf.get_name())
        elif self._format_type == 4.0:
            self._read_format_4(ttf, data)

        self.initialized = True

    def _read_format_2(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        num_glyphs = data.read_unsigned_short()
        glyph_name_index = [0] * num_glyphs
        self._glyph_names = [""] * num_glyphs
        max_index = -2_147_483_648
        for i in range(num_glyphs):
            index = data.read_unsigned_short()
            glyph_name_index[i] = index
            # PDFBOX-808: 32768..65535 reserved
            if index <= 32767:
                if index > max_index:
                    max_index = index

        name_array: list[str] | None = None
        if max_index >= wgl4_names.NUMBER_OF_MAC_GLYPHS:
            length = max_index - wgl4_names.NUMBER_OF_MAC_GLYPHS + 1
            name_array = [""] * length
            for i in range(length):
                try:
                    number_of_chars = data.read_unsigned_byte()
                    name_array[i] = data.read_string(number_of_chars)
                except (OSError, EOFError) as exc:
                    # PDFBOX-4851: EOF while reading post names; pad with .notdef
                    _LOG.warning(
                        "Error reading names in PostScript table at entry %d of %d, "
                        "setting remaining entries to .notdef: %s",
                        i,
                        length,
                        exc,
                    )
                    for j in range(i, length):
                        name_array[j] = ".notdef"
                    break

        for i in range(num_glyphs):
            index = glyph_name_index[i]
            if 0 <= index < wgl4_names.NUMBER_OF_MAC_GLYPHS:
                name = wgl4_names.get_glyph_name(index)
                self._glyph_names[i] = name if name is not None else ".undefined"
            elif (
                wgl4_names.NUMBER_OF_MAC_GLYPHS <= index <= 32767
                and name_array is not None
            ):
                self._glyph_names[i] = name_array[index - wgl4_names.NUMBER_OF_MAC_GLYPHS]
            else:
                self._glyph_names[i] = ".undefined"

    def _read_format_2_5(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        num_glyphs = ttf.get_number_of_glyphs()
        glyph_name_index = [0] * num_glyphs
        for i in range(num_glyphs):
            offset = data.read_signed_byte()
            glyph_name_index[i] = i + 1 + offset
        names = [""] * num_glyphs
        for i in range(num_glyphs):
            index = glyph_name_index[i]
            if 0 <= index < wgl4_names.NUMBER_OF_MAC_GLYPHS:
                name = wgl4_names.get_glyph_name(index)
                if name is not None:
                    names[i] = name
            else:
                _LOG.debug(
                    "incorrect glyph name index %d, valid numbers 0..%d",
                    index,
                    wgl4_names.NUMBER_OF_MAC_GLYPHS,
                )
        self._glyph_names = names

    def _read_format_4(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        """Format 4.0 — used for CID fonts on Mac. Per-glyph 16-bit CIDs.

        The names are synthesized as ``"aN"`` where N is the CID, mirroring the
        convention upstream uses for these glyphs.
        """
        num_glyphs = ttf.get_number_of_glyphs()
        names: list[str] = [".undefined"] * num_glyphs
        for i in range(num_glyphs):
            try:
                cid = data.read_unsigned_short()
            except (OSError, EOFError) as exc:
                _LOG.warning(
                    "Error reading CIDs in PostScript table at entry %d of %d: %s",
                    i,
                    num_glyphs,
                    exc,
                )
                break
            names[i] = f"a{cid}"
        self._glyph_names = names

    # ---- accessors ----
    def get_format_type(self) -> float:
        return self._format_type

    def get_italic_angle(self) -> float:
        return self._italic_angle

    def get_underline_position(self) -> int:
        return self._underline_position

    def get_underline_thickness(self) -> int:
        return self._underline_thickness

    def get_is_fixed_pitch(self) -> int:
        return self._is_fixed_pitch

    def get_min_mem_type42(self) -> int:
        return self._min_mem_type42

    def get_max_mem_type42(self) -> int:
        return self._max_mem_type42

    def get_min_mem_type1(self) -> int:
        return self._mim_mem_type1

    def get_max_mem_type1(self) -> int:
        return self._max_mem_type1

    def get_glyph_names(self) -> list[str] | None:
        return self._glyph_names

    def set_glyph_names(self, value: list[str] | None) -> None:
        self._glyph_names = value

    def get_name(self, gid: int) -> str | None:
        if gid < 0 or self._glyph_names is None or gid >= len(self._glyph_names):
            return None
        return self._glyph_names[gid]
