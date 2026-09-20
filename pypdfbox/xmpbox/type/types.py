"""Property-type tag enumeration.

Mirrors ``org.apache.xmpbox.type.Types`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/type/Types.java``).

The Java enum classifies every XMP property kind as basic/derived,
simple/structured, and pairs it with the ``AbstractField`` subclass that
materialises that type. We model it as a Python ``Enum`` whose values are
the metadata tuple ``(name, simple, basic, impl_class_name)`` so callers
can introspect classifications without forcing the implementation classes
to import at module-load time.

The leading ``name`` element exists purely to keep every member's value
unique. Java enum constants are always distinct even when they carry
identical constructor arguments, whereas a Python ``Enum`` silently folds
equal-valued members into aliases. Without the discriminator
``DefinedType`` would alias ``Structured`` and ``LangAlt`` would alias
``GPSCoordinate``, losing two of upstream's 38 constants.
"""

from enum import Enum


class Types(Enum):
    Structured = ("Structured", False, None, None)
    DefinedType = ("DefinedType", False, None, None)

    # basic
    Text = ("Text", True, None, "TextType")
    Date = ("Date", True, None, "DateType")
    Boolean = ("Boolean", True, None, "BooleanType")
    Integer = ("Integer", True, None, "IntegerType")
    Real = ("Real", True, None, "RealType")
    GPSCoordinate = ("GPSCoordinate", True, "Text", "TextType")

    ProperName = ("ProperName", True, "Text", "ProperNameType")
    Locale = ("Locale", True, "Text", "LocaleType")
    AgentName = ("AgentName", True, "Text", "AgentNameType")
    GUID = ("GUID", True, "Text", "GUIDType")
    XPath = ("XPath", True, "Text", "XPathType")
    Part = ("Part", True, "Text", "PartType")
    URL = ("URL", True, "Text", "URLType")
    URI = ("URI", True, "Text", "URIType")
    Choice = ("Choice", True, "Text", "ChoiceType")
    MIMEType = ("MIMEType", True, "Text", "MIMEType")
    LangAlt = ("LangAlt", True, "Text", "TextType")
    RenditionClass = ("RenditionClass", True, "Text", "RenditionClassType")
    Rational = ("Rational", True, "Text", "RationalType")

    Colorant = ("Colorant", False, "Structured", "ColorantType")
    Font = ("Font", False, "Structured", "FontType")
    Layer = ("Layer", False, "Structured", "LayerType")
    Thumbnail = ("Thumbnail", False, "Structured", "ThumbnailType")
    ResourceEvent = ("ResourceEvent", False, "Structured", "ResourceEventType")
    ResourceRef = ("ResourceRef", False, "Structured", "ResourceRefType")
    Version = ("Version", False, "Structured", "VersionType")
    PDFASchema = ("PDFASchema", False, "Structured", "PDFASchemaType")
    PDFAField = ("PDFAField", False, "Structured", "PDFAFieldType")
    PDFAProperty = ("PDFAProperty", False, "Structured", "PDFAPropertyType")
    PDFAType = ("PDFAType", False, "Structured", "PDFATypeType")
    Job = ("Job", False, "Structured", "JobType")
    OECF = ("OECF", False, "Structured", "OECFType")
    CFAPattern = ("CFAPattern", False, "Structured", "CFAPatternType")
    DeviceSettings = ("DeviceSettings", False, "Structured", "DeviceSettingsType")
    Flash = ("Flash", False, "Structured", "FlashType")
    Dimensions = ("Dimensions", False, "Structured", "DimensionsType")

    def is_simple(self) -> bool:
        return self.value[1]

    def is_basic(self) -> bool:
        return self.value[2] is None

    def is_structured(self) -> bool:
        return self.value[2] == "Structured"

    def is_defined(self) -> bool:
        return self is Types.DefinedType

    def get_basic(self) -> Types | None:
        b = self.value[2]
        return None if b is None else Types[b]

    def get_implementing_class_name(self) -> str | None:
        return self.value[3]


__all__ = ["Types"]
