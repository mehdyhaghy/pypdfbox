from __future__ import annotations

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

    def getName(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_name()

    def set_name(self, lname: str) -> None:
        self._name = lname

    def setName(self, lname: str) -> None:  # noqa: N802 - upstream Java name
        self.set_name(lname)

    def get_namespace(self) -> str | None:
        return self._ns_uri

    def getNamespace(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_namespace()

    def set_ns_uri(self, ns_uri: str | None) -> None:
        self._ns_uri = ns_uri

    def setNsURI(self, ns_uri: str | None) -> None:  # noqa: N802 - upstream Java name
        self.set_ns_uri(ns_uri)

    def get_value(self) -> str:
        return self._value

    def getValue(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_value()

    def set_value(self, value: str) -> None:
        self._value = value

    def setValue(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_value(value)

    def __repr__(self) -> str:
        return f"[attr:{{{self._ns_uri}}}{self._name}={self._value}]"

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


class AbstractField:
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

    def getPropertyName(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_property_name()

    def set_property_name(self, value: str | None) -> None:
        self._property_name = value

    def setPropertyName(self, value: str | None) -> None:  # noqa: N802
        self.set_property_name(value)

    def set_attribute(self, value: Attribute) -> None:
        self._attributes[value.get_name()] = value

    def setAttribute(self, value: Attribute) -> None:  # noqa: N802
        self.set_attribute(value)

    def contains_attribute(self, qualified_name: str) -> bool:
        return qualified_name in self._attributes

    def containsAttribute(self, qualified_name: str) -> bool:  # noqa: N802
        return self.contains_attribute(qualified_name)

    def get_attribute(self, qualified_name: str) -> Attribute | None:
        return self._attributes.get(qualified_name)

    def getAttribute(self, qualified_name: str) -> Attribute | None:  # noqa: N802
        return self.get_attribute(qualified_name)

    def get_all_attributes(self) -> list[Attribute]:
        return list(self._attributes.values())

    def getAllAttributes(self) -> list[Attribute]:  # noqa: N802
        return self.get_all_attributes()

    def remove_attribute(self, qualified_name: str) -> None:
        self._attributes.pop(qualified_name, None)

    def removeAttribute(self, qualified_name: str) -> None:  # noqa: N802
        self.remove_attribute(qualified_name)

    def get_metadata(self) -> XMPMetadata:
        return self._metadata

    def getMetadata(self) -> XMPMetadata:  # noqa: N802 - upstream Java name
        return self.get_metadata()

    def get_namespace(self) -> str | None:
        raise NotImplementedError

    def get_prefix(self) -> str | None:
        raise NotImplementedError
