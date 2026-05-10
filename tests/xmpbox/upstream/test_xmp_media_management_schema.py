"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/XMPMediaManagementTest.java

Upstream is a parameterised JUnit 5 driver around ``XMPSchemaTester``,
exercising ``getXxx`` / ``setXxx`` / ``getXxxProperty`` / ``setXxxProperty``
for every property declared on ``XMPMediaManagementSchema``. The Bag/Seq
properties (``Versions``, ``History``, ``Ingredients``) carry an array of
sample strings.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    AgentNameType,
    IntegerType,
    RenditionClassType,
    TextType,
    URIType,
    URLType,
    XMPMediaManagementSchema,
    XMPMetadata,
)

# Upstream initializeParameters() — kept verbatim so future re-syncs are diffable.
# (local-name, type-token, cardinality)
_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    ("DocumentID", "URI", "Simple"),
    ("Manager", "AgentName", "Simple"),
    ("ManageTo", "URI", "Simple"),
    ("ManageUI", "URI", "Simple"),
    ("InstanceID", "URI", "Simple"),
    ("OriginalDocumentID", "Text", "Simple"),
    ("RenditionParams", "Text", "Simple"),
    ("VersionID", "Text", "Simple"),
    ("Versions", "Version", "Seq"),
    ("History", "Text", "Seq"),
    ("Ingredients", "Text", "Bag"),
)

# Map upstream local-name → (string-getter, string-setter,
# typed-getter, typed-setter).
_ACCESSORS: dict[str, tuple[str, str, str | None, str | None]] = {
    "DocumentID": (
        "get_document_id",
        "set_document_id",
        "get_document_id_property",
        "set_document_id_property",
    ),
    "Manager": (
        "get_manager",
        "set_manager",
        "get_manager_property",
        "set_manager_property",
    ),
    "ManageTo": (
        "get_manage_to",
        "set_manage_to",
        "get_manage_to_property",
        "set_manage_to_property",
    ),
    "ManageUI": (
        "get_manage_ui",
        "set_manage_ui",
        "get_manage_ui_property",
        "set_manage_ui_property",
    ),
    "InstanceID": (
        "get_instance_id",
        "set_instance_id",
        "get_instance_id_property",
        "set_instance_id_property",
    ),
    "OriginalDocumentID": (
        "get_original_document_id",
        "set_original_document_id",
        "get_original_document_id_property",
        "set_original_document_id_property",
    ),
    "RenditionParams": (
        "get_rendition_params",
        "set_rendition_params",
        "get_rendition_params_property",
        "set_rendition_params_property",
    ),
    "VersionID": (
        "get_version_id",
        "set_version_id",
        "get_version_id_property",
        "set_version_id_property",
    ),
    "Versions": (
        "get_versions_string_list",
        "add_versions",
        None,
        None,
    ),
    "History": (
        "get_history_string_list",
        "add_history",
        None,
        None,
    ),
    "Ingredients": (
        "get_ingredients_string_list",
        "add_ingredients",
        None,
        None,
    ),
}

# Per-type token → typed property class for setXxxProperty round-trips.
_TYPED_CLASS: dict[str, type] = {
    "URI": URIType,
    "URL": URLType,
    "AgentName": AgentNameType,
    "Text": TextType,
    "RenditionClass": RenditionClassType,
}


@pytest.fixture
def metadata() -> XMPMetadata:
    """Mirror of upstream ``@BeforeEach initMetadata``."""
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> XMPMediaManagementSchema:
    obj = metadata.create_and_add_xmp_media_management_schema()
    assert isinstance(obj, XMPMediaManagementSchema)
    return obj


