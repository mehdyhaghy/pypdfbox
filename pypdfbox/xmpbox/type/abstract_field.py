from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class Attribute:
    """
    Simple representation of an XML attribute carried by an
    :class:`AbstractField`. Ported from ``org.apache.xmpbox.type.Attribute``.

    Upstream stores ``(namespaceURI, localName, value)`` as plain strings
    and exposes plain getters/setters; this port mirrors that surface.
    The namespace URI may be ``None`` for unqualified attributes.
    """

    def __init__(self, ns_uri: str | None, local_name: str, value: str) -> None:
        self._ns_uri = ns_uri
        self._name = local_name
        self._value = value

    def get_name(self) -> str:
        return self._name

    def set_name(self, lname: str) -> None:
        self._name = lname

    def get_namespace(self) -> str | None:
        return self._ns_uri

    def set_ns_uri(self, ns_uri: str | None) -> None:
        self._ns_uri = ns_uri

    def get_value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value

    def to_string(self) -> str:
        """Mirror upstream ``Attribute.toString()``.

        Upstream format (Java line 121):
        ``"[attr:{" + nsURI + "}" + name + "=" + value + "]"``.
        """
        return f"[attr:{{{self._ns_uri}}}{self._name}={self._value}]"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return self.to_string()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Attribute):
            return NotImplemented
        return (
            self._ns_uri == other._ns_uri
            and self._name == other._name
            and self._value == other._value
        )

    def __hash__(self) -> int:
        return hash((self._ns_uri, self._name, self._value))


class AbstractField(ABC):
    """
    Base class for XMP property representations.

    Ported from ``org.apache.xmpbox.type.AbstractField``. Concrete subclasses
    (:class:`AbstractSimpleProperty`, ``AbstractComplexProperty``) carry the
    namespace/prefix accessors; the base only owns the metadata back-reference,
    the local property name, and the bag of XML attributes.
    """

    def __init__(self, metadata: XMPMetadata, property_name: str | None) -> None:
        self._metadata = metadata
        self._property_name = property_name
        self._attributes: dict[str, Attribute] = {}

    def get_property_name(self) -> str | None:
        return self._property_name

    def set_property_name(self, value: str | None) -> None:
        self._property_name = value

    def set_attribute(self, value: Attribute) -> None:
        self._attributes[value.get_name()] = value

    def contains_attribute(self, qualified_name: str) -> bool:
        return qualified_name in self._attributes

    def get_attribute(self, qualified_name: str) -> Attribute | None:
        return self._attributes.get(qualified_name)

    def get_all_attributes(self) -> list[Attribute]:
        return list(self._attributes.values())

    def remove_attribute(self, qualified_name: str) -> None:
        self._attributes.pop(qualified_name, None)

    def get_metadata(self) -> XMPMetadata:
        return self._metadata

    @abstractmethod
    def get_namespace(self) -> str | None:
        """Return the namespace URI of this property.

        Mirrors upstream ``AbstractField.getNamespace()`` — abstract in Java.
        Concrete subclasses (``AbstractSimpleProperty``, ``ArrayProperty``,
        ``AbstractComplexProperty``) carry the namespace value supplied at
        construction time.
        """

    @abstractmethod
    def get_prefix(self) -> str | None:
        """Return the XML prefix used to serialize this property.

        Mirrors upstream ``AbstractField.getPrefix()`` — abstract in Java.
        Concrete subclasses are responsible for returning the prefix
        recorded at construction time.
        """
