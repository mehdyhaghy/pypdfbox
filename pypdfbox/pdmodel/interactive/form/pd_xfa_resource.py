from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

from pypdfbox.cos import COSArray, COSBase, COSName, COSStream, COSString


class PDXFAResource:
    """An XML Forms Architecture (XFA) resource. Mirrors PDFBox ``PDXFAResource``.

    The XFA entry on the AcroForm dictionary is either a single ``COSStream``
    containing the entire XFA XML packet, or a ``COSArray`` of alternating
    ``[name, stream, name, stream, ...]`` entries (the tagged-stream form per
    ISO 32000-1:2008 §12.7.8) where each stream carries one XML element.

    ``get_bytes`` mirrors upstream's concatenation behavior; ``get_document``
    parses the concatenated payload into an ``ElementTree`` element (cached
    on the instance).

    Deferred: set helpers.
    """

    # Sentinel for the cached ``is_dynamic`` slot — distinguishes "not yet
    # computed" from a legitimate ``False`` result.
    _IS_DYNAMIC_UNSET: ClassVar[object] = object()

    def __init__(self, xfa: COSBase) -> None:
        self._xfa = xfa
        self._document: ET.Element | None = None
        self._is_dynamic_cache: bool | object = self._IS_DYNAMIC_UNSET

    def get_cos_object(self) -> COSBase:
        return self._xfa

    def get_bytes(self) -> bytes:
        """Return the concatenated XFA XML packet bytes.

        For a ``COSStream``, returns its raw body. For a ``COSArray`` in
        tagged-stream form, returns the concatenation of stream bodies at
        odd indices (skipping the name labels at even indices), in order.
        Returns ``b""`` for any other shape.
        """
        xfa = self._xfa
        if isinstance(xfa, COSArray):
            return self._bytes_from_packet(xfa)
        if isinstance(xfa, COSStream):
            return self._bytes_from_stream(xfa)
        return b""

    @staticmethod
    def _bytes_from_packet(arr: COSArray) -> bytes:
        out = bytearray()
        # Upstream loops i = 1, 3, 5, ... reading the stream half of each pair.
        for i in range(1, arr.size(), 2):
            entry = arr.get_object(i)
            if isinstance(entry, COSStream):
                out.extend(PDXFAResource._bytes_from_stream(entry))
        return bytes(out)

    @staticmethod
    def _bytes_from_stream(stream: COSStream) -> bytes:
        with stream.create_input_stream() as src:
            return src.read()

    def get_xfa_packet(self, name: str) -> bytes | None:
        """Return the bytes of a single XFA packet by name.

        XFA payloads stored in the tagged-stream array form per
        ISO 32000-1 §12.7.8 alternate ``[name, stream, name, stream, ...]``
        where each ``name`` labels the packet that follows (e.g.
        ``"datasets"``, ``"form"``, ``"config"``, ``"template"``,
        ``"xdp"``). This helper locates the entry whose label equals
        ``name`` (matching against ``COSString`` or ``COSName`` labels)
        and returns the body of the immediately-following ``COSStream``.

        Returns ``None`` when:

        - the XFA entry is not in array form (e.g. a single packed
          stream), or
        - no packet labeled ``name`` is present, or
        - the entry following the matching label is not a stream.
        """
        xfa = self._xfa
        if not isinstance(xfa, COSArray):
            return None
        size = xfa.size()
        # Pairs live at (label = i, stream = i+1). Scan even indices.
        for i in range(0, size - 1, 2):
            label = xfa.get_object(i)
            if isinstance(label, COSString):
                label_text: str | None = label.get_string()
            elif isinstance(label, COSName):
                label_text = label.get_name()
            else:
                label_text = None
            if label_text != name:
                continue
            entry = xfa.get_object(i + 1)
            if isinstance(entry, COSStream):
                return self._bytes_from_stream(entry)
            return None
        return None

    def get_document_as_xml(self) -> str:
        """Return the concatenated XFA payload decoded as a UTF-8 string."""
        return self.get_bytes().decode(encoding="utf-8")

    def get_document(self) -> ET.Element:
        """Parse the XFA payload into an ``ElementTree`` element (cached).

        Mirrors upstream PDFBox's ``getDocument()`` which returns a parsed
        W3C ``Document``. Here we return the root ``Element`` from the
        stdlib ``xml.etree.ElementTree`` parser. The result is cached on
        the instance so repeated calls return the same object identity.

        Malformed XML raises ``xml.etree.ElementTree.ParseError`` (the
        stdlib default), which is allowed to propagate to the caller.
        """
        if self._document is None:
            self._document = ET.fromstring(self.get_bytes())
        return self._document

    def get_dom_document(self) -> ET.ElementTree | None:
        """Return the parsed XFA payload as an ``ElementTree`` wrapper.

        Whereas :meth:`get_document` returns the root ``Element`` (and
        propagates parse errors), this returns a full ``ElementTree``
        (which carries root + parse context, matching upstream's W3C
        ``Document`` shape more faithfully) and degrades gracefully:

        - returns ``None`` when the payload is empty (``b""``), and
        - returns ``None`` when the payload is malformed XML (caught
          ``ParseError``) — callers that want strict behavior should use
          :meth:`get_document` instead.

        On success the call also primes :meth:`get_document`'s cache so
        the two views stay in sync.
        """
        data = self.get_bytes()
        if not data:
            return None
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            return None
        # Keep the two accessors in sync so either entry point returns
        # the same parsed Element identity.
        if self._document is None:
            self._document = root
        return ET.ElementTree(self._document)

    def is_dynamic(self) -> bool:
        """Detect a dynamic-XFA payload.

        XFA payloads are wrapped in an ``<xdp:xdp>`` envelope whose top-level
        children are independent "packets" (one per XFA schema: template,
        config, datasets, form, ...). The dynamic/static distinction lives in
        the ``<template>`` packet: dynamic forms declare their root
        ``<subform>`` with a flow ``layout`` attribute (``tb``, ``lr-tb``,
        ``rl-tb``, ``tb-rl``, ...); static forms either set
        ``layout="position"`` or omit the attribute. The XFA template
        namespace is ``http://www.xfa.org/schema/xfa-template/<version>/``.

        Implementation: parse the concatenated payload with stdlib
        ``ElementTree``, locate any ``<template>`` element (namespaced or
        not, directly or as an ``<xdp:xdp>`` child), pick its first
        ``<subform>`` child, and check the ``layout`` attribute. Returns
        ``True`` when the layout is set and not ``"position"``; returns
        ``False`` when it is ``"position"`` or absent.

        On malformed XML, missing ``<template>`` packet, or missing root
        ``<subform>`` we fall back to the previous substring heuristic so
        broken-but-plausibly-dynamic payloads aren't silently downgraded.
        Result is cached on the instance.
        """
        cached = self._is_dynamic_cache
        if cached is not self._IS_DYNAMIC_UNSET:
            return bool(cached)

        result = self._compute_is_dynamic()
        self._is_dynamic_cache = result
        return result

    def _compute_is_dynamic(self) -> bool:
        try:
            data = self.get_bytes()
        except OSError:
            return False
        if not data:
            return False

        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            return self._is_dynamic_substring_heuristic(data)

        template = self._find_template_element(root)
        if template is None:
            return self._is_dynamic_substring_heuristic(data)

        subform = self._find_first_subform(template)
        if subform is None:
            return self._is_dynamic_substring_heuristic(data)

        layout = subform.get("layout")
        if layout is None:
            return False
        return layout != "position"

    @staticmethod
    def _local_name(tag: str) -> str:
        # ElementTree tags are ``{ns}local`` for namespaced elements.
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def _find_template_element(cls, root: ET.Element) -> ET.Element | None:
        # The root may already be the <template> packet (rare — usually it
        # is <xdp:xdp> with packets as children, but defensive-first).
        if cls._local_name(root.tag) == "template":
            return root
        for child in root:
            if cls._local_name(child.tag) == "template":
                return child
        # Last resort: scan the whole tree for any <template> element.
        for elem in root.iter():
            if cls._local_name(elem.tag) == "template":
                return elem
        return None

    @classmethod
    def _find_first_subform(cls, template: ET.Element) -> ET.Element | None:
        for child in template:
            if cls._local_name(child.tag) == "subform":
                return child
        return None

    @staticmethod
    def _is_dynamic_substring_heuristic(data: bytes) -> bool:
        for marker in (b"<xfa:datasets", b"<xdp:xdp", b'subform name="form1"'):
            if marker in data:
                return True
        return False


__all__ = ["PDXFAResource"]
