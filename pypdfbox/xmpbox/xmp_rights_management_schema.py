from __future__ import annotations

from typing import TYPE_CHECKING

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

    Properties:

      * ``Certificate`` (Text) — URI to a certificate of authority.
      * ``Marked`` (Boolean) — ``True`` when the resource is rights-managed,
        ``False`` when explicitly placed in the public domain. ``None``
        (the property absent) is distinct from ``False``.
      * ``Owner`` (Bag of Text) — list of legal owners.
      * ``UsageTerms`` (LangAlt) — localized human-readable usage statement.
      * ``WebStatement`` (Text) — URI to a web page describing the rights.
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

    # --- Certificate (Text) ------------------------------------------

    def get_certificate(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CERTIFICATE)

    def set_certificate(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CERTIFICATE)
            return
        self.set_text_property_value(self.CERTIFICATE, value)

    # --- Marked (Boolean) --------------------------------------------

    def get_marked(self) -> bool | None:
        raw = self._properties.get(self.MARKED)
        if raw is None:
            return None
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            # XMP serialises booleans as "True" / "False"; accept the lowercase
            # "true" / "false" forms too because real-world packets use both.
            normalized = raw.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
            return None
        # Fall through to the standard text accessor for parser-stored shapes
        # that may have landed in list/dict form.
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

    # --- Owner (Bag of Text) -----------------------------------------

    def add_owner(self, value: str) -> None:
        self.add_qualified_bag_value(self.OWNER, value)

    def get_owners(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.OWNER)

    def set_owners(self, values: list[str] | None) -> None:
        if values is None:
            self.remove_property(self.OWNER)
            return
        # Replace any existing bag with a fresh list to avoid duplicating items.
        self._properties[self.OWNER] = list(values)

    # --- UsageTerms (LangAlt) ----------------------------------------

    def get_usage_terms(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.USAGE_TERMS, lang)

    def set_usage_terms(self, value: str | None, lang: str = "x-default") -> None:
        if value is None:
            self.remove_property(self.USAGE_TERMS)
            return
        self.set_unqualified_language_property_value(self.USAGE_TERMS, lang, value)

    # --- WebStatement (Text) -----------------------------------------

    def get_web_statement(self) -> str | None:
        return self.get_unqualified_text_property_value(self.WEB_STATEMENT)

    def set_web_statement(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.WEB_STATEMENT)
            return
        self.set_text_property_value(self.WEB_STATEMENT, value)