def _sample_value(type_token: str) -> object:
    if type_token == "Integer":
        return 7
    return {
        "URI": "uuid:FB031973-5E75-11B2-8F06-E7F5C101C07A",
        "URL": "https://dam.example.com/asset/42",
        "AgentName": "Raoul",
        "Text": "uuid:142",
        "RenditionClass": "default",
        "Version": "1",
    }.get(type_token, "sample")


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_initialized_to_null(
    schema: XMPMediaManagementSchema,
    field_name: str,
    type_token: str,
    card: str,
) -> None:
    """Translated from upstream ``testElementValue`` — null branch."""
    del type_token, card
    getter_name, _, typed_getter, _ = _ACCESSORS[field_name]
    assert getattr(schema, getter_name)() is None
    if typed_getter is not None:
        assert getattr(schema, typed_getter)() is None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_set_then_get_string_form(
    schema: XMPMediaManagementSchema,
    field_name: str,
    type_token: str,
    card: str,
) -> None:
    """Translated from upstream ``testElementValue`` — string-form path."""
    getter_name, setter_name, _, _ = _ACCESSORS[field_name]
    value = _sample_value(type_token)
    if card in {"Bag", "Seq"}:
        # Array-cardinality: addXxx(String) appends to the bag/seq.
        for item in (value, "second"):
            getattr(schema, setter_name)(item)
        result = getattr(schema, getter_name)()
        assert result == [value, "second"]
        return
    getattr(schema, setter_name)(value)
    assert getattr(schema, getter_name)() == value


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_set_then_get_typed_form(
    metadata: XMPMetadata,
    schema: XMPMediaManagementSchema,
    field_name: str,
    type_token: str,
    card: str,
) -> None:
    """
    Translated from upstream ``testElementProperty`` — exercises the typed
    ``getXxxProperty`` / ``setXxxProperty`` round-trip for the simple
    properties; array-cardinality rows reuse the string-flavour Bag/Seq path
    in pypdfbox (no setXxxProperty in the upstream class itself).
    """
    _, _, typed_getter, typed_setter = _ACCESSORS[field_name]
    if typed_getter is None or typed_setter is None:
        pytest.skip(f"no typed accessor pair for {field_name}")
    if card != "Simple":
        pytest.skip(f"typed setXxxProperty not declared upstream for {field_name}")
    value = _sample_value(type_token)
    type_cls = _TYPED_CLASS[type_token]
    prop = type_cls(
        metadata,
        XMPMediaManagementSchema.NAMESPACE,
        XMPMediaManagementSchema.PREFERRED_PREFIX,
        field_name,
        value,
    )
    getattr(schema, typed_setter)(prop)
    typed_result = getattr(schema, typed_getter)()
    # Upstream returns ``TextType`` from getXxxProperty even when the stored
    # value was a URIType/URLType/AgentNameType/RenditionClassType (these all
    # extend TextType); pypdfbox returns the same instance that was stored.
    assert typed_result is prop


def test_save_id_round_trip(
    metadata: XMPMetadata, schema: XMPMediaManagementSchema
) -> None:
    """Upstream ``setSaveId(Integer)`` / ``getSaveID()`` round-trip."""
    schema.set_save_id(42)
    assert schema.get_save_id() == 42
    prop = schema.get_save_id_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 42

    replacement = IntegerType(
        metadata,
        XMPMediaManagementSchema.NAMESPACE,
        XMPMediaManagementSchema.PREFERRED_PREFIX,
        XMPMediaManagementSchema.SAVE_ID,
        7,
    )
    schema.set_save_id_property(replacement)
    assert schema.get_save_id_property() is replacement
    assert schema.get_save_id() == 7


def test_last_url_round_trip(
    metadata: XMPMetadata, schema: XMPMediaManagementSchema
) -> None:
    """Upstream ``setLastURL(String)`` / ``getLastURL()`` triplet."""
    schema.set_last_url("https://example.com/last")
    assert schema.get_last_url() == "https://example.com/last"

    typed = URLType(
        metadata,
        XMPMediaManagementSchema.NAMESPACE,
        XMPMediaManagementSchema.PREFERRED_PREFIX,
        XMPMediaManagementSchema.LAST_URL,
        "https://example.com/typed",
    )
    schema.set_last_url_property(typed)
    assert schema.get_last_url_property() is typed
    assert schema.get_last_url() == "https://example.com/typed"


def test_local_name_constants_match_upstream() -> None:
    """Upstream ``public static final String`` constants verbatim."""
    assert XMPMediaManagementSchema.LAST_URL == "LastURL"
    assert XMPMediaManagementSchema.RENDITION_OF == "RenditionOf"
    assert XMPMediaManagementSchema.SAVE_ID == "SaveID"
    assert XMPMediaManagementSchema.DERIVED_FROM == "DerivedFrom"
    assert XMPMediaManagementSchema.DOCUMENTID == "DocumentID"
    assert XMPMediaManagementSchema.MANAGER == "Manager"
    assert XMPMediaManagementSchema.MANAGETO == "ManageTo"
    assert XMPMediaManagementSchema.MANAGEUI == "ManageUI"
    assert XMPMediaManagementSchema.MANAGERVARIANT == "ManagerVariant"
    assert XMPMediaManagementSchema.INSTANCEID == "InstanceID"
    assert XMPMediaManagementSchema.MANAGED_FROM == "ManagedFrom"
    assert XMPMediaManagementSchema.ORIGINALDOCUMENTID == "OriginalDocumentID"
    assert XMPMediaManagementSchema.RENDITIONCLASS == "RenditionClass"
    assert XMPMediaManagementSchema.RENDITIONPARAMS == "RenditionParams"
    assert XMPMediaManagementSchema.VERSIONID == "VersionID"
    assert XMPMediaManagementSchema.VERSIONS == "Versions"
    assert XMPMediaManagementSchema.HISTORY == "History"
    assert XMPMediaManagementSchema.INGREDIENTS == "Ingredients"
