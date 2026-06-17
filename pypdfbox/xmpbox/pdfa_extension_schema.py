from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .type.pdfa_field_description_type import PDFAFieldType
    from .type.pdfa_property_type import PDFAPropertyType
    from .type.pdfa_schema_type import PDFASchemaType
    from .type.pdfa_type_type import PDFATypeType
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
        # Typed mirror of ``pdfaExtension:schemas``. Populated only when callers
        # opt into the typed surface via :meth:`add_schema_description`; the
        # lite ``list[dict[str, str]]`` form continues to track the same
        # entries so existing readers (:meth:`get_extension_schemas` /
        # :meth:`get_count`) stay backwards-compatible.
        self._typed_schemas: list[PDFASchemaType] = []
        # Typed mirror of ``pdfaExtension:schemas``. Populated only when callers
        # opt into the typed surface via :meth:`add_schema_description`; the
        # lite ``list[dict[str, str]]`` form continues to track the same
        # entries so existing readers (:meth:`get_extension_schemas` /
        # :meth:`get_count`) stay backwards-compatible.
        self._typed_schemas: list[PDFASchemaType] = []

    # --- pdfaExtension:schemas Bag — lite struct surface --------------

    def _get_extension_list(self, *, create: bool = False) -> list[dict[str, str]]:
        """
        Return the backing list for ``pdfaExtension:schemas``.

        Read paths leave an absent property absent; mutating paths opt into
        creating an empty Bag so they can append in place.
        """
        existing = self._properties.get(self.SCHEMAS)
        if isinstance(existing, list) and all(isinstance(item, dict) for item in existing):
            return cast(list[dict[str, str]], existing)
        if existing is None and create:
            new_list: list[dict[str, str]] = []
            self._properties[self.SCHEMAS] = new_list
            return new_list
        if existing is None:
            return []
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
        backing = self._get_extension_list(create=True)
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

    # --- typed nested-struct surface (wave 1379) ----------------------
    #
    # The lite ``add_extension_schema`` / ``get_extension_schemas`` pair stores
    # entries as ``list[dict[str, str]]`` for backwards-compatibility with the
    # readers and parser path that landed in earlier waves. The typed surface
    # below lets callers opt into the canonical
    # :class:`PDFASchemaType` / :class:`PDFAPropertyType` /
    # :class:`PDFATypeType` / :class:`PDFAFieldType` hierarchy so that the
    # nested ``pdfaSchema:property`` Seq and ``pdfaSchema:valueType`` Seq are
    # introspectable — closing a deferred follow-up for nested
    # struct typing.

    def add_schema_description(self, schema_description: PDFASchemaType) -> str:
        """
        Append a typed :class:`PDFASchemaType` entry to the
        ``pdfaExtension:schemas`` Bag and return the local field name the entry
        was stored under (always ``"li"`` — the upstream RDF array element name,
        matching :data:`AbstractStructuredType.STRUCTURE_ARRAY_NAME`). The
        lite-surface ``list[dict[str, str]]`` is kept in sync so existing
        readers see the same Bag length and ``schema`` / ``namespaceURI`` /
        ``prefix`` slots — only the nested ``property`` / ``valueType`` Seqs
        live exclusively on the typed mirror.

        Mirrors the shape of upstream PDFBox's
        ``PDFAExtensionSchema.addSchemaDescription`` helper paired with
        ``PDFASchemaType.addPropertyDescription`` / ``addValueTypeDescription``.
        """
        self._typed_schemas.append(schema_description)
        backing = self._get_extension_list(create=True)
        backing.append(
            {
                self.SCHEMA: schema_description.get_property_value_as_string(
                    schema_description.SCHEMA
                )
                or "",
                self.NAMESPACE_URI: schema_description.get_namespace_uri() or "",
                self.PREFIX: schema_description.get_prefix_value() or "",
            }
        )
        from .type.abstract_structured_type import STRUCTURE_ARRAY_NAME

        return STRUCTURE_ARRAY_NAME

    def get_schema_descriptions(self) -> list[PDFASchemaType]:
        """
        Return the typed :class:`PDFASchemaType` mirror of
        ``pdfaExtension:schemas``. Empty list when no typed entries have been
        registered (the lite ``add_extension_schema`` path does NOT populate
        the typed mirror — see :meth:`add_schema_description` for the typed
        write path).
        """
        return list(self._typed_schemas)

    def get_typed_schemas(self) -> list[PDFASchemaType]:
        """Alias of :meth:`get_schema_descriptions` keyed under the spec
        ``pdfaExtension:schemas`` local name so callers indexing by that
        attribute find the typed surface symmetrically."""
        return self.get_schema_descriptions()

    def find_schema_by_namespace(
        self, namespace_uri: str
    ) -> PDFASchemaType | None:
        """Return the first typed schema description whose
        ``pdfaSchema:namespaceURI`` matches ``namespace_uri``, or ``None``."""
        for entry in self._typed_schemas:
            if entry.get_namespace_uri() == namespace_uri:
                return entry
        return None

    def find_schema_by_prefix(self, prefix: str) -> PDFASchemaType | None:
        """Return the first typed schema description whose
        ``pdfaSchema:prefix`` matches ``prefix``, or ``None``."""
        for entry in self._typed_schemas:
            if entry.get_prefix_value() == prefix:
                return entry
        return None

    def create_property_type(self) -> PDFAPropertyType:
        """Construct a fresh :class:`PDFAPropertyType` bound to this schema's
        owning metadata. Convenience wrapper so callers don't have to import
        the type module just to populate one entry of the
        ``pdfaSchema:property`` Seq."""
        from .type.pdfa_property_type import PDFAPropertyType

        return PDFAPropertyType(self.get_metadata())

    def create_value_type(self) -> PDFATypeType:
        """Construct a fresh :class:`PDFATypeType` bound to this schema's
        owning metadata. Convenience wrapper for populating one entry of the
        ``pdfaSchema:valueType`` Seq."""
        from .type.pdfa_type_type import PDFATypeType

        return PDFATypeType(self.get_metadata())

    def create_field_type(self) -> PDFAFieldType:
        """Construct a fresh :class:`PDFAFieldType` bound to this schema's
        owning metadata. Convenience wrapper for populating one entry of a
        value type's ``pdfaType:field`` Seq."""
        from .type.pdfa_field_description_type import PDFAFieldType

        return PDFAFieldType(self.get_metadata())

    def create_schema_type(self) -> PDFASchemaType:
        """Construct a fresh :class:`PDFASchemaType` bound to this schema's
        owning metadata. Convenience wrapper for building a typed
        ``pdfaExtension:schemas`` entry before calling
        :meth:`add_schema_description`."""
        from .type.pdfa_schema_type import PDFASchemaType

        return PDFASchemaType(self.get_metadata())
