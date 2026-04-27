from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class BooleanType(AbstractSimpleProperty):
    """
    XMP Boolean simple property.

    Ported from ``org.apache.xmpbox.type.BooleanType``. The XMP serialization
    uses the strings ``"True"`` / ``"False"`` (capitalised); :meth:`set_value`
    accepts a :class:`bool` or a case-insensitive ``"true"``/``"false"`` string.
    """

    TRUE: ClassVar[str] = "True"
    FALSE: ClassVar[str] = "False"

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, namespace_uri, prefix, property_name, value)

    def set_value(self, value: Any) -> None:
        if isinstance(value, bool):
            self._boolean_value = value
            return
        if isinstance(value, str):
            stripped = value.strip().upper()
            if stripped == "TRUE":
                self._boolean_value = True
                return
            if stripped == "FALSE":
                self._boolean_value = False
                return
            raise ValueError(f"Not a valid boolean value : '{value}'")
        raise ValueError("Value given is not allowed for the Boolean type.")

    def get_value(self) -> bool:
        return self._boolean_value

    def get_string_value(self) -> str:
        return self.TRUE if self._boolean_value else self.FALSE
