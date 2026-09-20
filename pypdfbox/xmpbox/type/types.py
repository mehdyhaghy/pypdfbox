"""Property-type tag enumeration.

Mirrors ``org.apache.xmpbox.type.Types`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/type/Types.java``).

The Java enum classifies every XMP property kind as basic/derived,
simple/structured, and pairs it with the ``AbstractField`` subclass that
materialises that type.

Java enum constants are distinct by identity no matter what arguments they
carry; a Python ``Enum`` instead folds members that share a value into
aliases. Two pairs here carry identical metadata -- ``DefinedType`` with
``Structured``, and ``LangAlt`` with ``GPSCoordinate`` -- so the obvious
``Member = (simple, basic, impl)`` spelling silently produced 36 constants
out of 38, and ``Types.Structured.is_defined()`` answered ``True``.

``__new__`` therefore gives every member its own ``_value_`` and the
declared tuple is consumed by ``__init__`` as named attributes. That is
the same shape as the Java constructor -- arguments become fields, the
constant's identity is its own -- and it makes uniqueness structural: a
new member with metadata identical to an existing one cannot reintroduce
the alias. ``@unique`` guards the result at import time.

The implementing class is carried as a *name* rather than the class
object so the implementation modules need not import at module-load time.
``_value_`` is an opaque ordinal with no upstream counterpart (Java enums
have no ``value``); callers use the accessors or the named attributes.
"""

from enum import Enum, unique


@unique
class Types(Enum):
    simple: bool
    basic: str | None
    impl_class_name: str | None

    def __new__(cls, *args: object) -> Types:
        # Unique ordinal per member -- see the module docstring. Without this,
        # members sharing a metadata tuple collapse into aliases.
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__) + 1
        return obj

    def __init__(self, simple: bool, basic: str | None, impl_class_name: str | None) -> None:
        self.simple = simple
        self.basic = basic
        self.impl_class_name = impl_class_name

    Structured = (False, None, None)
    DefinedType = (False, None, None)  # noqa: PIE796 (distinct via __new__)

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
    LangAlt = (True, "Text", "TextType")  # noqa: PIE796 (distinct via __new__)
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
        return self.simple

    def is_basic(self) -> bool:
        return self.basic is None

    def is_structured(self) -> bool:
        return self.basic == "Structured"

    def is_defined(self) -> bool:
        return self is Types.DefinedType

    def get_basic(self) -> Types | None:
        return None if self.basic is None else Types[self.basic]

    def get_implementing_class_name(self) -> str | None:
        return self.impl_class_name


__all__ = ["Types"]
