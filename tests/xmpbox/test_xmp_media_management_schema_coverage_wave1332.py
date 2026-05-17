"""Wave 1332 — coverage boost for ``pypdfbox.xmpbox.xmp_media_management_schema``.

Targets ``set_*_property(None)`` clearing branches, the
``_get_simple_typed`` materialisation from raw strings (including the
``TypeError``/``ValueError`` swallow), the structured ``get_*_property``
ArrayProperty branches, and the ``SaveID`` integer/string/bool/invalid
paths so the module reaches >=95%.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    IntegerType,
    XMPMediaManagementSchema,
    XMPMetadata,
)
from pypdfbox.xmpbox.type import ResourceEventType, ResourceRefType, VersionType
from pypdfbox.xmpbox.type.agent_name_type import AgentNameType
from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.rendition_class_type import RenditionClassType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.type.uri_type import URIType
from pypdfbox.xmpbox.type.url_type import URLType


def _mm() -> XMPMediaManagementSchema:
    return XMPMediaManagementSchema(XMPMetadata.create_xmp_metadata())


def _text(schema: XMPMediaManagementSchema, value: str) -> TextType:
    return TextType(
        schema._metadata,  # noqa: SLF001
        schema._namespace,  # noqa: SLF001
        schema._prefix,  # noqa: SLF001
        "tmp",
        value,
    )


# --- _get_simple_typed branches ---------------------------------------


def test_get_simple_typed_returns_none_when_value_unsupported() -> None:
    schema = _mm()
    schema._properties["DocumentID"] = 42  # noqa: SLF001 — exercise "neither str nor typed"
    assert schema.get_document_id_property() is None


def test_get_simple_typed_materialises_typed_from_string_for_document_id() -> None:
    schema = _mm()
    schema.set_text_property_value("DocumentID", "uuid:abc")
    prop = schema.get_document_id_property()
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "uuid:abc"


def test_get_simple_typed_swallows_value_error_when_materialising() -> None:
    schema = _mm()
    # SAVE_ID typed-from-string path raises ValueError for non-numeric; the
    # helper must swallow and return None instead of propagating.
    schema._properties["SaveID"] = "not-a-number"  # noqa: SLF001
    assert schema.get_save_id_property() is None


# --- set_*_property(None) clearing branches ---------------------------


@pytest.mark.parametrize(
    ("setter_name", "local_name", "typed_value"),
    [
        ("set_document_id_property", "DocumentID", "uri-doc"),
        ("set_instance_id_property", "InstanceID", "uri-inst"),
        ("set_original_document_id_property", "OriginalDocumentID", "orig"),
        ("set_version_id_property", "VersionID", "v9"),
        ("set_rendition_params_property", "RenditionParams", "dpi=72"),
        ("set_manage_to_property", "ManageTo", "https://dam.example/asset"),
        ("set_manage_ui_property", "ManageUI", "https://dam.example/ui"),
        ("set_manager_variant_property", "ManagerVariant", "enterprise"),
    ],
)
def test_set_property_none_clears_simple_property(
    setter_name: str, local_name: str, typed_value: str
) -> None:
    schema = _mm()
    typed = _text(schema, typed_value)
    getattr(schema, setter_name)(typed)
    assert schema._properties[local_name] is typed  # noqa: SLF001
    getattr(schema, setter_name)(None)
    assert local_name not in schema._properties  # noqa: SLF001


def test_set_rendition_class_property_stores_then_clears() -> None:
    schema = _mm()
    rc = RenditionClassType(
        schema._metadata, schema._namespace, schema._prefix, "RenditionClass", "proof"  # noqa: SLF001
    )
    schema.set_rendition_class_property(rc)
    assert schema._properties["RenditionClass"] is rc  # noqa: SLF001
    assert isinstance(schema.get_rendition_class_property(), TextType)
    schema.set_rendition_class_property(None)
    assert "RenditionClass" not in schema._properties  # noqa: SLF001


def test_set_manager_property_stores_then_clears() -> None:
    schema = _mm()
    agent = AgentNameType(
        schema._metadata, schema._namespace, schema._prefix, "Manager", "DAM Pro"  # noqa: SLF001
    )
    schema.set_manager_property(agent)
    assert schema._properties["Manager"] is agent  # noqa: SLF001
    schema.set_manager_property(None)
    assert "Manager" not in schema._properties  # noqa: SLF001


# --- read_text falls through TextType-wrapped values ------------------


def test_get_via_typed_text_property_round_trip() -> None:
    schema = _mm()
    typed = _text(schema, "wrapped")
    schema.set_document_id_property(typed)  # type: ignore[arg-type]
    assert schema.get_document_id() == "wrapped"
    assert schema.get_instance_id() is None


def test_get_via_uri_subtype_wrapped_value() -> None:
    schema = _mm()
    uri = URIType(
        schema._metadata, schema._namespace, schema._prefix, "ManageTo", "https://x/y"  # noqa: SLF001
    )
    schema.set_manage_to_property(uri)
    assert schema.get_manage_to() == "https://x/y"


# --- DerivedFrom / ManagedFrom / RenditionOf --------------------------


def _resource_ref(schema: XMPMediaManagementSchema) -> ResourceRefType:
    ref = ResourceRefType(schema._metadata)  # noqa: SLF001
    return ref


def test_derived_from_set_clear_and_resource_ref_alias() -> None:
    schema = _mm()
    ref = _resource_ref(schema)
    schema.set_derived_from(ref)
    assert schema.get_derived_from() is ref
    assert schema.get_derived_from_property() is ref
    assert schema.get_resource_ref_property() is ref
    schema.set_derived_from_property(None)
    assert schema.get_derived_from() is None
    assert schema.get_derived_from_property() is None
    assert schema.get_resource_ref_property() is None


def test_derived_from_get_returns_none_for_non_resource_ref_value() -> None:
    schema = _mm()
    schema._properties["DerivedFrom"] = "not-a-ref"  # noqa: SLF001
    assert schema.get_derived_from() is None


def test_managed_from_setters_and_getters() -> None:
    schema = _mm()
    ref = _resource_ref(schema)
    schema.set_managed_from_property(ref)
    assert schema.get_managed_from() is ref
    assert schema.get_managed_from_property() is ref
    schema.set_managed_from(None)
    assert schema.get_managed_from() is None
    # non-ref stored value yields None
    schema._properties["ManagedFrom"] = 7  # noqa: SLF001
    assert schema.get_managed_from() is None


def test_rendition_of_set_clear_and_get_none_for_unrelated_value() -> None:
    schema = _mm()
    ref = _resource_ref(schema)
    schema.set_rendition_of(ref)
    assert schema.get_rendition_of() is ref
    schema.set_rendition_of(None)
    assert schema.get_rendition_of() is None
    schema._properties["RenditionOf"] = "scalar"  # noqa: SLF001
    assert schema.get_rendition_of() is None


# --- History ----------------------------------------------------------


def test_history_typed_append_and_get_skips_non_typed() -> None:
    schema = _mm()
    event = ResourceEventType(schema._metadata)  # noqa: SLF001
    schema.add_history(event)
    schema.add_history(event)
    # Pre-existing non-list entry forces the "wrap to list" branch on get_history.
    schema._properties["History"] = event  # noqa: SLF001 — exercise non-list branch
    assert schema.get_history() == [event]


def test_get_history_property_returns_array_property_when_present() -> None:
    schema = _mm()
    array = ArrayProperty(
        schema._metadata,  # noqa: SLF001
        schema._namespace,  # noqa: SLF001
        schema._prefix,  # noqa: SLF001
        "History",
        Cardinality.Seq,
    )
    schema._properties["History"] = array  # noqa: SLF001
    assert schema.get_history_property() is array


def test_get_history_property_returns_none_for_non_array_value() -> None:
    schema = _mm()
    schema._properties["History"] = []  # noqa: SLF001
    assert schema.get_history_property() is None


# --- Versions ---------------------------------------------------------


def test_versions_typed_append_and_wrap_non_list() -> None:
    schema = _mm()
    version = VersionType(schema._metadata)  # noqa: SLF001
    schema.add_version(version)
    assert schema.get_versions() == [version]
    schema._properties["Versions"] = version  # noqa: SLF001 — non-list branch
    assert schema.get_versions() == [version]


def test_get_versions_property_returns_array_property() -> None:
    schema = _mm()
    array = ArrayProperty(
        schema._metadata,  # noqa: SLF001
        schema._namespace,  # noqa: SLF001
        schema._prefix,  # noqa: SLF001
        "Versions",
        Cardinality.Seq,
    )
    schema._properties["Versions"] = array  # noqa: SLF001
    assert schema.get_versions_property() is array


def test_get_versions_property_returns_none_for_non_array_value() -> None:
    schema = _mm()
    schema._properties["Versions"] = ["v1"]  # noqa: SLF001
    assert schema.get_versions_property() is None


# --- Manifest ---------------------------------------------------------


def test_manifest_wraps_non_list_value_for_get() -> None:
    schema = _mm()
    ref = _resource_ref(schema)
    schema._properties["Manifest"] = ref  # noqa: SLF001 — exercise wrap branch
    assert schema.get_manifest() == [ref]


# --- LastURL ----------------------------------------------------------


def test_last_url_property_typed_round_trip_and_clear() -> None:
    schema = _mm()
    url = URLType(
        schema._metadata, schema._namespace, schema._prefix, "LastURL", "https://e/x"  # noqa: SLF001
    )
    schema.set_last_url_property(url)
    assert schema.get_last_url_property() is url
    assert schema.get_last_url() == "https://e/x"
    schema.set_last_url_property(None)
    assert "LastURL" not in schema._properties  # noqa: SLF001


# --- SaveID -----------------------------------------------------------


def test_save_id_get_with_integer_type_unwraps_value() -> None:
    schema = _mm()
    schema.set_save_id(7)
    assert schema.get_save_id() == 7
    assert isinstance(schema.get_save_id_property(), IntegerType)


def test_save_id_get_returns_int_for_plain_int() -> None:
    schema = _mm()
    schema._properties["SaveID"] = 11  # noqa: SLF001
    assert schema.get_save_id() == 11


def test_save_id_get_returns_int_for_numeric_string() -> None:
    schema = _mm()
    schema._properties["SaveID"] = " 42 "  # noqa: SLF001
    assert schema.get_save_id() == 42


def test_save_id_get_returns_none_for_unparseable_string() -> None:
    schema = _mm()
    schema._properties["SaveID"] = "abc"  # noqa: SLF001
    assert schema.get_save_id() is None


def test_save_id_get_coerces_bool_to_int() -> None:
    schema = _mm()
    schema._properties["SaveID"] = True  # noqa: SLF001
    assert schema.get_save_id() == 1


def test_save_id_get_returns_none_for_unknown_type() -> None:
    schema = _mm()
    schema._properties["SaveID"] = 3.14  # noqa: SLF001
    assert schema.get_save_id() is None


def test_save_id_property_get_returns_none_for_bool() -> None:
    schema = _mm()
    schema._properties["SaveID"] = False  # noqa: SLF001
    assert schema.get_save_id_property() is None


def test_save_id_property_get_materialises_from_int() -> None:
    schema = _mm()
    schema._properties["SaveID"] = 99  # noqa: SLF001
    prop = schema.get_save_id_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 99


def test_save_id_property_get_returns_none_for_unknown_type() -> None:
    schema = _mm()
    schema._properties["SaveID"] = 3.14  # noqa: SLF001
    assert schema.get_save_id_property() is None


def test_save_id_setters_clear_and_round_trip_typed_property() -> None:
    schema = _mm()
    typed = IntegerType(
        schema._metadata, schema._namespace, schema._prefix, "SaveID", 5  # noqa: SLF001
    )
    schema.set_save_id_property(typed)
    assert schema.get_save_id_property() is typed
    schema.set_save_id_property(None)
    assert "SaveID" not in schema._properties  # noqa: SLF001
    schema.set_save_id(3)
    schema.set_save_id(None)
    assert "SaveID" not in schema._properties  # noqa: SLF001


# --- Ingredients ------------------------------------------------------


def test_ingredients_typed_append_and_wrap_non_list() -> None:
    schema = _mm()
    ref = _resource_ref(schema)
    schema.add_ingredient(ref)
    assert schema.get_ingredients() == [ref]
    schema._properties["Ingredients"] = ref  # noqa: SLF001 — exercise wrap branch
    assert schema.get_ingredients() == [ref]


def test_get_ingredients_property_returns_array_property() -> None:
    schema = _mm()
    array = ArrayProperty(
        schema._metadata,  # noqa: SLF001
        schema._namespace,  # noqa: SLF001
        schema._prefix,  # noqa: SLF001
        "Ingredients",
        Cardinality.Bag,
    )
    schema._properties["Ingredients"] = array  # noqa: SLF001
    assert schema.get_ingredients_property() is array


def test_get_ingredients_property_returns_none_for_non_array_value() -> None:
    schema = _mm()
    schema._properties["Ingredients"] = []  # noqa: SLF001
    assert schema.get_ingredients_property() is None
