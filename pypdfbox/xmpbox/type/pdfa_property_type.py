from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .choice_type import ChoiceType
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class PDFAPropertyType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.PDFAPropertyType``. Represents the
    ``pdfaProperty:Property`` structure used inside the PDF/A Extension
    schema's ``pdfaSchema:property`` seq to describe one custom property
    declared by a third-party schema (``name`` / ``valueType`` /
    ``category`` / ``description``).
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/property#"
    PREFERRED_PREFIX = "pdfaProperty"

    NAME = "name"
    VALUETYPE = "valueType"
    CATEGORY = "category"
    DESCRIPTION = "description"

    _FIELD_TYPES = {
        NAME: "Text",
        VALUETYPE: "Choice",
        CATEGORY: "Choice",
        DESCRIPTION: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    def get_name(self) -> str | None:
        prop = self.get_property(self.NAME)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def get_value_type(self) -> str | None:
        prop = self.get_property(self.VALUETYPE)
        if isinstance(prop, ChoiceType):
            return prop.get_string_value()
        return None

    def get_description(self) -> str | None:
        prop = self.get_property(self.DESCRIPTION)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def get_category(self) -> str | None:
        prop = self.get_property(self.CATEGORY)
        if isinstance(prop, ChoiceType):
            return prop.get_string_value()
        return None
