"""Font-descriptor /Flags decoder.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.FontFlag``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

_FLAGS: COSName = COSName.get_pdf_name("Flags")


class FontFlag(Flag):
    """Decode the ``/Flags`` entry of a font descriptor dictionary."""

    def __init__(self, font_desc_dictionary: COSDictionary) -> None:
        self._font_descriptor = font_desc_dictionary

    # ---- Flag surface ------------------------------------------------------

    def get_flag_type(self) -> str:
        return "Font flag"

    def get_flag_value(self) -> str:
        return "Flag value:" + str(self._font_descriptor.get_int(_FLAGS))

    def get_flag_bits(self) -> list[list[Any]]:
        font_desc = PDFontDescriptor(self._font_descriptor)
        return [
            [1, "FixedPitch", font_desc.is_fixed_pitch()],
            [2, "Serif", font_desc.is_serif()],
            [3, "Symbolic", font_desc.is_symbolic()],
            [4, "Script", font_desc.is_script()],
            [6, "NonSymbolic", font_desc.is_non_symbolic()],
            [7, "Italic", font_desc.is_italic()],
            [17, "AllCap", font_desc.is_all_cap()],
            [18, "SmallCap", font_desc.is_small_cap()],
            [19, "ForceBold", font_desc.is_force_bold()],
        ]
