"""
pypdfbox.xmpbox.type — typed XMP property hierarchy.

Ported from ``org.apache.xmpbox.type``. This package lands the foundation
of the AbstractField / AbstractSimpleProperty hierarchy along with the
common simple-property wrappers (Text, Integer, Boolean, Date, Real, URI,
ProperName, AgentName, MIME, GUID, Choice), the array container
(ArrayProperty for Bag/Seq/Alt), the LangAlt convenience helper, and a
TypeMapping registry for instantiating typed wrappers by name. Schemas
continue to expose their existing string-form accessors; migrating those
callers to typed properties is intentionally a separate wave so existing
parser/serialiser behavior is unaffected.
"""

from __future__ import annotations

from .abstract_field import AbstractField, Attribute
from .abstract_simple_property import AbstractSimpleProperty
from .agent_name_type import AgentNameType
from .array_property import ArrayProperty, Cardinality
from .boolean_type import BooleanType
from .choice_type import ChoiceType
from .date_type import DateType
from .guid_type import GUIDType
from .integer_type import IntegerType
from .lang_alt import LangAlt
from .mime_type import MIMEType
from .proper_name_type import ProperNameType
from .real_type import RealType
from .text_type import TextType
from .type_mapping import TypeMapping
from .uri_type import URIType

__all__ = [
    "AbstractField",
    "AbstractSimpleProperty",
    "AgentNameType",
    "ArrayProperty",
    "Attribute",
    "BooleanType",
    "Cardinality",
    "ChoiceType",
    "DateType",
    "GUIDType",
    "IntegerType",
    "LangAlt",
    "MIMEType",
    "ProperNameType",
    "RealType",
    "TextType",
    "TypeMapping",
    "URIType",
]
