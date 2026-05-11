"""Base class for XMP properties that aggregate sub-fields.

Mirrors ``org.apache.xmpbox.type.AbstractComplexProperty`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/type/AbstractComplexProperty.java``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.xmpbox.type.abstract_field import AbstractField
from pypdfbox.xmpbox.type.complex_property_container import ComplexPropertyContainer

if TYPE_CHECKING:
    from pypdfbox.xmpbox.type.array_property import ArrayProperty
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


class AbstractComplexProperty(AbstractField):
    """Abstract field whose value is a container of sub-fields."""

    def __init__(self, metadata: XMPMetadata, property_name: str | None) -> None:
        super().__init__(metadata, property_name)
        self._container = ComplexPropertyContainer()
        self._namespace_to_prefix: dict[str, str] = {}

    def add_namespace(self, namespace: str, prefix: str) -> None:
        self._namespace_to_prefix[namespace] = prefix

    def get_namespace_prefix(self, namespace: str) -> str | None:
        return self._namespace_to_prefix.get(namespace)

    def get_all_namespaces_with_prefix(self) -> dict[str, str]:
        return self._namespace_to_prefix

    def add_property(self, obj: AbstractField) -> None:
        """Add ``obj`` (replacing any same-name property unless we are an array)."""
        # ``ArrayProperty`` allows multiple ``rdf:li`` siblings.
        from pypdfbox.xmpbox.type.array_property import ArrayProperty

        if not isinstance(self, ArrayProperty):
            self._container.remove_properties_by_name(obj.get_property_name())
        self._container.add_property(obj)

    def remove_property(self, property_: AbstractField) -> None:
        self._container.remove_property(property_)

    def get_container(self) -> ComplexPropertyContainer:
        return self._container

    def get_all_properties(self) -> list[AbstractField]:
        return self._container.get_all_properties()

    def get_property(self, field_name: str) -> AbstractField | None:
        lst = self._container.get_properties_by_local_name(field_name)
        if lst is None:
            return None
        return lst[0]

    def get_array_property(self, field_name: str) -> ArrayProperty | None:
        from pypdfbox.xmpbox.type.array_property import ArrayProperty

        lst = self._container.get_properties_by_local_name(field_name)
        if lst is None:
            return None
        first = lst[0]
        return first if isinstance(first, ArrayProperty) else None

    def get_first_equivalent_property(
        self, local_name: str, type_: type[AbstractField]
    ) -> AbstractField | None:
        return self._container.get_first_equivalent_property(local_name, type_)


__all__ = ["AbstractComplexProperty"]
