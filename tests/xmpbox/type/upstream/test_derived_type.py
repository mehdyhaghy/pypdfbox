"""Port of xmpbox/src/test/java/org/apache/xmpbox/type/TestDerivedType.java

Upstream baseline: PDFBox 3.0.x. Parametrised constructor-shape check
across every TextType-derived simple property class.
"""
from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AgentNameType,
    ChoiceType,
    GUIDType,
    LocaleType,
    MIMEType,
    PartType,
    ProperNameType,
    RenditionClassType,
    TextType,
    URIType,
    URLType,
    XPathType,
)

PREFIX = "myprefix"
NAME = "myname"
VALUE = "myvalue"


@pytest.fixture
def xmp() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.mark.parametrize(
    "clz,type_name",
    [
        (AgentNameType, "AgentName"),
        (ChoiceType, "Choice"),
        (GUIDType, "GUID"),
        (LocaleType, "Locale"),
        (MIMEType, "MIME"),
        (PartType, "Part"),
        (ProperNameType, "ProperName"),
        (RenditionClassType, "RenditionClass"),
        (URIType, "URI"),
        (URLType, "URL"),
        (XPathType, "XPath"),
    ],
)
def test1(xmp: XMPMetadata, clz: type[TextType], type_name: str) -> None:
    element = clz(xmp, None, PREFIX, NAME, VALUE)
    assert element.get_namespace() is None
    assert isinstance(element.get_value(), str)
    assert element.get_value() == VALUE
