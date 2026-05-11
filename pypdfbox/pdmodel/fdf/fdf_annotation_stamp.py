from __future__ import annotations

import base64
import logging
from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

from .fdf_annotation import FDFAnnotation

_log = logging.getLogger(__name__)

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")


class FDFAnnotationStamp(FDFAnnotation):
    """FDF Stamp annotation — ``/Subtype /Stamp``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationStamp`` (Java
    lines 50-424). Stamps may carry an appearance dictionary (``/AP``)
    that XFDF stores as a base64-encoded XML blob.
    """

    SUBTYPE: str = "Stamp"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /AP appearance dictionary ----------

    def set_appearance(self, appearance: COSDictionary | None) -> None:
        """Set the appearance dictionary (``/AP``).

        Mirrors upstream's XFDF appearance assignment (Java line 133:
        ``annot.setItem(COSName.AP, parseStampAnnotationAppearanceXML(...))``).
        Provided here as a direct setter — XFDF appearance-XML decoding is
        omitted because the round-trip path uses native ``COSDictionary``
        appearances rather than XFDF text.
        """
        if appearance is None:
            self._annot.remove_item(_AP)
            return
        self._annot.set_item(_AP, appearance)

    def get_appearance(self) -> COSDictionary | None:
        """Return the appearance dictionary (``/AP``) or ``None``."""
        ap = self._annot.get_dictionary_object(_AP)
        return ap if isinstance(ap, COSDictionary) else None

    def ensure_normal_appearance(self) -> COSStream:
        """Return the existing ``/AP /N`` stream, creating empty entries as
        needed. Mirrors upstream's appearance-dict bootstrap (Java line 146:
        ``dictionary.setItem(COSName.N, new COSStream())``).
        """
        ap = self.get_appearance()
        if ap is None:
            ap = COSDictionary()
            self._annot.set_item(_AP, ap)
        normal = ap.get_dictionary_object(_N)
        if isinstance(normal, COSStream):
            return normal
        new_stream = COSStream()
        ap.set_item(_N, new_stream)
        return new_stream


    # ------------------------------------------------------------------
    # XFDF appearance-XML parsing helpers (mirror upstream's private
    # parse* methods in FDFAnnotationStamp.java)
    # ------------------------------------------------------------------

    def parse_stamp_annotation_appearance_xml(self, xml_text: str) -> COSDictionary | None:
        """Decode a base64-encoded XFDF stamp appearance XML payload into a
        ``COSDictionary``. Mirrors upstream's private
        ``parseStampAnnotationAppearanceXML`` (Java line 133)."""
        if not xml_text:
            return None
        try:
            decoded = base64.b64decode(xml_text)
        except (ValueError, TypeError):
            _log.debug("unable to decode stamp appearance XML")
            return None
        # Best-effort XML → COSDictionary: full XFDF appearance round-trip
        # isn't in scope, so we surface the raw bytes as a stream payload.
        result = COSDictionary()
        appearance_stream = COSStream()
        appearance_stream.set_raw_data(decoded)
        result.set_item(_N, appearance_stream)
        return result

    def parse_dict_element(self, element: Any) -> COSDictionary | None:
        """Parse a ``<dict>`` element from the XFDF appearance XML.
        Mirrors upstream's private ``parseDictElement`` (Java line 234)."""
        if element is None:
            return None
        result = COSDictionary()
        children = getattr(element, "iter", None)
        if children is None:
            return result
        for child in element:
            key = child.get("KEY") if hasattr(child, "get") else None
            if not key:
                continue
            tag = getattr(child, "tag", "").lower() if hasattr(child, "tag") else ""
            value: Any
            if tag.endswith("dict"):
                value = self.parse_dict_element(child)
            elif tag.endswith("array"):
                value = self.parse_array_element(child)
            elif tag.endswith("stream"):
                value = self.parse_stream_element(child)
            else:
                value = child.text if hasattr(child, "text") else None
            if value is not None:
                result.set_item(COSName.get_pdf_name(key), value)
        return result

    def parse_array_element(self, element: Any) -> COSArray | None:
        """Parse an ``<array>`` element from the XFDF appearance XML.
        Mirrors upstream's private ``parseArrayElement`` (Java line 297)."""
        if element is None:
            return None
        result = COSArray()
        for child in element:
            tag = getattr(child, "tag", "").lower() if hasattr(child, "tag") else ""
            value: Any
            if tag.endswith("dict"):
                value = self.parse_dict_element(child)
            elif tag.endswith("array"):
                value = self.parse_array_element(child)
            elif tag.endswith("stream"):
                value = self.parse_stream_element(child)
            else:
                value = child.text if hasattr(child, "text") else None
            if value is not None:
                result.add(value)
        return result

    def parse_stream_element(self, element: Any) -> COSStream | None:
        """Parse a ``<stream>`` element (base64-encoded) from the XFDF
        appearance XML. Mirrors upstream's private ``parseStreamElement``
        (Java line 370)."""
        if element is None:
            return None
        text = element.text if hasattr(element, "text") else None
        if not text:
            return COSStream()
        try:
            payload = base64.b64decode(text)
        except (ValueError, TypeError):
            _log.debug("unable to decode XFDF stream payload")
            return None
        stream = COSStream()
        stream.set_raw_data(payload)
        return stream


__all__ = ["FDFAnnotationStamp"]
