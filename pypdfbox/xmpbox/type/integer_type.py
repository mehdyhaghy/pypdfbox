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

    Upstream stores the value in a Java ``int`` field and parses strings with
    ``Integer.parseInt``, so the magnitude is bounded to the signed 32-bit
    range ``[-2147483648, 2147483647]``. A string (or direct ``int``) outside
    that range raises ``NumberFormatException`` / ``IllegalArgumentException``
    upstream; the port mirrors that with :class:`ValueError` rather than
    silently accepting Python's unbounded ``int`` (wave 1535).
    """

    _MIN_INT32: int = -(2**31)
    _MAX_INT32: int = 2**31 - 1

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
            parsed = value
        elif isinstance(value, str):
            digits = value[1:] if value[:1] in {"+", "-"} else value
            if not digits or not all("0" <= char <= "9" for char in digits):
                raise ValueError(
                    f"Value given is not allowed for the Integer type: {value!r}"
                )
            parsed = int(value)
        else:
            raise ValueError(f"Value given is not allowed for the Integer type: {value!r}")
        # Upstream stores a Java int (Integer.parseInt); reject anything outside
        # the signed 32-bit range to mirror its NumberFormatException/overflow.
        if not self._MIN_INT32 <= parsed <= self._MAX_INT32:
            raise ValueError(
                f"Value given is not allowed for the Integer type: {value!r}"
            )
        self._integer_value = parsed

    def get_value(self) -> int:
        return self._integer_value

    def get_string_value(self) -> str:
        return str(self._integer_value)
