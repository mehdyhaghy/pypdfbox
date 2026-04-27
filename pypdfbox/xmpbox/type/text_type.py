from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class TextType(AbstractSimpleProperty):
    """
    XMP Text simple property.

    Ported from ``org.apache.xmpbox.type.TextType``. The accepted value is a
    Python ``str``; any non-string raises :class:`ValueError` to mirror
    upstream's ``IllegalArgumentException``.
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
        if not isinstance(value, str):
            raise ValueError(
                f"Value given is not allowed for the Text type : '{value!r}'"
            )
        self._text_value = value

    def get_string_value(self) -> str:
        return self._text_value

    def get_value(self) -> str:
        return self._text_value
