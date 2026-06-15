from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .real_type import RealType
from .text_type import TextType

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

    def get_w(self) -> float | None:
        prop = self.get_property(self.W)
        if isinstance(prop, RealType):
            return prop.get_value()
        return None

    def get_unit(self) -> str | None:
        return self.get_property_value_as_string(self.UNIT)

    def set_h(self, value: float) -> None:
        self.add_simple_property(self.H, value)

    def set_w(self, value: float) -> None:
        self.add_simple_property(self.W, value)

    def set_unit(self, value: str) -> None:
        self.add_simple_property(self.UNIT, value)

    # --- typed property accessors -------------------------------------

    def get_h_property(self) -> RealType | None:
        """Return the underlying ``RealType`` carrier for ``h`` or ``None``."""
        prop = self.get_property(self.H)
        return prop if isinstance(prop, RealType) else None

    def get_w_property(self) -> RealType | None:
        """Return the underlying ``RealType`` carrier for ``w`` or ``None``."""
        prop = self.get_property(self.W)
        return prop if isinstance(prop, RealType) else None

    def get_unit_property(self) -> TextType | None:
        """Return the underlying ``TextType`` carrier for ``unit`` or ``None``."""
        prop = self.get_property(self.UNIT)
        return prop if isinstance(prop, TextType) else None

    def __repr__(self) -> str:
        return self.to_string()

    def __str__(self) -> str:
        # Mirrors upstream ``DimensionsType.toString()``.
        return self.to_string()

    def to_string(self) -> str:
        """Mirrors upstream ``DimensionsType.toString()`` —
        ``DimensionsType{<w> x <h> <unit>}``. Surfaced explicitly so
        callers porting from PDFBox can keep the literal
        ``.toString()`` invocation spelled snake_case.

        Missing fields render as the literal ``null`` (upstream interpolates
        the ``Float`` / ``String`` field objects via Java string concatenation,
        which renders a ``null`` reference as ``"null"`` — not Python's
        ``"None"``)."""

        def _render(value: object | None) -> str:
            return "null" if value is None else str(value)

        return (
            f"DimensionsType{{{_render(self.get_w())} x "
            f"{_render(self.get_h())} {_render(self.get_unit())}}}"
        )
