"""Stack-based tracker of XML namespace declarations.

Mirrors the inner class ``DomXmpParser.NamespaceFinder`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/xml/DomXmpParser.java`` lines
1199-1229). Upstream nests this class inside :class:`DomXmpParser`; we
host it as a sibling module so it can be unit-tested in isolation.
"""

from __future__ import annotations

from collections import deque
from xml.dom.minidom import Element

_XMLNS_NS = "http://www.w3.org/2000/xmlns/"


class NamespaceFinder:
    """LIFO stack of ``prefix → URI`` maps from nested elements."""

    def __init__(self) -> None:
        self._stack: deque[dict[str, str]] = deque()

    def push(self, description: Element) -> None:
        """Capture all ``xmlns:*`` attributes declared on ``description``."""
        mapping: dict[str, str] = {}
        attrs = description.attributes
        if attrs is not None:
            for j in range(attrs.length):
                attr = attrs.item(j)
                if attr.namespaceURI == _XMLNS_NS:
                    mapping[attr.localName] = attr.value
        self._stack.appendleft(mapping)

    def pop(self) -> dict[str, str]:
        return self._stack.popleft()

    def contains_namespace(self, namespace: str) -> bool:
        """True if any frame on the stack maps a prefix to ``namespace``."""
        return any(namespace in m.values() for m in self._stack)


__all__ = ["NamespaceFinder"]
