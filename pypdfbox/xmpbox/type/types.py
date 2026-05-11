"""Property-type tag enumeration.

Mirrors ``org.apache.xmpbox.type.Types`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/type/Types.java``).

The Java enum classifies every XMP property kind as basic/derived,
simple/structured, and pairs it with the ``AbstractField`` subclass that
materialises that type. We model it as a Python ``Enum`` whose values are
the metadata tuple ``(simple, basic, impl_class_name)`` so callers can
introspect classifications without forcing the implementation classes to
import at module-load time.
"""

from __future__ import annotations

from enum import Enum


class Types(Enum):
    Structured = (False, None, None)
    DefinedType = (False, None, None)

    # basic
    Text = (True, None, "TextType")
    Date = (True, None, "DateType")
    Boolean = (True, None, "BooleanType")
    Integer = (True, None, "IntegerType")
    Real = (True, None, "RealType")
    GPSCoordinate = (True, "Text", "TextType")

    ProperName = (True, "Text", "ProperNameType")
    Locale = (True, "Text", "LocaleType")
    AgentName = (True, "Text", "AgentNameType")
    GUID = (True, "Text", "GUIDType")
    XPath = (True, "Text", "XPathType")
    Part = (True, "Text", "PartType")
    URL = (True, "Text", "URLType")
    URI = (True, "Text", "URIType")
    Choice = (True, "Text", "ChoiceType")
    MIMEType = (True, "Text", "MIMEType")
    LangAlt = (True, "Text", "TextType")
    RenditionClass = (True, "Text", "RenditionClassType")
    Rational = (True, "Text", "RationalType")

    Colorant = (False, "Structured", "ColorantType")
    Font = (False, "Structured", "FontType")
    Layer = (False, "Structured", "LayerType")
    Thumbnail = (False, "Structured", "ThumbnailType")
    ResourceEvent = (False, "Structured", "ResourceEventType")
    ResourceRef = (False, "Structured", "ResourceRefType")
    Version = (False, "Structured", "VersionType")
    PDFASchema = (False, "Structured", "PDFASchemaType")
    PDFAField = (False, "Structured", "PDFAFieldType")
    PDFAProperty = (False, "Structured", "PDFAPropertyType")
    PDFAType = (False, "Structured", "PDFATypeType")
    Job = (False, "Structured", "JobType")
    OECF = (False, "Structured", "OECFType")
    CFAPattern = (False, "Structured", "CFAPatternType")
    DeviceSettings = (False, "Structured", "DeviceSettingsType")
    Flash = (False, "Structured", "FlashType")
    Dimensions = (False, "Structured", "DimensionsType")

    def is_simple(self) -> bool:
        return self.value[0]

    def is_basic(self) -> bool:
        return self.value[1] is None

    def is_structured(self) -> bool:
        return self.value[1] == "Structured"

    def is_defined(self) -> bool:
        return self is Types.DefinedType

    def get_basic(self) -> Types | None:
        b = self.value[1]
        return None if b is None else Types[b]

    def get_implementing_class_name(self) -> str | None:
        return self.value[2]


__all__ = ["Types"]
