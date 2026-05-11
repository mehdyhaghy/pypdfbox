"""Factory that instantiates :class:`XMPSchema` subclasses.

Mirrors ``org.apache.xmpbox.schema.XMPSchemaFactory`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/schema/XMPSchemaFactory.java``).
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from pypdfbox.xmpbox.type.type_mapping import PropertiesDescription, PropertyType
from pypdfbox.xmpbox.xmp_schema import XMPSchema

if TYPE_CHECKING:
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


class XmpSchemaException(OSError):
    """Mirrors Java's ``XmpSchemaException``."""


class XMPSchemaFactory:
    """Build :class:`XMPSchema` instances under a fixed namespace."""

    def __init__(
        self,
        namespace: str,
        schema_class: type[XMPSchema],
        prop_def: PropertiesDescription,
    ) -> None:
        self._namespace = namespace
        self._schema_class = schema_class
        self._prop_def = prop_def

    def get_namespace(self) -> str:
        return self._namespace

    def get_property_type(self, name: str) -> PropertyType | None:
        return self._prop_def.get_property_type(name)

    def get_property_definition(self) -> PropertiesDescription:
        return self._prop_def

    def create_xmp_schema(
        self, metadata: XMPMetadata, prefix: str | None = None
    ) -> XMPSchema:
        """Construct the schema instance and attach it to ``metadata``."""
        try:
            sig = inspect.signature(self._schema_class.__init__)
            params = [p for p in sig.parameters.values() if p.name != "self"]
            args: list = [metadata]
            if self._schema_class is XMPSchema:
                args = [metadata, self._namespace, prefix]
            elif prefix and len(params) >= 2:
                args = [metadata, prefix]
            schema = self._schema_class(*args)
        except Exception as exc:  # pragma: no cover - mirrors Java's broad catch
            raise XmpSchemaException("Cannot instantiate specified object schema") from exc
        metadata.add_schema(schema)
        return schema


__all__ = ["XMPSchemaFactory", "XmpSchemaException"]
