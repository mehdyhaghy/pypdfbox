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
            return self._get_text_field_flag_bits(flag_value)
        if field_type == _BTN:
            return self._get_button_field_flag_bits(flag_value)
        if field_type == _CH:
            return self._get_choice_field_flag_bits(flag_value)
        return self._get_field_flag_bits(flag_value)

    # ---- private decoding tables ------------------------------------------

    def _get_text_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self._is_flag_bit_set(flag_value, 1)],
            [2, "Required", self._is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self._is_flag_bit_set(flag_value, 3)],
            [13, "Multiline", self._is_flag_bit_set(flag_value, 13)],
            [14, "Password", self._is_flag_bit_set(flag_value, 14)],
            [21, "FileSelect", self._is_flag_bit_set(flag_value, 21)],
            [23, "DoNotSpellCheck", self._is_flag_bit_set(flag_value, 23)],
            [24, "DoNotScroll", self._is_flag_bit_set(flag_value, 24)],
            [25, "Comb", self._is_flag_bit_set(flag_value, 25)],
            [26, "RichText", self._is_flag_bit_set(flag_value, 26)],
        ]

    def _get_button_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self._is_flag_bit_set(flag_value, 1)],
            [2, "Required", self._is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self._is_flag_bit_set(flag_value, 3)],
            [15, "NoToggleToOff", self._is_flag_bit_set(flag_value, 15)],
            [16, "Radio", self._is_flag_bit_set(flag_value, 16)],
            [17, "Pushbutton", self._is_flag_bit_set(flag_value, 17)],
            [26, "RadiosInUnison", self._is_flag_bit_set(flag_value, 26)],
        ]

    def _get_choice_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self._is_flag_bit_set(flag_value, 1)],
            [2, "Required", self._is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self._is_flag_bit_set(flag_value, 3)],
            [18, "Combo", self._is_flag_bit_set(flag_value, 18)],
            [19, "Edit", self._is_flag_bit_set(flag_value, 19)],
            [20, "Sort", self._is_flag_bit_set(flag_value, 20)],
            [22, "MultiSelect", self._is_flag_bit_set(flag_value, 22)],
            [23, "DoNotSpellCheck", self._is_flag_bit_set(flag_value, 23)],
            [27, "CommitOnSelChange", self._is_flag_bit_set(flag_value, 27)],
        ]

    def _get_field_flag_bits(self, flag_value: int) -> list[list[Any]]:
        return [
            [1, "ReadOnly", self._is_flag_bit_set(flag_value, 1)],
            [2, "Required", self._is_flag_bit_set(flag_value, 2)],
            [3, "NoExport", self._is_flag_bit_set(flag_value, 3)],
        ]
