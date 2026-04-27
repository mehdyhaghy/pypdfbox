from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class PDFAFieldType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.PDFAFieldType``. Represents the
    ``pdfaField:Field`` structure used inside the PDF/A Extension schema's
    ``pdfaType:field`` seq to describe one field of a custom value type
    (``name`` / ``valueType`` / ``description``).

    Lives in ``pdfa_field_description_type`` to match the schema-level
    "field description" terminology while preserving the exact upstream
    class name ``PDFAFieldType``.
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/field#"
    PREFERRED_PREFIX = "pdfaField"

    NAME = "name"
    VALUETYPE = "valueType"
    DESCRIPTION = "description"

    _FIELD_TYPES = {
        NAME: "Text",
        VALUETYPE: "Choice",
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
        # Upstream casts to TextType even though VALUETYPE is annotated as
        # Choice; ChoiceType is a TextType subclass so the cast succeeds.
        return self.get_property_value_as_string(self.VALUETYPE)

    def get_description(self) -> str | None:
        prop = self.get_property(self.DESCRIPTION)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None
