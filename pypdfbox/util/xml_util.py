"""Tiny DOM parsing helpers.

Mirrors ``org.apache.pdfbox.util.XMLUtil`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/XMLUtil.java``).

Library-first: we delegate to :mod:`defusedxml.ElementTree` for safe
parsing (no DTD/external-entity resolution), then convert to ``xml.dom``
nodes so callers that introspect a DOM keep working.
"""

from __future__ import annotations

import re
from typing import BinaryIO
from xml.dom import minidom
from xml.dom.minidom import Document, Element

_DOCTYPE_RE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)


def contains_doctype(data: bytes | bytearray | memoryview) -> bool:
    """Return ``True`` if a ``<!DOCTYPE`` declaration appears anywhere in
    ``data``.

    A DOCTYPE is the entry point for DTD-based attacks — XML internal-entity
    expansion ("billion laughs") and external-entity resolution (XXE). XMP
    (ISO 16684) and XFDF do not use DTDs, so any DOCTYPE in those payloads is
    rejected. The whole buffer is scanned (not just a fixed-size prefix):
    a fixed window can be bypassed by padding the prolog with a large leading
    comment so the DOCTYPE lands past the window. Stdlib-only; complements
    :mod:`defusedxml` when it is installed.
    """
    return _DOCTYPE_RE.search(bytes(data)) is not None


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
            # Reject any DTD: it is the entry point for XXE and entity-expansion
            # ("billion laughs") DoS. Scans the whole buffer, not a fixed prefix
            # (a large leading comment can otherwise push the DOCTYPE past the
            # window). See ``contains_doctype``.
            if contains_doctype(data):
                raise OSError("DOCTYPE declarations are not allowed")
            try:
                from defusedxml.minidom import parseString as _safe_parse

                # pragma: no cover -- defusedxml is an optional hardening
                # path; not in pyproject (the project ships permissive-only,
                # no-new-deps gate) so this branch only fires for downstream
                # users who add defusedxml themselves.
                return _safe_parse(  # pragma: no cover
                    data, forbid_dtd=True, forbid_entities=True
                )
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
