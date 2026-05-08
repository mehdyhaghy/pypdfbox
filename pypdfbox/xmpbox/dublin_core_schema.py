from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from .type import (
    AbstractSimpleProperty,
    ArrayProperty,
    Attribute,
    Cardinality,
    DateType,
    LangAlt,
    MIMEType,
    ProperNameType,
    TextType,
)
from .type.lang_alt import LANG_ATTR_NAME, X_DEFAULT, XML_NS_URI
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class DublinCoreSchema(XMPSchema):
    """
    Representation of a Dublin Core XMP schema.

    Ported from ``org.apache.xmpbox.schema.DublinCoreSchema`` (PDFBox 3.0).
    Property local names match upstream constants verbatim.

    The string-form accessors (``get_title``, ``get_creators``,
    ``set_format`` …) remain for back-compat. Typed ``*Property`` accessors
    that mirror upstream's :class:`TextType` / :class:`ArrayProperty` /
    :class:`LangAlt` surface — added in Wave 32 on top of the
    :mod:`pypdfbox.xmpbox.type` foundation — are now available alongside.
    Both surfaces share the same underlying storage, so a value written via
    one is visible to the other.
    """

    NAMESPACE = "http://purl.org/dc/elements/1.1/"
    PREFERRED_PREFIX = "dc"

    # Local-name constants — names match upstream ``public static final`` fields.
    CONTRIBUTOR = "contributor"
    COVERAGE = "coverage"
    CREATOR = "creator"
    DATE = "date"
    DESCRIPTION = "description"
    FORMAT = "format"
    IDENTIFIER = "identifier"
    LANGUAGE = "language"
    PUBLISHER = "publisher"
    RELATION = "relation"
    RIGHTS = "rights"
    SOURCE = "source"
    SUBJECT = "subject"
    TITLE = "title"
    TYPE = "type"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # ================================================================
    # Internal helpers — typed-property fabrication / extraction
    # ================================================================

    def _make_text(self, name: str, value: str) -> TextType:
        return TextType(
            self._metadata, self._namespace, self._prefix, name, value
        )

    def _make_proper_name(self, name: str, value: str) -> ProperNameType:
        return ProperNameType(
            self._metadata, self._namespace, self._prefix, name, value
        )

    def _make_mime_type(self, name: str, value: str) -> MIMEType:
        return MIMEType(
            self._metadata, self._namespace, self._prefix, name, value
        )

    def _make_date(self, name: str, value: datetime | str) -> DateType:
        return DateType(
            self._metadata, self._namespace, self._prefix, name, value
        )

    def _build_text_property(
        self, local_name: str, factory: Callable[[str, str], TextType]
    ) -> TextType | None:
        """Synthesize a typed simple wrapper from the stored string."""
        value = self.get_unqualified_text_property_value(local_name)
        if value is None:
            return None
        return factory(local_name, value)

    def _build_array_of_text(
        self,
        local_name: str,
        cardinality: Cardinality,
        factory: Callable[[str, str], AbstractSimpleProperty],
    ) -> ArrayProperty | None:
        items = self.get_unqualified_array_list(local_name)
        if items is None:
            return None
        array = ArrayProperty(
            self._metadata, self._namespace, self._prefix, local_name, cardinality
        )
        for item in items:
            if isinstance(item, str):
                array.add_property(factory(local_name, item))
        return array

    def _build_array_of_date(self, local_name: str) -> ArrayProperty | None:
        items = self.get_unqualified_array_list(local_name)
        if items is None:
            return None
        array = ArrayProperty(
            self._metadata,
            self._namespace,
            self._prefix,
            local_name,
            Cardinality.Seq,
        )
        for item in items:
            if isinstance(item, str):
                array.add_property(self._make_date(local_name, item))
        return array

    def _build_lang_alt(self, local_name: str) -> LangAlt | None:
        raw = self._properties.get(local_name)
        if not isinstance(raw, dict) or not raw:
            return None
        la = LangAlt(self._metadata, self._namespace, self._prefix, local_name)
        # Insert x-default first (mirrors LangAlt._reorganize_alt_order).
        keys = list(raw.keys())
        if X_DEFAULT in keys:
            keys.remove(X_DEFAULT)
            keys.insert(0, X_DEFAULT)
        for lang in keys:
            value = raw[lang]
            if not isinstance(value, str):
                continue
            text = self._make_text(local_name, value)
            text.set_attribute(Attribute(XML_NS_URI, LANG_ATTR_NAME, lang))
            la.add_property(text)
        return la

    @staticmethod
    def _extract_text_value(prop: TextType | str) -> str:
        """Pull the underlying string from a TextType-like or raw value."""
        if isinstance(prop, TextType):
            return prop.get_string_value()
        if isinstance(prop, str):
            return prop
        raise TypeError(
            f"expected TextType or str, got {type(prop).__name__}"
        )

    def _store_array_of_text_property(
        self, local_name: str, prop: ArrayProperty
    ) -> None:
        """Replace the bag/seq under ``local_name`` with the prop's children."""
        values: list[str] = []
        for child in prop.get_all_properties():
            if isinstance(child, TextType):
                values.append(child.get_string_value())
        self._properties[local_name] = values

    def _store_lang_alt_property(self, local_name: str, prop: ArrayProperty) -> None:
        bucket: dict[str, str] = {}
        for child in prop.get_all_properties():
            if not isinstance(child, TextType):
                continue
            attr = child.get_attribute(LANG_ATTR_NAME)
            lang = attr.get_value() if attr is not None else X_DEFAULT
            bucket[lang] = child.get_string_value()
        self._properties[local_name] = bucket

    # ================================================================
    # title (LangAlt, Simple)
    # ================================================================

    def set_title(self, value: str, lang: str | None = None) -> None:
        """
        Set the title for the document.

        Mirrors upstream's overloaded ``setTitle`` pair: ``setTitle(value)``
        defaults the language qualifier to ``x-default``; ``setTitle(lang,
        value)`` writes a specific language. The Python form merges both into
        a single signature with optional ``lang`` — pass a language code to
        target a specific entry in the title's lang-alt array.
        """
        self.set_unqualified_language_property_value(self.TITLE, lang, value)

    def set_title_lang(self, lang: str | None, value: str) -> None:
        # Upstream overload: ``setTitle(String lang, String value)``.
        self.set_unqualified_language_property_value(self.TITLE, lang, value)

    def add_title(self, lang: str | None, value: str) -> None:
        self.set_title_lang(lang, value)

    def get_title(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.TITLE, lang)

    def get_title_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(self.TITLE)

    def get_title_property(self) -> LangAlt | None:
        """Mirror of upstream ``getTitleProperty`` (typed accessor)."""
        return self._build_lang_alt(self.TITLE)

    def set_title_property(self, prop: ArrayProperty) -> None:
        """Mirror of upstream ``setTitleProperty`` — store a LangAlt directly."""
        self._store_lang_alt_property(self.TITLE, prop)

    # ================================================================
    # description (LangAlt, Simple)
    # ================================================================

    def set_description(self, value: str, lang: str | None = None) -> None:
        """
        Set the description of the resource.

        Mirrors upstream's overloaded ``setDescription`` / ``addDescription``
        pair: with no ``lang`` the value is stored under ``x-default``; with
        a ``lang`` the value is written under that language code.
        """
        self.set_unqualified_language_property_value(self.DESCRIPTION, lang, value)

    def add_description(self, lang: str | None, value: str) -> None:
        self.set_unqualified_language_property_value(self.DESCRIPTION, lang, value)

    def get_description(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.DESCRIPTION, lang)

    def get_description_languages(self) -> list[str] | None:
        """Mirror of upstream ``getDescriptionLanguages``."""
        return self.get_unqualified_language_property_languages_value(self.DESCRIPTION)

    def get_description_property(self) -> LangAlt | None:
        """Mirror of upstream ``getDescriptionProperty``."""
        return self._build_lang_alt(self.DESCRIPTION)

    def set_description_property(self, prop: ArrayProperty) -> None:
        self._store_lang_alt_property(self.DESCRIPTION, prop)

    # ================================================================
    # rights (LangAlt, Simple)
    # ================================================================

    def add_rights(self, lang: str | None, value: str) -> None:
        """Mirror of upstream ``addRights(lang, value)``."""
        self.set_unqualified_language_property_value(self.RIGHTS, lang, value)

    def set_rights(self, value: str, lang: str | None = None) -> None:
        """
        Set the rights statement for the resource.

        Symmetric with :meth:`set_title` / :meth:`set_description`: with no
        ``lang`` the value is stored under ``x-default``; with a ``lang`` the
        value is written under that specific language code. Upstream exposes
        only ``addRights(lang, value)``; this convenience makes the default-
        language path read naturally for callers porting code that uses the
        title/description setters.
        """
        self.set_unqualified_language_property_value(self.RIGHTS, lang, value)

    def get_rights(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.RIGHTS, lang)

    def get_rights_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(self.RIGHTS)

    def get_rights_property(self) -> LangAlt | None:
        return self._build_lang_alt(self.RIGHTS)

    def set_rights_property(self, prop: ArrayProperty) -> None:
        self._store_lang_alt_property(self.RIGHTS, prop)

    # ================================================================
    # creator (Seq of ProperName/Text)
    # ================================================================

    def add_creator(self, proper_name: str) -> None:
        self.add_unqualified_sequence_value(self.CREATOR, proper_name)

    def remove_creator(self, name: str) -> None:
        self.remove_unqualified_sequence_value(self.CREATOR, name)

    def get_creators(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.CREATOR)

    def get_creators_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getCreatorsProperty`` — Seq<ProperName>."""
        return self._build_array_of_text(
            self.CREATOR, Cardinality.Seq, self._make_proper_name
        )

    def set_creators_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.CREATOR, prop)

    # ================================================================
    # contributor (Bag of ProperName/Text)
    # ================================================================

    def add_contributor(self, proper_name: str) -> None:
        self.add_qualified_bag_value(self.CONTRIBUTOR, proper_name)

    def remove_contributor(self, proper_name: str) -> None:
        """Mirror of upstream ``removeContributor``."""
        self.remove_unqualified_bag_value(self.CONTRIBUTOR, proper_name)

    def get_contributors(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.CONTRIBUTOR)

    def get_contributors_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getContributorsProperty`` — Bag<ProperName>."""
        return self._build_array_of_text(
            self.CONTRIBUTOR, Cardinality.Bag, self._make_proper_name
        )

    def set_contributors_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.CONTRIBUTOR, prop)

    # ================================================================
    # publisher (Bag of ProperName/Text)
    # ================================================================

    def add_publisher(self, proper_name: str) -> None:
        self.add_qualified_bag_value(self.PUBLISHER, proper_name)

    def remove_publisher(self, name: str) -> None:
        """Mirror of upstream ``removePublisher``."""
        self.remove_unqualified_bag_value(self.PUBLISHER, name)

    def get_publishers(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.PUBLISHER)

    def get_publishers_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getPublishersProperty`` — Bag<ProperName>."""
        return self._build_array_of_text(
            self.PUBLISHER, Cardinality.Bag, self._make_proper_name
        )

    def set_publishers_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.PUBLISHER, prop)

    # ================================================================
    # language (Bag of Text/Locale)
    # ================================================================

    def add_language(self, locale: str) -> None:
        self.add_qualified_bag_value(self.LANGUAGE, locale)

    def remove_language(self, locale: str) -> None:
        """Mirror of upstream ``removeLanguage``."""
        self.remove_unqualified_bag_value(self.LANGUAGE, locale)

    def get_languages(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.LANGUAGE)

    def get_languages_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getLanguagesProperty`` — Bag<Locale> as Text."""
        return self._build_array_of_text(
            self.LANGUAGE, Cardinality.Bag, self._make_text
        )

    def set_languages_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.LANGUAGE, prop)

    # ================================================================
    # relation (Bag of Text)
    # ================================================================

    def add_relation(self, text: str) -> None:
        """Mirror of upstream ``addRelation``."""
        self.add_qualified_bag_value(self.RELATION, text)

    def remove_relation(self, text: str) -> None:
        """Mirror of upstream ``removeRelation``."""
        self.remove_unqualified_bag_value(self.RELATION, text)

    def get_relations(self) -> list[str] | None:
        """Mirror of upstream ``getRelations``."""
        return self.get_unqualified_bag_value_list(self.RELATION)

    def get_relations_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getRelationsProperty`` — Bag<Text>."""
        return self._build_array_of_text(
            self.RELATION, Cardinality.Bag, self._make_text
        )

    def set_relations_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.RELATION, prop)

    # ================================================================
    # subject (Bag of Text)
    # ================================================================

    def add_subject(self, text: str) -> None:
        self.add_qualified_bag_value(self.SUBJECT, text)

    def remove_subject(self, text: str) -> None:
        self.remove_unqualified_bag_value(self.SUBJECT, text)

    def get_subjects(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.SUBJECT)

    def get_subjects_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getSubjectsProperty`` — Bag<Text>."""
        return self._build_array_of_text(
            self.SUBJECT, Cardinality.Bag, self._make_text
        )

    def set_subjects_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.SUBJECT, prop)

    # ================================================================
    # type (Bag of Text)
    # ================================================================

    def add_type(self, value: str) -> None:
        """Mirror of upstream ``addType``."""
        self.add_qualified_bag_value(self.TYPE, value)

    def remove_type(self, value: str) -> None:
        """Mirror of upstream ``removeType``."""
        self.remove_unqualified_bag_value(self.TYPE, value)

    def get_types(self) -> list[str] | None:
        """Mirror of upstream ``getTypes``."""
        return self.get_unqualified_bag_value_list(self.TYPE)

    def get_types_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getTypesProperty`` — Bag<Text>."""
        return self._build_array_of_text(
            self.TYPE, Cardinality.Bag, self._make_text
        )

    def set_types_property(self, prop: ArrayProperty) -> None:
        self._store_array_of_text_property(self.TYPE, prop)

    # ================================================================
    # date (Seq of Date)
    # ================================================================

    def add_date(self, value: datetime | str) -> None:
        """Mirror of upstream ``addDate(Calendar)`` — accepts datetime/str."""
        if isinstance(value, datetime):
            stored = value.isoformat()
        elif isinstance(value, str):
            # Validate via the typed wrapper to mirror upstream rejection.
            self._make_date(self.DATE, value)
            stored = value
        else:
            raise TypeError(
                f"add_date expects datetime or str, got {type(value).__name__}"
            )
        self.add_unqualified_sequence_value(self.DATE, stored)

    def remove_date(self, value: datetime | str) -> None:
        """Mirror of upstream ``removeDate(Calendar)``."""
        target = value.isoformat() if isinstance(value, datetime) else value
        self.remove_unqualified_sequence_value(self.DATE, target)

    def get_dates(self) -> list[datetime] | None:
        """Mirror of upstream ``getDates`` — list of datetime values."""
        items = self.get_unqualified_array_list(self.DATE)
        if items is None:
            return None
        result: list[datetime] = []
        for item in items:
            if isinstance(item, str):
                result.append(self._make_date(self.DATE, item).get_value())
        return result

    def get_dates_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getDatesProperty`` — Seq<Date>."""
        return self._build_array_of_date(self.DATE)

    def set_dates_property(self, prop: ArrayProperty) -> None:
        values: list[str] = []
        for child in prop.get_all_properties():
            if isinstance(child, DateType | TextType):
                values.append(child.get_string_value())
        self._properties[self.DATE] = values

    # ================================================================
    # coverage (Text, Simple)
    # ================================================================

    def set_coverage(self, text: str) -> None:
        self.set_text_property_value(self.COVERAGE, text)

    def get_coverage(self) -> str | None:
        return self.get_unqualified_text_property_value(self.COVERAGE)

    def get_coverage_property(self) -> TextType | None:
        """Mirror of upstream ``getCoverageProperty``."""
        return self._build_text_property(self.COVERAGE, self._make_text)

    def set_coverage_property(self, prop: TextType) -> None:
        """Mirror of upstream ``setCoverageProperty(TextType)``."""
        self._properties[self.COVERAGE] = self._extract_text_value(prop)

    # ================================================================
    # format (MIMEType, Simple)
    # ================================================================

    def set_format(self, mime_type: str) -> None:
        self.set_text_property_value(self.FORMAT, mime_type)

    def get_format(self) -> str | None:
        return self.get_unqualified_text_property_value(self.FORMAT)

    def get_format_property(self) -> MIMEType | None:
        """Mirror of upstream ``getFormatProperty``."""
        v = self.get_unqualified_text_property_value(self.FORMAT)
        if v is None:
            return None
        return self._make_mime_type(self.FORMAT, v)

    def set_format_property(self, prop: MIMEType | TextType) -> None:
        """Mirror of upstream ``setFormatProperty(MIMEType)``."""
        self._properties[self.FORMAT] = self._extract_text_value(prop)

    # ================================================================
    # identifier (Text, Simple)
    # ================================================================

    def set_identifier(self, text: str) -> None:
        self.set_text_property_value(self.IDENTIFIER, text)

    def get_identifier(self) -> str | None:
        return self.get_unqualified_text_property_value(self.IDENTIFIER)

    def get_identifier_property(self) -> TextType | None:
        """Mirror of upstream ``getIdentifierProperty``."""
        return self._build_text_property(self.IDENTIFIER, self._make_text)

    def set_identifier_property(self, prop: TextType) -> None:
        """Mirror of upstream ``setIdentifierProperty(TextType)``."""
        self._properties[self.IDENTIFIER] = self._extract_text_value(prop)

    # ================================================================
    # source (Text, Simple)
    # ================================================================

    def set_source(self, text: str) -> None:
        self.set_text_property_value(self.SOURCE, text)

    def get_source(self) -> str | None:
        return self.get_unqualified_text_property_value(self.SOURCE)

    def get_source_property(self) -> TextType | None:
        """Mirror of upstream ``getSourceProperty``."""
        return self._build_text_property(self.SOURCE, self._make_text)

    def set_source_property(self, prop: TextType) -> None:
        """Mirror of upstream ``setSourceProperty(TextType)``."""
        self._properties[self.SOURCE] = self._extract_text_value(prop)
