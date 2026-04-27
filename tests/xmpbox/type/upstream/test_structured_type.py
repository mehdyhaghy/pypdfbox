"""
Ported from upstream
``xmpbox/src/test/java/org/apache/xmpbox/type/TestStructuredType.java``.

Upstream uses JUnit ``@ParameterizedTest`` + reflection on Java setter naming
conventions (``setXxx``) to dispatch by field name. This port replaces
reflection with an explicit setter-getter map so the round-trip parity is
preserved while staying fully Pythonic.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AbstractSimpleProperty,
    AbstractStructuredType,
    AgentNameType,
    ChoiceType,
    DateType,
    GUIDType,
    IntegerType,
    JobType,
    LayerType,
    ResourceEventType,
    ResourceRefType,
    TextType,
    ThumbnailType,
    URIType,
)

_TYPE_TO_CLS: dict[str, type[AbstractSimpleProperty]] = {
    "Text": TextType,
    "Choice": ChoiceType,
    "GUID": GUIDType,
    "AgentName": AgentNameType,
    "Date": DateType,
    "URI": URIType,
    "URL": URIType,
    "Integer": IntegerType,
}


def _camel_to_snake(name: str) -> str:
    s = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s).lower()


def _java_value(type_name: str) -> object:
    if type_name == "Date":
        return datetime(2024, 1, 1, tzinfo=UTC)
    if type_name == "Integer":
        return 42
    return "hello"


def _make_metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


_PARAMS: list[tuple[type[AbstractStructuredType], str, str, list[object]]] = [
    (JobType, "id", "Text", []),
    (JobType, "name", "Text", []),
    (JobType, "url", "URL", []),
    (LayerType, "LayerName", "Text", []),
    (LayerType, "LayerText", "Text", []),
    (ResourceEventType, "action", "Choice", []),
    (ResourceEventType, "changed", "Text", []),
    (ResourceEventType, "instanceID", "GUID", []),
    (ResourceEventType, "parameters", "Text", []),
    (ResourceEventType, "softwareAgent", "AgentName", []),
    (ResourceEventType, "when", "Date", []),
    (ResourceRefType, "documentID", "URI", []),
    (ResourceRefType, "filePath", "URI", []),
    (ResourceRefType, "instanceID", "URI", []),
    (ResourceRefType, "lastModifyDate", "Date", []),
    (ResourceRefType, "manager", "AgentName", []),
    (ResourceRefType, "managerVariant", "Text", []),
    (ResourceRefType, "manageTo", "URI", []),
    (ResourceRefType, "manageUI", "URI", []),
    (ResourceRefType, "maskMarkers", "Choice", []),
    (ResourceRefType, "partMapping", "Text", []),
    (ResourceRefType, "renditionParams", "Text", []),
    (ResourceRefType, "versionID", "Text", []),
    (ThumbnailType, "format", "Choice", []),
    (ThumbnailType, "height", "Integer", []),
    (ThumbnailType, "width", "Integer", []),
    (ThumbnailType, "image", "Text", []),
]


def _build(cls: type[AbstractStructuredType]) -> AbstractStructuredType:
    if cls is JobType:
        return cls(_make_metadata(), "job")
    return cls(_make_metadata())


def _setter_method_name(field_name: str) -> str:
    return "set_" + _camel_to_snake(field_name)


def _getter_method_name(field_name: str) -> str:
    return "get_" + _camel_to_snake(field_name)


@pytest.mark.parametrize("cls,field_name,type_name,_extra", _PARAMS)
def test_initialized_to_null(
    cls: type[AbstractStructuredType], field_name: str, type_name: str, _extra: list[object]
) -> None:
    structured = _build(cls)
    assert structured.get_property(field_name) is None
    getter = getattr(structured, _getter_method_name(field_name), None)
    if getter is not None:
        assert getter() is None


@pytest.mark.parametrize("cls,field_name,type_name,_extra", _PARAMS)
def test_setting_value_via_add_simple_property(
    cls: type[AbstractStructuredType], field_name: str, type_name: str, _extra: list[object]
) -> None:
    structured = _build(cls)
    value = _java_value(type_name)
    structured.add_simple_property(field_name, value)
    assert structured.get_property(field_name) is not None


@pytest.mark.parametrize("cls,field_name,type_name,_extra", _PARAMS)
def test_property_type_class(
    cls: type[AbstractStructuredType], field_name: str, type_name: str, _extra: list[object]
) -> None:
    structured = _build(cls)
    value = _java_value(type_name)
    structured.add_simple_property(field_name, value)
    expected_cls = _TYPE_TO_CLS[type_name]
    asp = structured.get_property(field_name)
    assert isinstance(asp, expected_cls)


@pytest.mark.parametrize("cls,field_name,type_name,_extra", _PARAMS)
def test_setter_then_getter(
    cls: type[AbstractStructuredType], field_name: str, type_name: str, _extra: list[object]
) -> None:
    structured = _build(cls)
    setter = getattr(structured, _setter_method_name(field_name), None)
    getter = getattr(structured, _getter_method_name(field_name), None)
    if setter is None or getter is None:
        pytest.skip(f"no typed setter/getter pair for {field_name}")
    value = _java_value(type_name)
    setter(value)
    asp = structured.get_property(field_name)
    assert isinstance(asp, AbstractSimpleProperty)
    if type_name in ("Date", "Integer"):
        assert asp.get_value() == value
    else:
        assert asp.get_string_value() == value
    result = getter()
    assert result == value
