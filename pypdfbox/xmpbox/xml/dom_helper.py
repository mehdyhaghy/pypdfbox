"""DOM walking helpers for the XMP parser.

Mirrors ``org.apache.xmpbox.xml.DomHelper`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/xml/DomHelper.java``).
"""

from __future__ import annotations

from xml.dom.minidom import Element, Node

from pypdfbox.xmpbox.xmp_metadata import (
    DEFAULT_RDF_PREFIX,
    DESCRIPTION_NAME,
    PARSE_TYPE,
    RDF_NAMESPACE,
    RESOURCE_NAME,
)


class DomHelper:
    """Static-only DOM utility helpers used by the XMP parser."""

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("DomHelper is a utility class")

    @staticmethod
    def get_unique_element_child(description: Element) -> Element | None:
        """Return the single Element child of ``description``.

        Raises :class:`OSError` if more than one element child is present.
        """
        children = description.childNodes
        pos = -1
        for i, child in enumerate(children):
            if child.nodeType == Node.ELEMENT_NODE:
                if pos >= 0:
                    raise OSError(f"Found two child elements in {description}")
                pos = i
        if pos < 0:
            return None
        return children[pos]

    @staticmethod
    def get_first_child_element(description: Element) -> Element | None:
        """Return the first child Element of ``description``, or ``None``."""
        for child in description.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                return child
        return None

    @staticmethod
    def get_element_children(description: Element) -> list[Element]:
        return [c for c in description.childNodes if c.nodeType == Node.ELEMENT_NODE]

    @staticmethod
    def get_qname(element: Element) -> tuple[str | None, str, str | None]:
        """Return ``(namespaceURI, localName, prefix)`` triple."""
        return (element.namespaceURI, element.localName, element.prefix)

    @staticmethod
    def get_q_name(element: Element) -> tuple[str | None, str, str | None]:
        """Parity alias matching upstream snake-case of ``getQName``."""
        return DomHelper.get_qname(element)

    @staticmethod
    def is_rdf_description(element: Element) -> bool:
        """True if ``element`` is ``rdf:Description``."""
        return (
            element.prefix == DEFAULT_RDF_PREFIX
            and element.localName == DESCRIPTION_NAME
        )

    @staticmethod
    def is_parse_type_resource(element: Element) -> bool:
        """True if ``element`` carries ``rdf:parseType="Resource"``."""
        parse_type = element.getAttributeNS(RDF_NAMESPACE, PARSE_TYPE)
        return parse_type == RESOURCE_NAME


__all__ = ["DomHelper"]
