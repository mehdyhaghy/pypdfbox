from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .abstract_field import AbstractField

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class AbstractSimpleProperty(AbstractField):
    """
    Abstract base class for simple (scalar) XMP properties.

    Ported from ``org.apache.xmpbox.type.AbstractSimpleProperty``. Subclasses
    implement :meth:`set_value` (which validates and stores), :meth:`get_value`
    (returns the typed Python value) and :meth:`get_string_value` (returns the
    canonical XML serialization). The raw constructor argument is kept around
    via :meth:`get_raw_value` for downstream validation use.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, property_name)
        self.set_value(value)
        self._namespace = namespace_uri
        self._prefix = prefix
        self._raw_value = value

    def set_value(self, value: Any) -> None:
        raise NotImplementedError

    def get_string_value(self) -> str:
        raise NotImplementedError

    def get_value(self) -> Any:
        raise NotImplementedError

    def get_raw_value(self) -> Any:
        return self._raw_value

    def __repr__(self) -> str:
        # Mirrors upstream AbstractSimpleProperty#toString:
        # "[" + propertyName + "=" + simpleClassName + ":" + stringValue + "]"
        return (
            f"[{self.get_property_name()}="
            f"{type(self).__name__}:{self.get_string_value()}]"
        )

    def get_namespace(self) -> str | None:
        return self._namespace

    def get_prefix(self) -> str | None:
        return self._prefix
