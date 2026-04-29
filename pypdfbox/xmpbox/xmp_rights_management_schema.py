from __future__ import annotations

from typing import TYPE_CHECKING

from .type import (
    AbstractSimpleProperty,
    ArrayProperty,
    Attribute,
    BooleanType,
    Cardinality,
    LangAlt,
    ProperNameType,
    TextType,
    URIType,
)
from .type.lang_alt import LANG_ATTR_NAME, X_DEFAULT, XML_NS_URI
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPRightsManagementSchema(XMPSchema):
    """
    Representation of the XMP Rights Management schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.XMPRightsManagementSchema`` (PDFBox 3.0).
    Per Adobe XMP Specification Part 1, the namespace is
    ``http://ns.adobe.com/xap/1.0/rights/`` with preferred prefix
    ``xmpRights``. Property local names match upstream constants verbatim.

    Properties (with upstream ``@PropertyType`` annotations):

      * ``Certificate`` (URL, Simple) — URI to a certificate of authority.
      * ``Marked`` (Boolean, Simple) — ``True`` when the resource is
        rights-managed, ``False`` when explicitly placed in the public
        domain. ``None`` (the property absent) is distinct from ``False``.
      * ``Owner`` (ProperName, Bag) — list of legal owners.
      * ``UsageTerms`` (LangAlt, Simple) — localized human-readable usage
        statement.
      * ``WebStatement`` (URL, Simple) — URI to a web page describing the
        rights.

    Each property exposes both the existing string-form accessors (Wave 27,
    e.g. ``set_certificate(str)`` / ``get_certificate() -> str``) and typed
    ``*_property`` accessors mirroring upstream's ``setXxxProperty(Type)`` /
    ``getXxxProperty()``. Both surfaces share the same underlying
    ``self._properties`` storage so a value written through one form is
    visible through the other.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/rights/"
    PREFERRED_PREFIX = "xmpRights"

    # Local-name constants — names match upstream ``public static final`` fields.
    CERTIFICATE = "Certificate"
    MARKED = "Marked"
    OWNER = "Owner"
    USAGE_TERMS = "UsageTerms"
    WEB_STATEMENT = "WebStatement"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # ================================================================
    # Internal helpers — typed-property fabrication / extraction
    # ================================================================

    def _typed_get(
        self, local_name: str, expected: type[AbstractSimpleProperty]
    ) -> AbstractSimpleProperty | None:
        """
        Return the typed wrapper for ``local_name``: if the slot already
        holds an instance of ``expected`` (or any
        :class:`AbstractSimpleProperty`), return it as-is; if it holds a
        plain string/bool from the simple-form setter or parser, wrap it
        on the fly so callers always get a typed view. Returns ``None``
        when the property is absent.
        """
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, expected):
            return raw
        if isinstance(raw, AbstractSimpleProperty):
            # Cross-type request — re-wrap from the string form.
            return expected(
                self._metadata,
                self._namespace,
                self._prefix,
                local_name,
                raw.get_string_value(),
            )
        # Plain str/bool/etc. from the simple-form setter or parser.
        return expected(
            self._metadata, self._namespace, self._prefix, local_name, raw
        )

    def _typed_set(
        self, local_name: str, prop: AbstractSimpleProperty | None
    ) -> None:
        if prop is None:
            self.remove_property(local_name)
            return
        # Mirror upstream addProperty(AbstractField): pin the upstream local
        # name on the field and store the typed instance in the slot.
        prop.set_property_name(local_name)
        self._properties[local_name] = prop

    def _build_owners_array(self) -> ArrayProperty | None:
        """Synthesize a Bag<ProperName> ArrayProperty for the Owner list."""
        items = self.get_unqualified_bag_value_list(self.OWNER)
        if items is None:
            return None
        array = ArrayProperty(
            self._metadata,
            self._namespace,
            self._prefix,
            self.OWNER,
            Cardinality.Bag,
        )
        for item in items:
            if isinstance(item, str):
                array.add_property(
                    ProperNameType(
                        self._metadata,
                        self._namespace,
                        self._prefix,
                        self.OWNER,
                        item,
                    )
                )
        return array

    def _store_owners_array(self, prop: ArrayProperty) -> None:
        """Replace the Owner bag with the children of an ArrayProperty."""
        values: list[str] = []
        for child in prop.get_all_properties():
            if isinstance(child, AbstractSimpleProperty):
                values.append(child.get_string_value())
        self._properties[self.OWNER] = values

    def _build_usage_terms_lang_alt(self) -> LangAlt | None:
        raw = self._properties.get(self.USAGE_TERMS)
        if not isinstance(raw, dict) or not raw:
            return None
        la = LangAlt(
            self._metadata, self._namespace, self._prefix, self.USAGE_TERMS
        )
        keys = list(raw.keys())
        if X_DEFAULT in keys:
            keys.remove(X_DEFAULT)
            keys.insert(0, X_DEFAULT)
        for lang in keys:
            value = raw[lang]
            if not isinstance(value, str):
                continue
            text = TextType(
                self._metadata,
                self._namespace,
                self._prefix,
                self.USAGE_TERMS,
                value,
            )
            text.set_attribute(Attribute(XML_NS_URI, LANG_ATTR_NAME, lang))
            la.add_property(text)
        return la

    def _store_usage_terms_lang_alt(self, prop: ArrayProperty) -> None:
        bucket: dict[str, str] = {}
        for child in prop.get_all_properties():
            if not isinstance(child, TextType):
                continue
            attr = child.get_attribute(LANG_ATTR_NAME)
            lang = attr.get_value() if attr is not None else X_DEFAULT
            bucket[lang] = child.get_string_value()
        self._properties[self.USAGE_TERMS] = bucket

    def _read_text_string(self, local_name: str) -> str | None:
        """
        Reach through either a typed :class:`AbstractSimpleProperty` instance
        installed via a ``set_xxx_property`` call or a plain string written
        by the simple ``set_xxx`` form. Used by the URL / Text string-form
        getters so the two storage forms stay interchangeable.
        """
        raw = self._properties.get(local_name)
        if isinstance(raw, AbstractSimpleProperty):
            value = raw.get_string_value()
            return value if isinstance(value, str) else None
        return self.get_unqualified_text_property_value(local_name)

    # --- Certificate (URL / TextType-derived) ------------------------

    def get_certificate(self) -> str | None:
        return self._read_text_string(self.CERTIFICATE)

    def set_certificate(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CERTIFICATE)
            return
        self.set_text_property_value(self.CERTIFICATE, value)

    def get_certificate_property(self) -> URIType | None:
        result = self._typed_get(self.CERTIFICATE, URIType)
        return result if isinstance(result, URIType) else None

    def set_certificate_property(self, value: URIType | None) -> None:
        self._typed_set(self.CERTIFICATE, value)

    # --- Marked (Boolean) --------------------------------------------

    def get_marked(self) -> bool | None:
        raw = self._properties.get(self.MARKED)
        if raw is None:
            return None
        if isinstance(raw, BooleanType):
            return raw.get_value()
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, AbstractSimpleProperty):
            text = raw.get_string_value()
        elif isinstance(raw, str):
            text = raw
        else:
            text = self.get_unqualified_text_property_value(self.MARKED)
        if text is None:
            return None
        normalized = text.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        return None

    def set_marked(self, value: bool | None) -> None:
        if value is None:
            self.remove_property(self.MARKED)
            return
        # Upstream serialises BooleanType as "True" / "False" (capitalised).
        self.set_text_property_value(self.MARKED, "True" if value else "False")

    def get_marked_property(self) -> BooleanType | None:
        result = self._typed_get(self.MARKED, BooleanType)
        return result if isinstance(result, BooleanType) else None

    def set_marked_property(self, value: BooleanType | None) -> None:
        self._typed_set(self.MARKED, value)

    # --- Owner (Bag of ProperName) -----------------------------------

    def add_owner(self, value: str) -> None:
        self.add_qualified_bag_value(self.OWNER, value)

    def remove_owner(self, value: str) -> None:
        """Mirror of upstream ``removeOwner(String)``."""
        raw = self._properties.get(self.OWNER)
        if isinstance(raw, ArrayProperty):
            kept = ArrayProperty(
                self._metadata,
                self._namespace,
                self._prefix,
                self.OWNER,
                Cardinality.Bag,
            )
            for child in raw.get_all_properties():
                if not isinstance(child, AbstractSimpleProperty):
                    kept.add_property(child)
                    continue
                if child.get_string_value() != value:
                    kept.add_property(child)
            self._properties[self.OWNER] = kept
            return
        self.remove_unqualified_bag_value(self.OWNER, value)

    def get_owners(self) -> list[str] | None:
        raw = self._properties.get(self.OWNER)
        if isinstance(raw, ArrayProperty):
            # A typed setter may have installed an ArrayProperty directly.
            return [
                child.get_string_value()
                for child in raw.get_all_properties()
                if isinstance(child, AbstractSimpleProperty)
            ]
        if isinstance(raw, list):
            return [
                item.get_string_value()
                if isinstance(item, AbstractSimpleProperty)
                else item
                for item in raw
                if isinstance(item, (str, AbstractSimpleProperty))
            ]
        return self.get_unqualified_bag_value_list(self.OWNER)

    def set_owners(self, values: list[str] | None) -> None:
        if values is None:
            self.remove_property(self.OWNER)
            return
        # Replace any existing bag with a fresh list to avoid duplicating items.
        self._properties[self.OWNER] = list(values)

    def get_owners_property(self) -> ArrayProperty | None:
        return self._build_owners_array()

    def set_owners_property(self, prop: ArrayProperty | None) -> None:
        if prop is None:
            self.remove_property(self.OWNER)
            return
        self._store_owners_array(prop)

    # --- UsageTerms (LangAlt) ----------------------------------------

    def get_usage_terms(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.USAGE_TERMS, lang)

    def set_usage_terms(self, value: str | None, lang: str = "x-default") -> None:
        if value is None:
            self.remove_property(self.USAGE_TERMS)
            return
        self.set_unqualified_language_property_value(self.USAGE_TERMS, lang, value)

    def add_usage_terms(self, lang: str | None, value: str) -> None:
        """Mirror of upstream ``addUsageTerms(String, String)``."""
        self.set_unqualified_language_property_value(self.USAGE_TERMS, lang, value)

    def get_usage_terms_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(
            self.USAGE_TERMS
        )

    def get_usage_terms_property(self) -> LangAlt | None:
        return self._build_usage_terms_lang_alt()

    def set_usage_terms_property(self, prop: ArrayProperty | None) -> None:
        if prop is None:
            self.remove_property(self.USAGE_TERMS)
            return
        self._store_usage_terms_lang_alt(prop)

    # --- WebStatement (URL / TextType-derived) -----------------------

    def get_web_statement(self) -> str | None:
        return self._read_text_string(self.WEB_STATEMENT)

    def set_web_statement(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.WEB_STATEMENT)
            return
        self.set_text_property_value(self.WEB_STATEMENT, value)

    def get_web_statement_property(self) -> URIType | None:
        result = self._typed_get(self.WEB_STATEMENT, URIType)
        return result if isinstance(result, URIType) else None

    def set_web_statement_property(self, value: URIType | None) -> None:
        self._typed_set(self.WEB_STATEMENT, value)
