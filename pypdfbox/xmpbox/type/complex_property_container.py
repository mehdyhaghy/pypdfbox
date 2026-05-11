"""Container for a list of XMP ``AbstractField`` properties.

Mirrors ``org.apache.xmpbox.type.ComplexPropertyContainer`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/type/ComplexPropertyContainer.java``).
"""

from __future__ import annotations

import contextlib

from pypdfbox.xmpbox.type.abstract_field import AbstractField


class ComplexPropertyContainer:
    """Ordered list of :class:`AbstractField` objects."""

    def __init__(self) -> None:
        self._properties: list[AbstractField] = []

    def get_first_equivalent_property(
        self, local_name: str, type_: type[AbstractField]
    ) -> AbstractField | None:
        lst = self.get_properties_by_local_name(local_name)
        if lst is None:
            return None
        for field in lst:
            if type(field) is type_:
                return field
        return None

    def add_property(self, obj: AbstractField) -> None:
        """Append ``obj`` after removing any prior identical reference."""
        self.remove_property(obj)
        self._properties.append(obj)

    def get_all_properties(self) -> list[AbstractField]:
        return self._properties

    def get_properties_by_local_name(self, local_name: str) -> list[AbstractField] | None:
        lst = [f for f in self._properties if f.get_property_name() == local_name]
        if not lst:
            return None
        return lst

    def is_same_property(self, prop1: AbstractField, prop2: AbstractField) -> bool:
        if type(prop1) is not type(prop2):
            return False
        pn1 = prop1.get_property_name()
        pn2 = prop2.get_property_name()
        if pn1 is None:
            return pn2 is None
        if pn1 != pn2:
            return False
        return prop1 == prop2

    def contains_property(self, property_: AbstractField) -> bool:
        return any(self.is_same_property(p, property_) for p in self._properties)

    def remove_property(self, property_: AbstractField) -> None:
        with contextlib.suppress(ValueError):
            self._properties.remove(property_)

    def remove_properties_by_name(self, local_name: str) -> None:
        if not self._properties:
            return
        prop_list = self.get_properties_by_local_name(local_name)
        if prop_list is None:
            return
        for prop in prop_list:
            with contextlib.suppress(ValueError):
                self._properties.remove(prop)


__all__ = ["ComplexPropertyContainer"]
