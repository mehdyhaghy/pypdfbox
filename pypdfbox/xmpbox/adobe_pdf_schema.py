from __future__ import annotations

from typing import TYPE_CHECKING

from .type.text_type import TextType
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class AdobePDFSchema(XMPSchema):
    """
    Representation of the Adobe PDF schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.AdobePDFSchema`` (PDFBox 3.0). Per the
    ``@StructuredType`` annotation, the namespace is
    ``http://ns.adobe.com/pdf/1.3/`` with preferred prefix ``pdf``. Property
    local names match upstream ``public static final`` constants verbatim.

    Properties:

      * ``Keywords`` (Text) — keywords associated with the document.
      * ``PDFVersion`` (Text) — PDF spec version, e.g. ``"1.4"``.
      * ``Producer`` (Text) — name of the tool that produced the PDF.

    Each property is exposed via two pairs of accessors mirroring upstream:

      * String-form (``set_keywords(str)`` / ``get_keywords() -> str``) —
        accepts/returns plain ``str`` values, matching the upstream
        ``setKeywords(String)`` / ``getKeywords()`` overloads.
      * Typed-form (``set_keywords_property(TextType)`` /
        ``get_keywords_property() -> TextType | None``) — accepts/returns the
        :class:`~pypdfbox.xmpbox.type.text_type.TextType` field instance,
        matching upstream's ``setKeywordsProperty(TextType)`` /
        ``getKeywordsProperty()``.
    """

    NAMESPACE = "http://ns.adobe.com/pdf/1.3/"
    PREFERRED_PREFIX = "pdf"

    KEYWORDS = "Keywords"
    PDF_VERSION = "PDFVersion"
    PRODUCER = "Producer"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)
        # Typed property cache. The string-form path stores plain ``str`` values
        # in ``self._properties`` for parity with cluster #1; this side-table
        # captures the originating ``TextType`` instance when callers go
        # through the typed setters, so the typed getter can hand back the same
        # object on round-trip. The string-form value remains authoritative —
        # callers that mutate via ``set_keywords(str)`` after handing in a
        # ``TextType`` will see the typed cache invalidated.
        self._typed_properties: dict[str, TextType] = {}

    # --- internal helpers --------------------------------------------

    def _set_text_property(self, local_name: str, prop: TextType | None) -> None:
        if prop is None:
            self._properties.pop(local_name, None)
            self._typed_properties.pop(local_name, None)
            return
        if not isinstance(prop, TextType):
            raise TypeError(
                f"{local_name} must be a TextType, got {type(prop).__name__}"
            )
        # Mirror upstream: the typed setter stores the TextType's string value
        # in the underlying property store (so string-form readers see it) and
        # also caches the typed instance for typed-form readers.
        self._properties[local_name] = prop.get_string_value()
        self._typed_properties[local_name] = prop

    def _get_text_property(self, local_name: str) -> TextType | None:
        cached = self._typed_properties.get(local_name)
        value = self._properties.get(local_name)
        if cached is not None and value == cached.get_string_value():
            return cached
        # Either no typed instance was ever installed, or the string-form
        # setter overwrote the value out from under it. Fall back to lazily
        # rehydrating a TextType wrapping whatever the string store currently
        # holds — matches upstream ``getXxxProperty()`` returning a freshly
        # built field when none was explicitly attached.
        if isinstance(value, str):
            rehydrated = TextType(
                self._metadata, self._namespace, self._prefix, local_name, value
            )
            self._typed_properties[local_name] = rehydrated
            return rehydrated
        return None

    # --- Keywords (Text) ---------------------------------------------

    def set_keywords(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.KEYWORDS)
            self._typed_properties.pop(self.KEYWORDS, None)
            return
        self.set_text_property_value(self.KEYWORDS, value)
        # Invalidate any stale typed cache — the string-form path is now
        # authoritative.
        self._typed_properties.pop(self.KEYWORDS, None)

    def get_keywords(self) -> str | None:
        return self.get_unqualified_text_property_value(self.KEYWORDS)

    def set_keywords_property(self, prop: TextType | None) -> None:
        self._set_text_property(self.KEYWORDS, prop)

    def get_keywords_property(self) -> TextType | None:
        return self._get_text_property(self.KEYWORDS)

    # --- PDFVersion (Text) -------------------------------------------

    def set_pdf_version(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.PDF_VERSION)
            self._typed_properties.pop(self.PDF_VERSION, None)
            return
        self.set_text_property_value(self.PDF_VERSION, value)
        self._typed_properties.pop(self.PDF_VERSION, None)

    def get_pdf_version(self) -> str | None:
        return self.get_unqualified_text_property_value(self.PDF_VERSION)

    def set_pdf_version_property(self, prop: TextType | None) -> None:
        self._set_text_property(self.PDF_VERSION, prop)

    def get_pdf_version_property(self) -> TextType | None:
        return self._get_text_property(self.PDF_VERSION)

    # --- Producer (Text) ---------------------------------------------

    def set_producer(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.PRODUCER)
            self._typed_properties.pop(self.PRODUCER, None)
            return
        self.set_text_property_value(self.PRODUCER, value)
        self._typed_properties.pop(self.PRODUCER, None)

    def get_producer(self) -> str | None:
        return self.get_unqualified_text_property_value(self.PRODUCER)

    def set_producer_property(self, prop: TextType | None) -> None:
        self._set_text_property(self.PRODUCER, prop)

    def get_producer_property(self) -> TextType | None:
        return self._get_text_property(self.PRODUCER)
