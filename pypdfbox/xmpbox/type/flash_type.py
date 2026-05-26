from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .boolean_type import BooleanType
from .integer_type import IntegerType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class FlashType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.FlashType``. Represents the EXIF
    flash description used by the ``exif:Flash`` property: the boolean state
    flags (``Fired`` / ``Function`` / ``RedEyeMode``) plus the integer
    ``Mode`` and ``Return`` codes.

    Upstream carries the ``@StructuredType(preferedPrefix = "exif", namespace =
    "http://ns.adobe.com/exif/1.0/")`` annotation, mirrored here by the
    ``NAMESPACE`` / ``PREFERRED_PREFIX`` class attributes. The ``@PropertyType``
    annotations are: ``Fired`` (Boolean), ``Function`` (Boolean),
    ``RedEyeMode`` (Boolean), ``Mode`` (Integer), ``Return`` (Integer).
    """

    NAMESPACE = "http://ns.adobe.com/exif/1.0/"
    PREFERRED_PREFIX = "exif"

    FIRED = "Fired"
    FUNCTION = "Function"
    RED_EYE_MODE = "RedEyeMode"
    MODE = "Mode"
    RETURN = "Return"

    _FIELD_TYPES = {
        FIRED: "Boolean",
        FUNCTION: "Boolean",
        RED_EYE_MODE: "Boolean",
        MODE: "Integer",
        RETURN: "Integer",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    # --- Fired (Boolean) ---------------------------------------------

    def get_fired(self) -> bool | None:
        prop = self.get_first_equivalent_property(self.FIRED, BooleanType)
        if isinstance(prop, BooleanType):
            return prop.get_value()
        return None

    def set_fired(self, value: bool) -> None:
        self.add_simple_property(self.FIRED, value)

    # --- Function (Boolean) ------------------------------------------

    def get_function(self) -> bool | None:
        prop = self.get_first_equivalent_property(self.FUNCTION, BooleanType)
        if isinstance(prop, BooleanType):
            return prop.get_value()
        return None

    def set_function(self, value: bool) -> None:
        self.add_simple_property(self.FUNCTION, value)

    # --- RedEyeMode (Boolean) ----------------------------------------

    def get_red_eye_mode(self) -> bool | None:
        prop = self.get_first_equivalent_property(self.RED_EYE_MODE, BooleanType)
        if isinstance(prop, BooleanType):
            return prop.get_value()
        return None

    def set_red_eye_mode(self, value: bool) -> None:
        self.add_simple_property(self.RED_EYE_MODE, value)

    # --- Mode (Integer) ----------------------------------------------

    def get_mode(self) -> int | None:
        prop = self.get_first_equivalent_property(self.MODE, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_mode(self, value: int) -> None:
        self.add_simple_property(self.MODE, value)

    # --- Return (Integer) --------------------------------------------

    def get_return(self) -> int | None:
        prop = self.get_first_equivalent_property(self.RETURN, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_return(self, value: int) -> None:
        self.add_simple_property(self.RETURN, value)
