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

    # pypdfbox enrichment — frozenset of the local names this schema models.
    # Useful for callers that want to iterate the full property surface (e.g.
    # diagnostics / round-trip snapshotting via :meth:`get_known_properties`)
    # without hard-coding the three names. Upstream PDFBox has no equivalent
    # collection — this is a small Pythonic convenience.
    KNOWN_PROPERTIES: frozenset[str] = frozenset({KEYWORDS, PDF_VERSION, PRODUCER})

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

    # --- predicate helpers -------------------------------------------
    #
    # pypdfbox enrichments — upstream PDFBox callers tend to read with
    # ``getXxx() != null``; these short predicates make pypdfbox call sites
    # read more naturally and keep the "absent vs. empty-string" distinction
    # explicit. ``has_xxx`` returns ``True`` only when the local name is
    # actually present in the property store; an empty-string value still
    # counts as "set" since upstream's ``getProperty`` would also surface it.

    def has_keywords(self) -> bool:
        """Return ``True`` when ``pdf:Keywords`` is set on this schema."""
        return self.KEYWORDS in self._properties

    def has_pdf_version(self) -> bool:
        """Return ``True`` when ``pdf:PDFVersion`` is set on this schema."""
        return self.PDF_VERSION in self._properties

    def has_producer(self) -> bool:
        """Return ``True`` when ``pdf:Producer`` is set on this schema."""
        return self.PRODUCER in self._properties

    # --- bulk operations ---------------------------------------------

    def clear(self) -> None:
        """
        Remove every property modelled by this schema (``Keywords``,
        ``PDFVersion``, ``Producer``). pypdfbox enrichment — upstream callers
        normally call each ``setXxx(null)`` individually; this short cut
        matches the way real-world rewriters (sanitisers / PDF/A
        conditioners) clear the entire ``pdf:`` block before re-emitting.
        Properties not modelled by this schema (e.g. parser-deposited ones)
        are left untouched.
        """
        for local_name in self.KNOWN_PROPERTIES:
            self._properties.pop(local_name, None)
            self._typed_properties.pop(local_name, None)

    def get_known_properties(self) -> dict[str, str]:
        """
        Return a dict snapshot of every modelled property currently set on
        this schema, keyed by upstream local name (``"Keywords"`` /
        ``"PDFVersion"`` / ``"Producer"``). Absent properties are omitted —
        the dict reflects only what's actually populated. pypdfbox
        enrichment, mainly useful for diagnostics, round-trip assertions,
        and quick equality comparisons across two ``AdobePDFSchema``
        instances. Values are coerced to ``str`` so the dict is JSON-safe;
        callers needing the typed wrappers should fall back to the
        ``get_xxx_property`` accessors.
        """
        snapshot: dict[str, str] = {}
        for local_name in self.KNOWN_PROPERTIES:
            value = self._properties.get(local_name)
            if value is None:
                continue
            if isinstance(value, TextType):
                snapshot[local_name] = value.get_string_value()
            else:
                snapshot[local_name] = str(value)
        return snapshot
