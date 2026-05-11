"""Tiny DOM parsing helpers.

Mirrors ``org.apache.pdfbox.util.XMLUtil`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/XMLUtil.java``).

Library-first: we delegate to :mod:`defusedxml.ElementTree` for safe
parsing (no DTD/external-entity resolution), then convert to ``xml.dom``
nodes so callers that introspect a DOM keep working.
"""

from __future__ import annotations

from typing import BinaryIO
from xml.dom import minidom
from xml.dom.minidom import Document, Element


def _read_all(stream: BinaryIO | bytes | bytearray) -> bytes:
    if isinstance(stream, (bytes, bytearray)):
        return bytes(stream)
    return stream.read()


class XMLUtil:
    """Static helpers."""

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("XMLUtil is a utility class")

    @staticmethod
    def parse(stream: BinaryIO | bytes | bytearray, ns_aware: bool = False) -> Document:
        """Parse an XML byte stream and return a DOM document.

        Disallows DOCTYPE declarations to match upstream's hardened
        ``DocumentBuilderFactory`` flags. When :mod:`defusedxml` is on the
        path we prefer it; otherwise we fall back to :mod:`xml.dom.minidom`
        with an explicit DOCTYPE check on the input bytes.
        """
        try:
            data = _read_all(stream)
            # Guard against the most common XXE vector: an external DOCTYPE.
            head = data[:2048].lstrip().lower()
            if b"<!doctype" in head:
                raise OSError("DOCTYPE declarations are not allowed")
            try:
                from defusedxml.minidom import parseString as _safe_parse

                return _safe_parse(data, forbid_dtd=True, forbid_entities=True)
            except ImportError:
                return minidom.parseString(data)
        except OSError:
            raise
        except Exception as exc:
            raise OSError(str(exc)) from exc

    @staticmethod
    def get_node_value(node: Element) -> str:
        """Return concatenated direct text-node children of ``node``."""
        parts: list[str] = []
        for child in node.childNodes:
            if child.nodeType == minidom.Node.TEXT_NODE:
                parts.append(child.nodeValue or "")
        return "".join(parts)


__all__ = ["XMLUtil"]
