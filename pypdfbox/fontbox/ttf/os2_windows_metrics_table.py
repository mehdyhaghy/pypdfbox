from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream

_LOG = logging.getLogger(__name__)


class OS2WindowsMetricsTable(TTFTable):
    """``OS/2`` — required-but-tolerant TrueType table. Mirrors upstream."""

    TAG: str = "OS/2"

    # weight class
    WEIGHT_CLASS_THIN: int = 100
    WEIGHT_CLASS_ULTRA_LIGHT: int = 200
    WEIGHT_CLASS_LIGHT: int = 300
    WEIGHT_CLASS_NORMAL: int = 400
    WEIGHT_CLASS_MEDIUM: int = 500
    WEIGHT_CLASS_SEMI_BOLD: int = 600
    WEIGHT_CLASS_BOLD: int = 700
    WEIGHT_CLASS_EXTRA_BOLD: int = 800
    WEIGHT_CLASS_BLACK: int = 900

    # width class
    WIDTH_CLASS_ULTRA_CONDENSED: int = 1
    WIDTH_CLASS_EXTRA_CONDENSED: int = 2
    WIDTH_CLASS_CONDENSED: int = 3
    WIDTH_CLASS_SEMI_CONDENSED: int = 4
    WIDTH_CLASS_MEDIUM: int = 5
    WIDTH_CLASS_SEMI_EXPANDED: int = 6
    WIDTH_CLASS_EXPANDED: int = 7
    WIDTH_CLASS_EXTRA_EXPANDED: int = 8
    WIDTH_CLASS_ULTRA_EXPANDED: int = 9

    # family class
    FAMILY_CLASS_NO_CLASSIFICATION: int = 0
    FAMILY_CLASS_OLDSTYLE_SERIFS: int = 1
    FAMILY_CLASS_TRANSITIONAL_SERIFS: int = 2
    FAMILY_CLASS_MODERN_SERIFS: int = 3
    FAMILY_CLASS_CLAREDON_SERIFS: int = 4
    FAMILY_CLASS_SLAB_SERIFS: int = 5
    FAMILY_CLASS_FREEFORM_SERIFS: int = 7
    FAMILY_CLASS_SANS_SERIF: int = 8
    FAMILY_CLASS_ORNAMENTALS: int = 9
    FAMILY_CLASS_SCRIPTS: int = 10
    FAMILY_CLASS_SYMBOLIC: int = 12

    FSTYPE_RESTRICTED: int = 0x0002
    FSTYPE_PREVIEW_AND_PRINT: int = 0x0004
    FSTYPE_EDITIBLE: int = 0x0008
    FSTYPE_NO_SUBSETTING: int = 0x0100
    FSTYPE_BITMAP_ONLY: int = 0x0200

    # fsSelection bits — Microsoft OS/2 spec.
    # Not declared upstream, but every OS/2 reader hard-codes these masks
    # against fsSelection. Centralising them lets callers express
    # boldness / italicness without knowing the bit positions.
    FS_SELECTION_ITALIC: int = 0x0001
    FS_SELECTION_UNDERSCORE: int = 0x0002
    FS_SELECTION_NEGATIVE: int = 0x0004
    FS_SELECTION_OUTLINED: int = 0x0008
    FS_SELECTION_STRIKEOUT: int = 0x0010
    FS_SELECTION_BOLD: int = 0x0020
    FS_SELECTION_REGULAR: int = 0x0040
    FS_SELECTION_USE_TYPO_METRICS: int = 0x0080
    FS_SELECTION_WWS: int = 0x0100
    FS_SELECTION_OBLIQUE: int = 0x0200

    def __init__(self) -> None:
        super().__init__()
        self._version: int = 0
        self._average_char_width: int = 0
        self._weight_class: int = 0
        self._width_class: int = 0
        self._fs_type: int = 0
        self._subscript_x_size: int = 0
        self._subscript_y_size: int = 0
        self._subscript_x_offset: int = 0
        self._subscript_y_offset: int = 0
        self._superscript_x_size: int = 0
        self._superscript_y_size: int = 0
        self._superscript_x_offset: int = 0
        self._superscript_y_offset: int = 0
        self._strikeout_size: int = 0
        self._strikeout_position: int = 0
        self._family_class: int = 0
        self._panose: bytes = b"\x00" * 10
        self._unicode_range1: int = 0
        self._unicode_range2: int = 0
        self._unicode_range3: int = 0
        self._unicode_range4: int = 0
        self._ach_vend_id: str = "XXXX"
        self._fs_selection: int = 0
        self._first_char_index: int = 0
        self._last_char_index: int = 0
        self._typo_ascender: int = 0
        self._typo_descender: int = 0
        self._typo_line_gap: int = 0
        self._win_ascent: int = 0
        self._win_descent: int = 0
        self._code_page_range1: int = 0
        self._code_page_range2: int = 0
        self._sx_height: int = 0
        self._s_cap_height: int = 0
        self._us_default_char: int = 0
        self._us_break_char: int = 0
        self._us_max_context: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._version = data.read_unsigned_short()
        self._average_char_width = data.read_signed_short()
        self._weight_class = data.read_unsigned_short()
        self._width_class = data.read_unsigned_short()
        self._fs_type = data.read_signed_short()
        self._subscript_x_size = data.read_signed_short()
        self._subscript_y_size = data.read_signed_short()
        self._subscript_x_offset = data.read_signed_short()
        self._subscript_y_offset = data.read_signed_short()
        self._superscript_x_size = data.read_signed_short()
        self._superscript_y_size = data.read_signed_short()
        self._superscript_x_offset = data.read_signed_short()
        self._superscript_y_offset = data.read_signed_short()
        self._strikeout_size = data.read_signed_short()
        self._strikeout_position = data.read_signed_short()
        self._family_class = data.read_signed_short()
        self._panose = data.read_bytes(10)
        self._unicode_range1 = data.read_unsigned_int()
        self._unicode_range2 = data.read_unsigned_int()
        self._unicode_range3 = data.read_unsigned_int()
        self._unicode_range4 = data.read_unsigned_int()
        self._ach_vend_id = data.read_string(4)
        self._fs_selection = data.read_unsigned_short()
        self._first_char_index = data.read_unsigned_short()
        self._last_char_index = data.read_unsigned_short()
        try:
            self._typo_ascender = data.read_signed_short()
            self._typo_descender = data.read_signed_short()
            self._typo_line_gap = data.read_signed_short()
            self._win_ascent = data.read_unsigned_short()
            self._win_descent = data.read_unsigned_short()
        except (OSError, EOFError):
            _LOG.debug("EOF, probably some legacy TrueType font")
            self.initialized = True
            return
        if self._version >= 1:
            try:
                self._code_page_range1 = data.read_unsigned_int()
                self._code_page_range2 = data.read_unsigned_int()
            except (OSError, EOFError):
                self._version = 0
                _LOG.warning(
                    "Could not read all expected parts of OS/2 version >= 1, setting version to 0"
                )
                self.initialized = True
                return
        if self._version >= 2:
            try:
                self._sx_height = data.read_signed_short()
                self._s_cap_height = data.read_signed_short()
                self._us_default_char = data.read_unsigned_short()
                self._us_break_char = data.read_unsigned_short()
                self._us_max_context = data.read_unsigned_short()
            except (OSError, EOFError):
                self._version = 1
                _LOG.warning(
                    "Could not read all expected parts of OS/2 version >= 2, setting version to 1"
                )
                self.initialized = True
                return
        self.initialized = True

    # ---- accessors ----
    def get_version(self) -> int:
        return self._version

    def set_version(self, value: int) -> None:
        self._version = value

    def get_average_char_width(self) -> int:
        return self._average_char_width

    def set_average_char_width(self, value: int) -> None:
        self._average_char_width = value

    def get_weight_class(self) -> int:
        return self._weight_class

    def set_weight_class(self, value: int) -> None:
        self._weight_class = value

    def get_width_class(self) -> int:
        return self._width_class

    def set_width_class(self, value: int) -> None:
        self._width_class = value

    def get_fs_type(self) -> int:
        return self._fs_type

    def set_fs_type(self, value: int) -> None:
        self._fs_type = value

    def get_subscript_x_size(self) -> int:
        return self._subscript_x_size

    def set_subscript_x_size(self, value: int) -> None:
        self._subscript_x_size = value

    def get_subscript_y_size(self) -> int:
        return self._subscript_y_size

    def set_subscript_y_size(self, value: int) -> None:
        self._subscript_y_size = value

    def get_subscript_x_offset(self) -> int:
        return self._subscript_x_offset

    def set_subscript_x_offset(self, value: int) -> None:
        self._subscript_x_offset = value

    def get_subscript_y_offset(self) -> int:
        return self._subscript_y_offset

    def set_subscript_y_offset(self, value: int) -> None:
        self._subscript_y_offset = value

    def get_superscript_x_size(self) -> int:
        return self._superscript_x_size

    def set_superscript_x_size(self, value: int) -> None:
        self._superscript_x_size = value

    def get_superscript_y_size(self) -> int:
        return self._superscript_y_size

    def set_superscript_y_size(self, value: int) -> None:
        self._superscript_y_size = value

    def get_superscript_x_offset(self) -> int:
        return self._superscript_x_offset

    def set_superscript_x_offset(self, value: int) -> None:
        self._superscript_x_offset = value

    def get_superscript_y_offset(self) -> int:
        return self._superscript_y_offset

    def set_superscript_y_offset(self, value: int) -> None:
        self._superscript_y_offset = value

    def get_strikeout_size(self) -> int:
        return self._strikeout_size

    def set_strikeout_size(self, value: int) -> None:
        self._strikeout_size = value

    def get_strikeout_position(self) -> int:
        return self._strikeout_position

    def set_strikeout_position(self, value: int) -> None:
        self._strikeout_position = value

    def get_family_class(self) -> int:
        return self._family_class

    def set_family_class(self, value: int) -> None:
        self._family_class = value

    def get_panose(self) -> bytes:
        return self._panose

    def set_panose(self, value: bytes) -> None:
        self._panose = value

    def get_unicode_range1(self) -> int:
        return self._unicode_range1

    def set_unicode_range1(self, value: int) -> None:
        self._unicode_range1 = value

    def get_unicode_range2(self) -> int:
        return self._unicode_range2

    def set_unicode_range2(self, value: int) -> None:
        self._unicode_range2 = value

    def get_unicode_range3(self) -> int:
        return self._unicode_range3

    def set_unicode_range3(self, value: int) -> None:
        self._unicode_range3 = value

    def get_unicode_range4(self) -> int:
        return self._unicode_range4

    def set_unicode_range4(self, value: int) -> None:
        self._unicode_range4 = value

    def get_ach_vend_id(self) -> str:
        return self._ach_vend_id

    def set_ach_vend_id(self, value: str) -> None:
        self._ach_vend_id = value

    def get_fs_selection(self) -> int:
        return self._fs_selection

    def set_fs_selection(self, value: int) -> None:
        self._fs_selection = value

    def get_first_char_index(self) -> int:
        return self._first_char_index

    def set_first_char_index(self, value: int) -> None:
        self._first_char_index = value

    def get_last_char_index(self) -> int:
        return self._last_char_index

    def set_last_char_index(self, value: int) -> None:
        self._last_char_index = value

    def get_typo_ascender(self) -> int:
        return self._typo_ascender

    def set_typo_ascender(self, value: int) -> None:
        self._typo_ascender = value

    def get_typo_descender(self) -> int:
        return self._typo_descender

    def set_typo_descender(self, value: int) -> None:
        self._typo_descender = value

    def get_typo_line_gap(self) -> int:
        return self._typo_line_gap

    def set_typo_line_gap(self, value: int) -> None:
        self._typo_line_gap = value

    def get_win_ascent(self) -> int:
        return self._win_ascent

    def set_win_ascent(self, value: int) -> None:
        self._win_ascent = value

    def get_win_descent(self) -> int:
        return self._win_descent

    def set_win_descent(self, value: int) -> None:
        self._win_descent = value

    def get_code_page_range1(self) -> int:
        return self._code_page_range1

    def set_code_page_range1(self, value: int) -> None:
        self._code_page_range1 = value

    def get_code_page_range2(self) -> int:
        return self._code_page_range2

    def set_code_page_range2(self, value: int) -> None:
        self._code_page_range2 = value

    def get_height(self) -> int:
        return self._sx_height

    def get_cap_height(self) -> int:
        return self._s_cap_height

    def get_default_char(self) -> int:
        return self._us_default_char

    def get_break_char(self) -> int:
        return self._us_break_char

    def get_max_context(self) -> int:
        return self._us_max_context

    # ---- predicate helpers (no upstream equivalent — additions) ----

    def is_italic(self) -> bool:
        """``True`` if the fsSelection Italic bit is set."""
        return bool(self._fs_selection & self.FS_SELECTION_ITALIC)

    def is_bold(self) -> bool:
        """``True`` if the fsSelection Bold bit is set."""
        return bool(self._fs_selection & self.FS_SELECTION_BOLD)

    def is_regular(self) -> bool:
        """``True`` if the fsSelection Regular bit is set.

        The OpenType spec recommends this bit be set if and only if all
        of Italic / Bold / Outlined / Negative / Strikeout / Underscore
        are clear, but the table itself reports the field verbatim.
        """
        return bool(self._fs_selection & self.FS_SELECTION_REGULAR)

    def is_oblique(self) -> bool:
        """``True`` if the fsSelection Oblique bit (v4+, bit 9) is set."""
        return bool(self._fs_selection & self.FS_SELECTION_OBLIQUE)

    def is_strikeout(self) -> bool:
        """``True`` if the fsSelection Strikeout bit is set."""
        return bool(self._fs_selection & self.FS_SELECTION_STRIKEOUT)

    def is_underscore(self) -> bool:
        """``True`` if the fsSelection Underscore bit is set."""
        return bool(self._fs_selection & self.FS_SELECTION_UNDERSCORE)

    def use_typo_metrics(self) -> bool:
        """``True`` if the USE_TYPO_METRICS bit (v4+, bit 7) is set.

        Renderers that honour this bit prefer ``sTypoAscender`` /
        ``sTypoDescender`` / ``sTypoLineGap`` over the win-metrics for
        line spacing.
        """
        return bool(self._fs_selection & self.FS_SELECTION_USE_TYPO_METRICS)

    def is_restricted_license_embedding(self) -> bool:
        """``True`` if fsType marks the font as restricted-license.

        Per the spec, restricted-license must be the only embedding bit
        set; this predicate reports the bit verbatim regardless.
        """
        return bool(self._fs_type & self.FSTYPE_RESTRICTED)

    def allows_subsetting(self) -> bool:
        """``True`` if the font does NOT carry the no-subsetting bit.

        Mirrors the test most callers perform before subsetting:
        ``(fsType & FSTYPE_NO_SUBSETTING) == 0``.
        """
        return not (self._fs_type & self.FSTYPE_NO_SUBSETTING)

    def is_bitmap_embedding_only(self) -> bool:
        """``True`` if fsType restricts embedding to bitmap data only."""
        return bool(self._fs_type & self.FSTYPE_BITMAP_ONLY)
