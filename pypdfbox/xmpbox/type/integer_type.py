from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class IntegerType(AbstractSimpleProperty):
    """
    XMP Integer simple property.

    Ported from ``org.apache.xmpbox.type.IntegerType``. Accepts ``int`` or
    a decimal ``str`` (which is parsed via :class:`int`); other types
    or unparseable strings raise :class:`ValueError`.
    """

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
            raise ValueError(f"Value given is not allowed for the Integer type: {value!r}")
        if isinstance(value, int):
            self._integer_value = value
        elif isinstance(value, str):
            digits = value[1:] if value[:1] in {"+", "-"} else value
            if not digits or not all("0" <= char <= "9" for char in digits):
                raise ValueError(
                    f"Value given is not allowed for the Integer type: {value!r}"
                )
            self._integer_value = int(value)
        else:
            raise ValueError(f"Value given is not allowed for the Integer type: {value!r}")

    def get_value(self) -> int:
        return self._integer_value

    def get_string_value(self) -> str:
        return str(self._integer_value)
