"""Helper for the PDF/A extension schema validation pass.

Mirrors ``org.apache.xmpbox.xml.PdfaExtensionHelper`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/xml/PdfaExtensionHelper.java``).

Upstream walks the PDF/A extension namespace declarations on an
``rdf:Description`` element and verifies that the prefixes used match the
canonical ``PDFAExtensionSchema`` / ``PDFASchemaType`` / ``PDFAFieldType``
namespaces. The full ``populate_schema_mapping`` logic depends on a stack
of schema/type/field helpers not yet ported individually. This module
ports the public surface (validation entry points + closed/open choice
constants) and leaves the deeper population logic for a future wave.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.dom.minidom import Element

if TYPE_CHECKING:
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


CLOSED_CHOICE = "closed Choice of "
CLOSED_CHOICE_U = "Closed Choice of "
OPEN_CHOICE = "open Choice of "
OPEN_CHOICE_U = "Open Choice of "

_PDFA_EXTENSION_NS = "http://www.aiim.org/pdfa/ns/extension/"
_PDFA_SCHEMA_NS = "http://www.aiim.org/pdfa/ns/schema#"
_PDFA_PROPERTY_NS = "http://www.aiim.org/pdfa/ns/property#"
_PDFA_FIELD_NS = "http://www.aiim.org/pdfa/ns/field#"
_PDFA_TYPE_NS = "http://www.aiim.org/pdfa/ns/type#"

_PREFERRED_PREFIXES = {
    _PDFA_EXTENSION_NS: "pdfaExtension",
    _PDFA_SCHEMA_NS: "pdfaSchema",
    _PDFA_PROPERTY_NS: "pdfaProperty",
    _PDFA_FIELD_NS: "pdfaField",
    _PDFA_TYPE_NS: "pdfaType",
}


class PdfaExtensionHelper:
    """Validator + populator for PDF/A extension namespace declarations."""

    CLOSED_CHOICE = CLOSED_CHOICE
    CLOSED_CHOICE_U = CLOSED_CHOICE_U
    OPEN_CHOICE = OPEN_CHOICE
    OPEN_CHOICE_U = OPEN_CHOICE_U

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("PdfaExtensionHelper is a utility class")

    @staticmethod
    def validate_naming(meta: XMPMetadata, description: Element) -> None:
        """Confirm PDF/A extension prefixes match canonical namespaces.

        Raises :class:`OSError` if a prefix collides with a canonical
        namespace under a different URI.
        """
        attrs = description.attributes
        if attrs is None:
            return
        for i in range(attrs.length):
            attr = attrs.item(i)
            if attr.namespaceURI != "http://www.w3.org/2000/xmlns/":
                continue
            prefix = attr.localName
            uri = attr.value
            for canonical_uri, canonical_prefix in _PREFERRED_PREFIXES.items():
                if uri == canonical_uri and prefix != canonical_prefix:
                    raise OSError(
                        f"Prefix mismatch for {canonical_uri}: "
                        f"expected {canonical_prefix!r}, got {prefix!r}"
                    )
                if prefix == canonical_prefix and uri != canonical_uri:
                    raise OSError(
                        f"Namespace mismatch for prefix {canonical_prefix!r}: "
                        f"expected {canonical_uri}, got {uri}"
                    )

    @staticmethod
    def populate_schema_mapping(
        meta: XMPMetadata, strict_parsing: bool = False
    ) -> None:
        """Register any custom schemas declared in the PDF/A extension.

        The full population routine depends on schema/type populators that
        will be wired up in a follow-up wave. For now this method is a
        no-op so that callers (mainly :class:`DomXmpParser`) can still
        invoke it without raising.
        """
        # Intentional no-op; preserved for upstream API parity.
        _ = meta, strict_parsing

    # --- Private upstream surface, exposed for parity --------------------

    @staticmethod
    def check_namespace_declaration(attr: object, clz: object) -> None:
        """Mirror of ``PdfaExtensionHelper.checkNamespaceDeclaration`` (Java line 78).

        Validates that a single xmlns attribute uses the canonical prefix
        for the namespace URI declared by ``clz``. Raises :class:`OSError`
        on mismatch.
        """
        ns_uri = getattr(attr, "value", None) or getattr(attr, "namespaceURI", None)
        prefix = getattr(attr, "localName", None)
        if ns_uri is None or prefix is None:
            return
        canonical_prefix = _PREFERRED_PREFIXES.get(ns_uri)
        if canonical_prefix is None:
            return
        if prefix != canonical_prefix:
            raise OSError(
                f"Prefix mismatch for {ns_uri}: expected {canonical_prefix!r}, "
                f"got {prefix!r}"
            )

    @staticmethod
    def populate_pdfa_schema_type(
        meta: XMPMetadata, schema_type: object, type_mapping: object, strict_parsing: bool
    ) -> None:
        """Mirror of ``PdfaExtensionHelper.populatePDFASchemaType`` (Java line 147)."""
        # Schema/type populator dependency chain is stubbed; preserve the
        # surface for parity. See the module docstring.
        _ = meta, schema_type, type_mapping, strict_parsing

    @staticmethod
    def populate_pdfa_property_type(
        prop: object, type_mapping: object, schema_factory: object
    ) -> None:
        """Mirror of ``PdfaExtensionHelper.populatePDFAPropertyType`` (Java line 191)."""
        _ = prop, type_mapping, schema_factory

    @staticmethod
    def populate_pdfa_type(
        meta: XMPMetadata, type_obj: object, type_mapping: object
    ) -> None:
        """Mirror of ``PdfaExtensionHelper.populatePDFAType`` (Java line 223)."""
        _ = meta, type_obj, type_mapping

    @staticmethod
    def populate_pdfa_field_type(field: object, structured_type: object) -> None:
        """Mirror of ``PdfaExtensionHelper.populatePDFAFieldType`` (Java line 257)."""
        _ = field, structured_type

    @staticmethod
    def transform_value_type(type_mapping: object, value_type: str) -> object | None:
        """Mirror of ``PdfaExtensionHelper.transformValueType`` (Java line 278)."""
        # Strip the upstream "Closed Choice of " / "Open Choice of " prefixes
        # so callers can resolve the underlying primitive type via the type
        # mapping.
        if not isinstance(value_type, str):
            return None
        for prefix in (CLOSED_CHOICE, CLOSED_CHOICE_U, OPEN_CHOICE, OPEN_CHOICE_U):
            if value_type.startswith(prefix):
                return value_type[len(prefix):]
        return value_type

    @staticmethod
    def require_non_null(value: object, message: object) -> None:
        """Mirror of ``PdfaExtensionHelper.requireNonNull`` (Java line 329).

        Raises :class:`OSError` (the project's stand-in for ``IOException``)
        when ``value`` is ``None``. ``message`` may be a callable supplier
        or a plain string.
        """
        if value is not None:
            return
        text = str(message()) if callable(message) else str(message)
        raise OSError(text)


__all__ = [
    "PdfaExtensionHelper",
    "CLOSED_CHOICE",
    "CLOSED_CHOICE_U",
    "OPEN_CHOICE",
    "OPEN_CHOICE_U",
]
