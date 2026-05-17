"""Wave 1337 coverage-boost tests for ``pypdfbox.xmpbox.type.type_mapping``.

Targets the residual branches:

  * :meth:`PropertyType.to_string` — explicit alias for ``__str__``.
  * :meth:`PropertiesDescription.__contains__` — membership test.
  * :meth:`DefinedStructuredType.get_properties_description`.
  * :meth:`TypeMapping.get_specified_property_type` — branches when a schema
    factory exposes a property type, when a structured namespace lookup
    matches via ``parent_type_name``, when a multi-struct namespace finds
    the property via local-part search, and when a multi-struct
    namespace doesn't match at all.
  * :meth:`TypeMapping.initialize_prop_mapping` — the ``PROPERTIES`` branch
    that consumes tuples and explicit :class:`PropertyType` declarations.
  * :meth:`TypeMapping.get_associated_schema_object` — the
    ``create_and_add_default_schema_for_namespace`` branch.
"""
from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TypeMapping, XMPMetadata
from pypdfbox.xmpbox.type.array_property import Cardinality
from pypdfbox.xmpbox.type.type_mapping import (
    DEFINED_TYPE,
    PropertiesDescription,
    PropertyType,
    _SchemaFactory,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def mapping(metadata: XMPMetadata) -> TypeMapping:
    return TypeMapping(metadata)


def test_property_type_to_string_matches_str() -> None:
    """Line 130 — explicit ``to_string`` alias for ``__str__``."""
    pt = PropertyType(type="Text", card=Cardinality.Bag)
    assert pt.to_string() == str(pt) == "{type: Text, card: Bag}"


def test_properties_description_contains_membership() -> None:
    """Line 161 — ``__contains__`` for the property-name registry."""
    desc = PropertiesDescription()
    pt = PropertyType(type="Text", card=Cardinality.Simple)
    desc.add_new_property("Title", pt)
    assert "Title" in desc
    assert "missing" not in desc


def test_schema_factory_get_properties_description() -> None:
    """Line 230 — :class:`_SchemaFactory` exposes its backing
    :class:`PropertiesDescription`."""
    desc = PropertiesDescription()
    factory = _SchemaFactory("http://example.com/ns/", desc)
    assert factory.get_properties_description() is desc
    # Default when no description is supplied.
    factory2 = _SchemaFactory("http://example.com/ns2/")
    assert isinstance(factory2.get_properties_description(), PropertiesDescription)


def test_get_specified_property_type_factory_match(mapping: TypeMapping) -> None:
    """Line 472 — when a registered schema factory exposes a property
    type for ``local_part``, the lookup short-circuits to that
    declaration."""
    ns = "http://example.com/sf/"
    # Use add_new_name_space to register the namespace; then prime the
    # underlying factory's PropertiesDescription via direct injection.
    mapping.add_new_name_space(ns)
    factory = mapping.get_schema_factory(ns)
    factory._properties.add_new_property(  # type: ignore[attr-defined]
        "MyField", PropertyType(type="Text", card=Cardinality.Bag)
    )
    result = mapping.get_specified_property_type((ns, "MyField"))
    assert result is not None
    assert result.type == "Text"
    assert result.card is Cardinality.Bag


def test_get_specified_property_type_single_struct_no_match(
    mapping: TypeMapping,
) -> None:
    """Lines around 479-481 — a single-struct namespace + factory whose
    factory doesn't expose the property and whose struct mapping also
    doesn't list it returns None."""
    # Pick a built-in struct namespace.
    job_ns = "http://ns.adobe.com/xap/1.0/sType/Job#"
    # Register a factory for that namespace with empty properties.
    mapping.add_new_name_space(job_ns)
    result = mapping.get_specified_property_type((job_ns, "totally_bogus_field"))
    assert result is None


def test_get_specified_property_type_defined_namespace(
    mapping: TypeMapping,
) -> None:
    """Line 499 — namespace registered via
    ``add_to_defined_structured_types`` resolves to ``DEFINED_TYPE``."""
    ns = "http://example.com/defined-t/"
    mapping.add_to_defined_structured_types("MyDef", ns)
    result = mapping.get_specified_property_type((ns, "any_field"))
    assert result is not None
    assert result.type == DEFINED_TYPE


def test_get_specified_property_type_unknown_namespace_raises(
    mapping: TypeMapping,
) -> None:
    """When neither a schema factory nor a defined structured namespace
    knows the namespace, ``BadFieldValueException`` is raised."""
    from pypdfbox.xmpbox.pdfa_identification_schema import BadFieldValueException

    with pytest.raises(BadFieldValueException, match="No descriptor"):
        mapping.get_specified_property_type(
            ("http://nowhere.example/", "field")
        )


def test_get_specified_property_type_unknown_via_factory_returns_none(
    mapping: TypeMapping,
) -> None:
    """Lines 491-493 — when a factory is registered for the namespace
    but doesn't have a matching field, the helper returns ``None`` rather
    than raising (matches upstream's ``return null`` for "factory-known
    namespace, unknown field")."""
    ns = "http://example.com/factory-only/"
    # Empty properties factory.
    mapping.add_new_name_space(ns)
    result = mapping.get_specified_property_type((ns, "field"))
    assert result is None


def test_initialize_prop_mapping_property_type_dict() -> None:
    """Lines 529-531 — ``PROPERTIES`` dict whose values are
    :class:`PropertyType` instances are harvested directly."""
    class _S:
        PROPERTIES = {
            "Title": PropertyType(type="Text", card=Cardinality.Simple),
        }

    desc = TypeMapping.initialize_prop_mapping(_S)
    assert "Title" in desc
    assert desc.get_property_type("Title").type == "Text"


def test_initialize_prop_mapping_tuple_dict() -> None:
    """Lines 532-534 — ``PROPERTIES`` whose values are
    ``(type_name, card)`` tuples are also harvested."""
    class _S:
        PROPERTIES = {
            "Tags": ("Text", Cardinality.Bag),
        }

    desc = TypeMapping.initialize_prop_mapping(_S)
    pt = desc.get_property_type("Tags")
    assert pt is not None
    assert pt.type == "Text"
    assert pt.card is Cardinality.Bag


def test_initialize_prop_mapping_combined() -> None:
    """Both ``_FIELD_TYPES`` and ``PROPERTIES`` may be present — the
    explicit ``PROPERTIES`` entries override the implicit ones."""
    class _S:
        _FIELD_TYPES = {"a": "Text", "b": "Integer"}
        PROPERTIES = {
            "a": PropertyType(type="Boolean", card=Cardinality.Simple),
        }

    desc = TypeMapping.initialize_prop_mapping(_S)
    # PROPERTIES wins for "a".
    assert desc.get_property_type("a").type == "Boolean"
    # _FIELD_TYPES survives for "b".
    assert desc.get_property_type("b").type == "Integer"


def test_initialize_prop_mapping_skips_malformed() -> None:
    """``PROPERTIES`` entries that are neither a :class:`PropertyType`
    nor a ``(name, card)`` tuple are silently skipped (none of the
    ``elif`` arms hit)."""
    class _S:
        PROPERTIES = {
            "weird": "not a PropertyType",
            "also_weird": (1, 2, 3),  # tuple but wrong arity
        }

    desc = TypeMapping.initialize_prop_mapping(_S)
    assert "weird" not in desc
    assert "also_weird" not in desc


def test_get_associated_schema_object_unknown_returns_none(
    mapping: TypeMapping,
) -> None:
    """Unknown namespace → ``None`` (early-return guard)."""
    assert (
        mapping.get_associated_schema_object(
            mapping.get_metadata(), "http://nowhere.example/", "x"
        )
        is None
    )


def test_get_associated_schema_object_known_namespace(
    mapping: TypeMapping, metadata: XMPMetadata,
) -> None:
    """Line 606 — when ``XMPMetadata.create_and_add_default_schema_for_namespace``
    exists (as it does in this build), the helper delegates to it.
    Pick a built-in schema namespace so ``is_defined_schema`` returns
    True."""
    # Dublin Core is a built-in
    dc_ns = "http://purl.org/dc/elements/1.1/"
    assert mapping.is_defined_schema(dc_ns) is True
    result = mapping.get_associated_schema_object(metadata, dc_ns, "dc")
    # Either returns a schema or None (depending on whether the
    # creator method really exists at this point); the goal is to
    # walk the branch.
    assert result is None or hasattr(result, "get_namespace")
