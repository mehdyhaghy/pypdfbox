from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPBasicSchema(XMPSchema):
    """
    Representation of the XMP Basic schema.

    Ported (subset, read path) from
    ``org.apache.xmpbox.schema.XMPBasicSchema`` (PDFBox 3.0). Local-name
    constants and accessor names mirror upstream. Date values are kept as
    strings in ISO-8601 form for cluster #1 — ``DateType`` parsing is deferred.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/"
    PREFERRED_PREFIX = "xmp"

    ADVISORY = "Advisory"
    BASEURL = "BaseURL"
    CREATEDATE = "CreateDate"
    CREATORTOOL = "CreatorTool"
    IDENTIFIER = "Identifier"
    LABEL = "Label"
    METADATADATE = "MetadataDate"
    MODIFYDATE = "ModifyDate"
    NICKNAME = "Nickname"
    RATING = "Rating"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- creator tool -------------------------------------------------

    def set_creator_tool(self, tool: str) -> None:
        self.set_text_property_value(self.CREATORTOOL, tool)

    def get_creator_tool(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CREATORTOOL)

    # --- create / modify / metadata dates (string ISO-8601 in this cluster) --

    def set_create_date(self, date: str) -> None:
        self.set_text_property_value(self.CREATEDATE, date)

    def get_create_date(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CREATEDATE)

    def set_modify_date(self, date: str) -> None:
        self.set_text_property_value(self.MODIFYDATE, date)

    def get_modify_date(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MODIFYDATE)

    def set_metadata_date(self, date: str) -> None:
        self.set_text_property_value(self.METADATADATE, date)

    def get_metadata_date(self) -> str | None:
        return self.get_unqualified_text_property_value(self.METADATADATE)

    # --- label / nickname / base url ---------------------------------

    def set_label(self, label: str) -> None:
        self.set_text_property_value(self.LABEL, label)

    def get_label(self) -> str | None:
        return self.get_unqualified_text_property_value(self.LABEL)

    def set_nickname(self, nickname: str) -> None:
        self.set_text_property_value(self.NICKNAME, nickname)

    def get_nickname(self) -> str | None:
        return self.get_unqualified_text_property_value(self.NICKNAME)

    def set_base_url(self, url: str) -> None:
        self.set_text_property_value(self.BASEURL, url)

    def get_base_url(self) -> str | None:
        return self.get_unqualified_text_property_value(self.BASEURL)

    # --- identifier (Bag) --------------------------------------------

    def add_identifier(self, value: str) -> None:
        self.add_qualified_bag_value(self.IDENTIFIER, value)

    def get_identifiers(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.IDENTIFIER)
