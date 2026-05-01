from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class PDFAExtensionSchema(XMPSchema):
    """
    Representation of the PDF/A Extension XMP schema.

    Ported (lite surface) from
    ``org.apache.xmpbox.schema.PDFAExtensionSchema`` (PDFBox 3.0). PDF/A-2/3/4
    documents use this schema to declare any XMP schemas they embed beyond the
    PDF/A-required set. Each declared extension carries a human-readable name,
    a namespace URI, a preferred prefix, and (optionally) the structured
    descriptions of every property and value type it contributes.

    Cluster surface intentionally narrow:

      * The ``pdfaExtension:schemas`` Bag is exposed via dict-shaped accessors
        carrying just ``schema`` / ``namespaceURI`` / ``prefix`` per entry.
      * :meth:`get_schemas_element` exposes the raw underlying property element
        for callers that need the full nested ``pdfaProperty`` / ``pdfaType``
        struct introspection — that typed wrapper lands in a later cluster.
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/extension/"
    PREFERRED_PREFIX = "pdfaExtension"

    # Nested-namespace constants — names match upstream ``public static final``
    # fields. Each describes one struct level inside ``pdfaExtension:schemas``.
    PDFASCHEMA_NAMESPACE = "http://www.aiim.org/pdfa/ns/schema#"
    PDFASCHEMA_PREFIX = "pdfaSchema"
    PDFAPROPERTY_NAMESPACE = "http://www.aiim.org/pdfa/ns/property#"
    PDFAPROPERTY_PREFIX = "pdfaProperty"
    PDFATYPE_NAMESPACE = "http://www.aiim.org/pdfa/ns/type#"
    PDFATYPE_PREFIX = "pdfaType"

    # Local-name constants used by the lite surface.
    SCHEMAS = "schemas"
    SCHEMA = "schema"
    NAMESPACE_URI = "namespaceURI"
    PREFIX = "prefix"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)
        # Register the nested struct namespaces so serialisers (when they land)
        # have the full set of bindings the schema expects to emit.
        self.add_namespace(self.PDFASCHEMA_PREFIX, self.PDFASCHEMA_NAMESPACE)
        self.add_namespace(self.PDFAPROPERTY_PREFIX, self.PDFAPROPERTY_NAMESPACE)
        self.add_namespace(self.PDFATYPE_PREFIX, self.PDFATYPE_NAMESPACE)

    # --- pdfaExtension:schemas Bag — lite struct surface --------------

    def _get_extension_list(self) -> list[dict[str, str]]:
        """
        Return the mutable backing list for ``pdfaExtension:schemas``,
        installing an empty Bag the first time it is read so downstream
        mutators always operate on an in-place container.
        """
        existing = self._properties.get(self.SCHEMAS)
        if isinstance(existing, list) and all(isinstance(item, dict) for item in existing):
            return existing  # type: ignore[return-value]
        if existing is None:
            new_list: list[dict[str, str]] = []
            self._properties[self.SCHEMAS] = new_list
            return new_list
        # Property exists in some other shape (e.g. a list of empty strings
        # from the parser path which currently lacks struct decoding). Surface
        # an empty list rather than raising — the raw element is still
        # available via :meth:`get_schemas_element`.
        return []

    def get_extension_schemas(self) -> list[dict[str, str]]:
        """
        Return a list of dicts describing each declared extension schema. Each
        dict carries the ``schema`` (human-readable name), ``namespaceURI`` and
        ``prefix`` fields. Empty list when no schemas are declared or when the
        underlying property is in an unrecognised shape.
        """
        # Defensive copy — callers should not mutate the schema through the
        # returned reference.
        return [dict(item) for item in self._get_extension_list()]

    def add_extension_schema(self, schema: str, namespace_uri: str, prefix: str) -> None:
        """
        Append a new ``pdfaSchema`` struct to the extension Bag with just the
        three lite-surface fields. Mirrors upstream
        ``addExtensionSchemaDefinition`` for the common-case write path; full
        ``pdfaSchema:property`` / ``pdfaSchema:valueType`` Seqs land later.
        """
        backing = self._get_extension_list()
        backing.append(
            {
                self.SCHEMA: schema,
                self.NAMESPACE_URI: namespace_uri,
                self.PREFIX: prefix,
            }
        )

    def get_schemas_element(self) -> Any | None:
        """
        Expose the raw underlying property element for ``pdfaExtension:schemas``
        so callers needing the full nested struct hierarchy
        (``pdfaSchema:property`` / ``pdfaSchema:valueType`` …) can introspect
        whatever the parser left in place. Returns the stored value as-is, or
        ``None`` when the property is absent.

        In cluster #1 the parser produces a ``list[str]`` of empty strings for
        struct-bearing Bags; this method returns that list verbatim. When the
        typed struct hierarchy lands the return type narrows accordingly —
        callers should treat the value as opaque.
        """
        return self._properties.get(self.SCHEMAS)

    def get_schemas_property(self) -> Any | None:
        """
        Mirror of upstream ``getSchemasProperty()``. Upstream returns the
        ``ArrayProperty`` backing ``pdfaExtension:schemas``; pypdfbox's
        lite-surface stores extension entries as a ``list[dict[str, str]]``
        rather than a typed ``ArrayProperty`` (the typed Bag-of-struct
        wrapper lands in a later cluster), so this method returns whatever
        ``get_schemas_element`` would — kept as a separate method so callers
        coding against the upstream API can find it under the upstream name.
        """
        return self.get_schemas_element()

    def get_count(self) -> int:
        """
        Return the number of extension schemas declared. Mirrors the cardinality
        readers Apache PDFBox tests use to validate the Bag length.
        """
        value = self._properties.get(self.SCHEMAS)
        if isinstance(value, list):
            return len(value)
        return 0
