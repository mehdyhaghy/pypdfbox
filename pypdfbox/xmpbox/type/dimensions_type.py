from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .real_type import RealType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class DimensionsType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.DimensionsType``. Represents the
    ``stDim:Dimensions`` XMP structure (``w`` / ``h`` / ``unit`` triple) used
    by Dynamic Media XMP packets.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/Dimensions#"
    PREFERRED_PREFIX = "stDim"

    H = "h"
    W = "w"
    UNIT = "unit"

    _FIELD_TYPES = {
        H: "Real",
        W: "Real",
        UNIT: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    def get_h(self) -> float | None:
        prop = self.get_property(self.H)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def getH(self) -> float | None:  # noqa: N802 - upstream Java name
        return self.get_h()

    def get_w(self) -> float | None:
        prop = self.get_property(self.W)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def getW(self) -> float | None:  # noqa: N802 - upstream Java name
        return self.get_w()

    def get_unit(self) -> str | None:
        return self.get_property_value_as_string(self.UNIT)

    def getUnit(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_unit()

    def set_h(self, value: float) -> None:
        self.add_simple_property(self.H, value)

    def setH(self, value: float) -> None:  # noqa: N802 - upstream Java name
        self.set_h(value)

    def set_w(self, value: float) -> None:
        self.add_simple_property(self.W, value)

    def setW(self, value: float) -> None:  # noqa: N802 - upstream Java name
        self.set_w(value)

    def set_unit(self, value: str) -> None:
        self.add_simple_property(self.UNIT, value)

    def setUnit(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_unit(value)

    def __repr__(self) -> str:
        return f"DimensionsType{{{self.get_w()} x {self.get_h()} {self.get_unit()}}}"
