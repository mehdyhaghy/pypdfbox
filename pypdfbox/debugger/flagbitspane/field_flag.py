"""AcroForm field /Ff flag decoder.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.FieldFlag``. The bit
tables depend on the value of /FT (Tx / Btn / Ch / generic).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.flag import Flag

_FF: COSName = COSName.get_pdf_name("Ff")
_FT: COSName = COSName.get_pdf_name("FT")
_TX: COSName = COSName.get_pdf_name("Tx")
_BTN: COSName = COSName.get_pdf_name("Btn")
_CH: COSName = COSName.get_pdf_name("Ch")


class FieldFlag(Flag):
    """Decode the ``/Ff`` entry of an AcroForm field dictionary."""

    def __init__(self, dictionary: COSDictionary) -> None:
        self._dictionary = dictionary

    # ---- Flag surface ------------------------------------------------------

    def get_flag_type(self) -> str:
        field_type = self._dictionary.get_cos_name(_FT)
        if field_type == _TX:
            return "Text field flag"
        if field_type == _BTN:
            return "Button field flag"
        if field_type == _CH:
            return "Choice field flag"
        return "Field flag"

    def get_flag_value(self) -> str:
        return "Flag value: " + str(self._dictionary.get_int(_FF))

    def get_flag_bits(self) -> list[list[Any]]:
        flag_value = self._dictionary.get_int(_FF)
        field_type = self._dictionary.get_cos_name(_FT)
        if field_type == _TX:
            return self.get_text_field_flag_bits(flag_value)
        if field_type == _BTN:
            return self.get_button_field_flag_bits(flag_value)
        if field_type == _CH:
            return self.get_choice_field_flag_bits(flag_value)
        return self.get_field_flag_bits(flag_value)

    # ---- per-field-type decoding tables ------------------------------------
    # Bit positions track PDF 32000-1 §12.7.3.1 (common) and §12.7.4.{2,3,4}
    # (button / text / choice respectively).

    def get_text_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self.is_flag_bit_set(flag_value, 1)],
            [2, "Required", self.is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self.is_flag_bit_set(flag_value, 3)],
            [13, "Multiline", self.is_flag_bit_set(flag_value, 13)],
            [14, "Password", self.is_flag_bit_set(flag_value, 14)],
            [21, "FileSelect", self.is_flag_bit_set(flag_value, 21)],
            [23, "DoNotSpellCheck", self.is_flag_bit_set(flag_value, 23)],
            [24, "DoNotScroll", self.is_flag_bit_set(flag_value, 24)],
            [25, "Comb", self.is_flag_bit_set(flag_value, 25)],
            [26, "RichText", self.is_flag_bit_set(flag_value, 26)],
        ]

    def get_button_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self.is_flag_bit_set(flag_value, 1)],
            [2, "Required", self.is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self.is_flag_bit_set(flag_value, 3)],
            [15, "NoToggleToOff", self.is_flag_bit_set(flag_value, 15)],
            [16, "Radio", self.is_flag_bit_set(flag_value, 16)],
            [17, "Pushbutton", self.is_flag_bit_set(flag_value, 17)],
            [26, "RadiosInUnison", self.is_flag_bit_set(flag_value, 26)],
        ]

    def get_choice_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self.is_flag_bit_set(flag_value, 1)],
            [2, "Required", self.is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self.is_flag_bit_set(flag_value, 3)],
            [18, "Combo", self.is_flag_bit_set(flag_value, 18)],
            [19, "Edit", self.is_flag_bit_set(flag_value, 19)],
            [20, "Sort", self.is_flag_bit_set(flag_value, 20)],
            [22, "MultiSelect", self.is_flag_bit_set(flag_value, 22)],
            [23, "DoNotSpellCheck", self.is_flag_bit_set(flag_value, 23)],
            [27, "CommitOnSelChange", self.is_flag_bit_set(flag_value, 27)],
        ]

    def get_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self.is_flag_bit_set(flag_value, 1)],
            [2, "Required", self.is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self.is_flag_bit_set(flag_value, 3)],
        ]

    @staticmethod
    def is_flag_bit_set(flag_value: int, bit_position: int) -> bool:
        mask = 1 << (bit_position - 1)
        return (flag_value & mask) == mask
