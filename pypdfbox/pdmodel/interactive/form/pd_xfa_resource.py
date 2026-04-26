from __future__ import annotations

import xml.etree.ElementTree as ET

from pypdfbox.cos import COSArray, COSBase, COSStream


class PDXFAResource:
    """An XML Forms Architecture (XFA) resource. Mirrors PDFBox ``PDXFAResource``.

    The XFA entry on the AcroForm dictionary is either a single ``COSStream``
    containing the entire XFA XML packet, or a ``COSArray`` of alternating
    ``[name, stream, name, stream, ...]`` entries (the tagged-stream form per
    ISO 32000-1:2008 §12.7.8) where each stream carries one XML element.

    ``get_bytes`` mirrors upstream's concatenation behavior; ``get_document``
    parses the concatenated payload into an ``ElementTree`` element (cached
    on the instance).

    Deferred: set helpers and fully-spec is_dynamic detection.
    """

    def __init__(self, xfa: COSBase) -> None:
        self._xfa = xfa
        self._document: ET.Element | None = None

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

    def is_dynamic(self) -> bool:
        """Heuristic dynamic-XFA check.

        Lite scope — looks for a couple of common dynamic-form markers in
        the raw XML bytes (``<xfa:datasets``, ``<xdp:xdp``, or a
        ``subform name="form1"`` declaration). Full spec-driven detection
        (parse the XDP, inspect ``/template/subform/@layout`` etc.) is
        deferred. Returns ``False`` on any I/O error.
        """
        try:
            data = self.get_bytes()
        except OSError:
            return False
        if not data:
            return False
        for marker in (b"<xfa:datasets", b"<xdp:xdp", b'subform name="form1"'):
            if marker in data:
                return True
        return False


__all__ = ["PDXFAResource"]
