from __future__ import annotations

import contextlib
from enum import Enum
from typing import TYPE_CHECKING

from .abstract_field import AbstractField
from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class Cardinality(Enum):
    """
    Ported from ``org.apache.xmpbox.type.Cardinality``. ``Simple`` is the
    scalar-property marker; the three array flavours are ``Bag`` (unordered),
    ``Seq`` (ordered) and ``Alt`` (alternative — language alternatives, etc).
    """

    Simple = False
    Bag = True
    Seq = True
    Alt = True

    def is_array(self) -> bool:
        return bool(self.value)


class ArrayProperty(AbstractField):
    """
    XMP array property representation, used for ``rdf:Bag`` / ``rdf:Seq`` /
    ``rdf:Alt`` containers.

    Ported from ``org.apache.xmpbox.type.ArrayProperty``. Children are
    :class:`AbstractField` instances (typically :class:`AbstractSimpleProperty`
    or nested :class:`ArrayProperty`); the upstream ``ComplexPropertyContainer``
    is folded into a plain Python list here because the only operations
    pypdfbox needs are append / iterate / by-name lookup.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace: str | None,
        prefix: str | None,
        property_name: str,
        array_type: Cardinality,
    ) -> None:
        super().__init__(metadata, property_name)
        self._array_type = array_type
        self._namespace = namespace
        self._prefix = prefix
        self._properties: list[AbstractField] = []
        self._namespace_to_prefix: dict[str, str] = {}

    def get_array_type(self) -> Cardinality:
        return self._array_type

    def get_namespace(self) -> str | None:
        return self._namespace

    def get_prefix(self) -> str | None:
        return self._prefix

    def add_property(self, obj: AbstractField) -> None:
        # Upstream's AbstractComplexProperty.addProperty removes existing
        # properties with the same local name unless `this instanceof
        # ArrayProperty` — array containers append, so we mirror that here.
        self._properties.append(obj)

    def remove_property(self, prop: AbstractField) -> None:
        with contextlib.suppress(ValueError):
            self._properties.remove(prop)

    def get_all_properties(self) -> list[AbstractField]:
        return list(self._properties)

    def get_properties_by_local_name(
        self, local_name: str
    ) -> list[AbstractField] | None:
        """
        Return all child properties whose local name matches ``local_name``,
        or ``None`` if there are none. Mirrors
        ``ComplexPropertyContainer.getPropertiesByLocalName`` upstream — note
        that upstream returns ``null`` (not an empty list) when nothing matches.
        """
        matches = [
            p for p in self._properties if p.get_property_name() == local_name
        ]
        if not matches:
            return None
        return matches

    def get_property(self, field_name: str) -> AbstractField | None:
        """
        Return the first child property with the given local name, or ``None``
        if no match. Mirrors ``AbstractComplexProperty.getProperty`` upstream.
        """
        matches = self.get_properties_by_local_name(field_name)
        if matches is None:
            return None
        return matches[0]

    def get_array_property(self, field_name: str) -> ArrayProperty | None:
        """
        Return the first nested :class:`ArrayProperty` child with the given
        local name, or ``None``. Mirrors
        ``AbstractComplexProperty.getArrayProperty`` upstream — upstream casts
        unconditionally and would raise ``ClassCastException`` on a non-array
        match; we return ``None`` to keep the call site type-safe.
        """
        prop = self.get_property(field_name)
        if isinstance(prop, ArrayProperty):
            return prop
        return None

    def add_namespace(self, namespace: str, prefix: str | None) -> None:
        """
        Register an additional ``namespace -> prefix`` binding. Mirrors
        ``AbstractComplexProperty.addNamespace`` upstream.
        """
        self._namespace_to_prefix[namespace] = prefix or ""

    def get_namespace_prefix(self, namespace: str) -> str | None:
        """
        Look up the prefix previously registered for ``namespace`` via
        :meth:`add_namespace`, or ``None``. Mirrors
        ``AbstractComplexProperty.getNamespacePrefix`` upstream.
        """
        return self._namespace_to_prefix.get(namespace)

    def get_all_namespaces_with_prefix(self) -> dict[str, str]:
        """
        Return the live ``namespace -> prefix`` map. Mirrors
        ``AbstractComplexProperty.getAllNamespacesWithPrefix`` upstream.
        """
        return self._namespace_to_prefix

    def get_elements_as_string(self) -> list[str]:
        result: list[str] = []
        for child in self._properties:
            if isinstance(child, AbstractSimpleProperty):
                result.append(child.get_string_value())
        return result
