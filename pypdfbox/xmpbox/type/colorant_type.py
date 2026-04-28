from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .integer_type import IntegerType
from .real_type import RealType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class ColorantType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.ColorantType``. Represents the
    ``xmpG:Colorant`` swatch structure used by XMP graphics packets — covers
    Lab, CMYK, and RGB component fields plus ``mode`` / ``swatchName`` /
    ``type`` metadata.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/g/"
    PREFERRED_PREFIX = "xmpG"

    A = "A"
    B = "B"
    L = "L"
    BLACK = "black"
    CYAN = "cyan"
    MAGENTA = "magenta"
    YELLOW = "yellow"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    MODE = "mode"
    SWATCH_NAME = "swatchName"
    TYPE = "type"

    _FIELD_TYPES = {
        A: "Integer",
        B: "Integer",
        L: "Real",
        BLACK: "Real",
        CYAN: "Real",
        MAGENTA: "Real",
        YELLOW: "Real",
        BLUE: "Integer",
        GREEN: "Integer",
        RED: "Integer",
        MODE: "Choice",
        SWATCH_NAME: "Text",
        TYPE: "Choice",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    # --- Lab components -------------------------------------------------

    def get_a(self) -> int | None:
        prop = self.get_first_equivalent_property(self.A, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_a(self, value: int) -> None:
        self.add_simple_property(self.A, value)

    def get_b(self) -> int | None:
        prop = self.get_first_equivalent_property(self.B, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_b(self, value: int) -> None:
        self.add_simple_property(self.B, value)

    def get_l(self) -> float | None:
        prop = self.get_first_equivalent_property(self.L, RealType)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def set_l(self, value: float) -> None:
        self.add_simple_property(self.L, value)

    # --- CMYK components -----------------------------------------------

    def get_black(self) -> float | None:
        prop = self.get_first_equivalent_property(self.BLACK, RealType)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def set_black(self, value: float) -> None:
        self.add_simple_property(self.BLACK, value)

    def get_cyan(self) -> float | None:
        prop = self.get_first_equivalent_property(self.CYAN, RealType)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def set_cyan(self, value: float) -> None:
        self.add_simple_property(self.CYAN, value)

    def get_magenta(self) -> float | None:
        prop = self.get_first_equivalent_property(self.MAGENTA, RealType)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def set_magenta(self, value: float) -> None:
        self.add_simple_property(self.MAGENTA, value)

    def get_yellow(self) -> float | None:
        prop = self.get_first_equivalent_property(self.YELLOW, RealType)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def set_yellow(self, value: float) -> None:
        self.add_simple_property(self.YELLOW, value)

    # --- RGB components ------------------------------------------------

    def get_red(self) -> int | None:
        prop = self.get_first_equivalent_property(self.RED, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_red(self, value: int) -> None:
        self.add_simple_property(self.RED, value)

    def get_green(self) -> int | None:
        prop = self.get_first_equivalent_property(self.GREEN, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_green(self, value: int) -> None:
        self.add_simple_property(self.GREEN, value)

    def get_blue(self) -> int | None:
        prop = self.get_first_equivalent_property(self.BLUE, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_blue(self, value: int) -> None:
        self.add_simple_property(self.BLUE, value)

    # --- Descriptive metadata ------------------------------------------

    def get_mode(self) -> str | None:
        return self.get_property_value_as_string(self.MODE)

    def set_mode(self, value: str) -> None:
        self.add_simple_property(self.MODE, value)

    def get_swatch_name(self) -> str | None:
        return self.get_property_value_as_string(self.SWATCH_NAME)

    def set_swatch_name(self, value: str) -> None:
        self.add_simple_property(self.SWATCH_NAME, value)

    def get_type(self) -> str | None:
        return self.get_property_value_as_string(self.TYPE)

    def set_type(self, value: str) -> None:
        self.add_simple_property(self.TYPE, value)
