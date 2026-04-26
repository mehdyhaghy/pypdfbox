from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class DublinCoreSchema(XMPSchema):
    """
    Representation of a Dublin Core XMP schema.

    Ported (subset, read path) from
    ``org.apache.xmpbox.schema.DublinCoreSchema`` (PDFBox 3.0). Property local
    names match upstream constants verbatim. Methods that return ``ArrayProperty``
    in upstream are deferred — only the value-returning variants ship in
    cluster #1.
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

    # --- title (LangAlt) ---------------------------------------------

    def set_title(self, value: str) -> None:
        self.set_unqualified_language_property_value(self.TITLE, None, value)

    def set_title_lang(self, lang: str | None, value: str) -> None:
        # Upstream overload: ``setTitle(String lang, String value)``.
        self.set_unqualified_language_property_value(self.TITLE, lang, value)

    def add_title(self, lang: str | None, value: str) -> None:
        self.set_title_lang(lang, value)

    def get_title(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.TITLE, lang)

    def get_title_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(self.TITLE)

    # --- description (LangAlt) ---------------------------------------

    def set_description(self, value: str) -> None:
        self.set_unqualified_language_property_value(self.DESCRIPTION, None, value)

    def add_description(self, lang: str | None, value: str) -> None:
        self.set_unqualified_language_property_value(self.DESCRIPTION, lang, value)

    def get_description(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.DESCRIPTION, lang)

    # --- creator (Seq) -----------------------------------------------

    def add_creator(self, proper_name: str) -> None:
        self.add_unqualified_sequence_value(self.CREATOR, proper_name)

    def remove_creator(self, name: str) -> None:
        self.remove_unqualified_sequence_value(self.CREATOR, name)

    def get_creators(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.CREATOR)

    # --- subject (Bag) -----------------------------------------------

    def add_subject(self, text: str) -> None:
        self.add_qualified_bag_value(self.SUBJECT, text)

    def remove_subject(self, text: str) -> None:
        self.remove_unqualified_bag_value(self.SUBJECT, text)

    def get_subjects(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.SUBJECT)

    # --- contributor / publisher / language / relation / type (Bag) --

    def add_contributor(self, proper_name: str) -> None:
        self.add_qualified_bag_value(self.CONTRIBUTOR, proper_name)

    def get_contributors(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.CONTRIBUTOR)

    def add_publisher(self, proper_name: str) -> None:
        self.add_qualified_bag_value(self.PUBLISHER, proper_name)

    def get_publishers(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.PUBLISHER)

    def add_language(self, locale: str) -> None:
        self.add_qualified_bag_value(self.LANGUAGE, locale)

    def get_languages(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.LANGUAGE)

    # --- simple text properties --------------------------------------

    def set_coverage(self, text: str) -> None:
        self.set_text_property_value(self.COVERAGE, text)

    def get_coverage(self) -> str | None:
        return self.get_unqualified_text_property_value(self.COVERAGE)

    def set_format(self, mime_type: str) -> None:
        self.set_text_property_value(self.FORMAT, mime_type)

    def get_format(self) -> str | None:
        return self.get_unqualified_text_property_value(self.FORMAT)

    def set_identifier(self, text: str) -> None:
        self.set_text_property_value(self.IDENTIFIER, text)

    def get_identifier(self) -> str | None:
        return self.get_unqualified_text_property_value(self.IDENTIFIER)

    def set_source(self, text: str) -> None:
        self.set_text_property_value(self.SOURCE, text)

    def get_source(self) -> str | None:
        return self.get_unqualified_text_property_value(self.SOURCE)
