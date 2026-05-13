"""Panose classification decoder.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.PanoseFlag``.

Unlike the other ``Flag`` subclasses, Panose data is byte-positional rather
than bit-positional and uses a 4-column layout (byte position, name, byte
value, English description). Lookup tables for each byte are reproduced
verbatim from upstream.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.pdmodel.font.pd_font_descriptor import PDPanose

_PANOSE: COSName = COSName.get_pdf_name("Panose")


# -- Lookup tables ----------------------------------------------------------
# Verbatim from upstream PanoseFlag.java. Indexed by the byte value at the
# corresponding Panose byte position.

_FAMILY_KIND = (
    "Any",
    "No Fit",
    "Latin Text",
    "Latin Hand Written",
    "Latin Decorative",
    "Latin Symbol",
)

_SERIF_STYLE = (
    "Any",
    "No Fit",
    "Cove",
    "Obtuse Cove",
    "Square Cove",
    "Obtuse Square Cove",
    "Square",
    "Thin",
    "Oval",
    "Exaggerated",
    "Triangle",
    "Normal Sans",
    "Obtuse Sans",
    "Perpendicular Sans",
    "Flared",
    "Rounded",
)

_WEIGHT = (
    "Any",
    "No Fit",
    "Very Light",
    "Light",
    "Thin",
    "Book",
    "Medium",
    "Demi",
    "Bold",
    "Heavy",
    "Black",
    "Extra Black",
)

_PROPORTION = (
    "Any",
    "No fit",
    "Old Style",
    "Modern",
    "Even Width",
    "Extended",
    "Condensed",
    "Very Extended",
    "Very Condensed",
    "Monospaced",
)

_CONTRAST = (
    "Any",
    "No Fit",
    "None",
    "Very Low",
    "Low",
    "Medium Low",
    "Medium",
    "Medium High",
    "High",
    "Very High",
)

_STROKE_VARIATION = (
    "Any",
    "No Fit",
    "No Variation",
    "Gradual/Diagonal",
    "Gradual/Transitional",
    "Gradual/Vertical",
    "Gradual/Horizontal",
    "Rapid/Vertical",
    "Rapid/Horizontal",
    "Instant/Vertical",
    "Instant/Horizontal",
)

_ARM_STYLE = (
    "Any",
    "No Fit",
    "Straight Arms/Horizontal",
    "Straight Arms/Wedge",
    "Straight Arms/Vertical",
    "Straight Arms/Single Serif",
    "Straight Arms/Double Serif",
    "Non-Straight/Horizontal",
    "Non-Straight/Wedge",
    "Non-Straight/Vertical",
    "Non-Straight/Single Serif",
    "Non-Straight/Double Serif",
)

_LETTERFORM = (
    "Any",
    "No Fit",
    "Normal/Contact",
    "Normal/Weighted",
    "Normal/Boxed",
    "Normal/Flattened",
    "Normal/Rounded",
    "Normal/Off Center",
    "Normal/Square",
    "Oblique/Contact",
    "Oblique/Weighted",
    "Oblique/Boxed",
    "Oblique/Flattened",
    "Oblique/Rounded",
    "Oblique/Off Center",
    "Oblique/Square",
)

_MIDLINE = (
    "Any",
    "No Fit",
    "Standard/Trimmed",
    "Standard/Pointed",
    "Standard/Serifed",
    "High/Trimmed",
    "High/Pointed",
    "High/Serifed",
    "Constant/Trimmed",
    "Constant/Pointed",
    "Constant/Serifed",
    "Low/Trimmed",
    "Low/Pointed",
    "Low/Serifed",
)

_X_HEIGHT = (
    "Any",
    "No Fit",
    "Constant/Small",
    "Constant/Standard",
    "Constant/Large",
    "Ducking/Small",
    "Ducking/Standard",
    "Ducking/Large",
)


class PanoseFlag(Flag):
    """Decode the ``/Panose`` byte string in a style dictionary."""

    def __init__(self, dictionary: COSDictionary) -> None:
        value = dictionary.get_dictionary_object(_PANOSE)
        if not isinstance(value, COSString):
            raise TypeError(
                "PanoseFlag expects /Panose to be a COSString; got "
                f"{type(value).__name__}"
            )
        self._byte_value: COSString = value
        self._bytes: bytes = self.get_panose_bytes(dictionary)

    # ---- Flag surface ------------------------------------------------------

    def get_flag_type(self) -> str:
        return "Panose classification"

    def get_flag_value(self) -> str:
        # Upstream uses "Panose byte :" with a space before the colon.
        return "Panose byte :" + self._byte_value.to_hex_string()

    def get_flag_bits(self) -> list[list[Any]]:
        pc = PDPanose(self._bytes).get_panose()
        family_kind = pc.get_family_kind()
        serif_style = pc.get_serif_style()
        weight = pc.get_weight()
        proportion = pc.get_proportion()
        contrast = pc.get_contrast()
        stroke_variation = pc.get_stroke_variation()
        arm_style = pc.get_arm_style()
        letterform = pc.get_letterform()
        midline = pc.get_midline()
        x_height = pc.get_x_height()
        return [
            [2, "Family Kind", family_kind, self._get_family_kind_value(family_kind)],
            [3, "Serif Style", serif_style, self._get_serif_style_value(serif_style)],
            [4, "Weight", weight, self._get_weight_value(weight)],
            [5, "Proportion", proportion, self._get_proportion_value(proportion)],
            [6, "Contrast", contrast, self._get_contrast_value(contrast)],
            [
                7,
                "Stroke Variation",
                stroke_variation,
                self._get_stroke_variation_value(stroke_variation),
            ],
            [8, "Arm Style", arm_style, self._get_arm_style_value(arm_style)],
            [9, "Letterform", letterform, self._get_letterform_value(letterform)],
            [10, "Midline", midline, self._get_midline_value(midline)],
            [11, "X-height", x_height, self._get_x_height_value(x_height)],
        ]

    def get_column_names(self) -> list[str]:
        return ["Byte Position", "Name", "Byte Value", "Value"]

    # ---- per-byte description lookups -------------------------------------

    @staticmethod
    def _get_family_kind_value(index: int) -> str:
        return _FAMILY_KIND[index]

    @staticmethod
    def _get_serif_style_value(index: int) -> str:
        return _SERIF_STYLE[index]

    @staticmethod
    def _get_weight_value(index: int) -> str:
        return _WEIGHT[index]

    @staticmethod
    def _get_proportion_value(index: int) -> str:
        return _PROPORTION[index]

    @staticmethod
    def _get_contrast_value(index: int) -> str:
        return _CONTRAST[index]

    @staticmethod
    def _get_stroke_variation_value(index: int) -> str:
        return _STROKE_VARIATION[index]

    @staticmethod
    def _get_arm_style_value(index: int) -> str:
        return _ARM_STYLE[index]

    @staticmethod
    def _get_letterform_value(index: int) -> str:
        return _LETTERFORM[index]

    @staticmethod
    def _get_midline_value(index: int) -> str:
        return _MIDLINE[index]

    @staticmethod
    def _get_x_height_value(index: int) -> str:
        return _X_HEIGHT[index]

    # ---- raw byte extraction ----------------------------------------------

    @staticmethod
    def get_panose_bytes(style: COSDictionary) -> bytes:
        """Return the raw bytes of the /Panose COSString entry of *style*."""
        panose = style.get_dictionary_object(_PANOSE)
        if not isinstance(panose, COSString):
            raise TypeError(
                "/Panose must resolve to a COSString; got "
                f"{type(panose).__name__}"
            )
        return panose.get_bytes()
