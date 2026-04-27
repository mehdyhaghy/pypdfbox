from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class RealType(AbstractSimpleProperty):
    """
    XMP Real (floating point) simple property.

    Ported from ``org.apache.xmpbox.type.RealType``. Accepts ``float`` /
    ``int`` (treated as float) or a numeric string; the stored value is a
    :class:`float`.
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
            raise ValueError(f"Value given is not allowed for the Real type: {value!r}")
        if isinstance(value, (float, int)):
            self._real_value = float(value)
        elif isinstance(value, str):
            try:
                self._real_value = float(value)
            except ValueError as exc:
                raise ValueError(
                    f"Value given is not allowed for the Real type: {value!r}"
                ) from exc
        else:
            raise ValueError(f"Value given is not allowed for the Real type: {value!r}")

    def get_value(self) -> float:
        return self._real_value

    def get_string_value(self) -> str:
        return str(self._real_value)
