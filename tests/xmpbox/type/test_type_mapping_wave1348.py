"""Wave 1348 coverage-boost tests for ``pypdfbox.xmpbox.type.type_mapping``.

Targets the residual branches:

  * ``initialize`` ``continue`` arm for a structured class that exposes no
    ``NAMESPACE`` attribute (line 299).
  * ``get_specified_property_type`` multi-struct namespace branches: the
    ``parent_type_name`` match (line 482-484) and the local-part lookup
    fallback when no parent name matches (lines 485-489).
  * ``get_associated_schema_object`` fallback when the
    :class:`XMPMetadata` class no longer exposes
    ``create_and_add_default_schema_for_namespace`` (line 606 — already
    covered for the "creator exists" arm; this test pins down the
    fallback path).
"""
from __future__ import annotations

import pytest

import pypdfbox.xmpbox.type.type_mapping as type_mapping_module
from pypdfbox.xmpbox import TypeMapping, XMPMetadata
from pypdfbox.xmpbox.type.array_property import Cardinality
from pypdfbox.xmpbox.type.type_mapping import (
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


# ---------- initialize() — class without NAMESPACE attribute ----------


def test_initialize_skips_structured_class_without_namespace(
    monkeypatch: pytest.MonkeyPatch, metadata: XMPMetadata
) -> None:
    """Line 299: a structured class with no ``NAMESPACE`` attribute is
    skipped during ``initialize``'s ``structured_namespaces2`` build."""

    class _NoNamespaceStruct:
        # Intentionally missing NAMESPACE.
        pass

    patched = {"NoNs": _NoNamespaceStruct, **type_mapping_module._STRUCTURED}
    monkeypatch.setattr(type_mapping_module, "_STRUCTURED", patched)

    # Re-initialising must not raise.
    tm = TypeMapping(metadata)
    # Sanity: the no-namespace class did not contaminate the
    # namespace-keyed lookup.
    for ns_list in tm._structured_namespaces2.values():  # noqa: SLF001
        assert "NoNs" not in ns_list


# ---------- get_specified_property_type — multi-struct namespace ----------


def test_get_specified_property_type_multi_struct_parent_match(
    mapping: TypeMapping,
) -> None:
    """Lines 482-484: when a single namespace hosts multiple structured
    types, the lookup first checks if any matches ``parent_type_name``."""
    ns = "http://example.com/multi-struct/"
    # Inject two synthetic structured types under the same namespace.
    desc_a = PropertiesDescription()
    desc_a.add_new_property(
        "field_a", PropertyType(type="Text", card=Cardinality.Simple)
    )
    desc_b = PropertiesDescription()
    desc_b.add_new_property(
        "field_b", PropertyType(type="Integer", card=Cardinality.Simple)
    )
    mapping._structured_namespaces2[ns] = ["TypeA", "TypeB"]  # noqa: SLF001
    mapping._structured_mappings["TypeA"] = desc_a  # noqa: SLF001
    mapping._structured_mappings["TypeB"] = desc_b  # noqa: SLF001

    # Parent match: even if local_part wouldn't normally resolve, the
    # parent_type_name overrides.
    result = mapping.get_specified_property_type(
        (ns, "anything"), parent_type_name="TypeB"
    )
    assert result is not None
    assert result.type == "TypeB"


def test_get_specified_property_type_multi_struct_local_part_match(
    mapping: TypeMapping,
) -> None:
    """Lines 485-488: when no struct matches ``parent_type_name``, the
    lookup falls back to scanning each struct's property list for
    ``local_part``."""
    ns = "http://example.com/multi-struct-lp/"
    desc_a = PropertiesDescription()
    desc_a.add_new_property(
        "field_a", PropertyType(type="Text", card=Cardinality.Simple)
    )
    desc_b = PropertiesDescription()
    desc_b.add_new_property(
        "field_b", PropertyType(type="Integer", card=Cardinality.Simple)
    )
    mapping._structured_namespaces2[ns] = ["TypeA", "TypeB"]  # noqa: SLF001
    mapping._structured_mappings["TypeA"] = desc_a  # noqa: SLF001
    mapping._structured_mappings["TypeB"] = desc_b  # noqa: SLF001

    # No parent match; field_b lives on TypeB so the result picks TypeB.
    result = mapping.get_specified_property_type((ns, "field_b"))
    assert result is not None
    assert result.type == "TypeB"


def test_get_specified_property_type_multi_struct_no_match_returns_none(
    mapping: TypeMapping,
) -> None:
    """Line 489: a multi-struct namespace whose neither parent nor field
    match yields ``None``."""
    ns = "http://example.com/multi-struct-none/"
    desc_a = PropertiesDescription()
    desc_b = PropertiesDescription()
    mapping._structured_namespaces2[ns] = ["TypeA", "TypeB"]  # noqa: SLF001
    mapping._structured_mappings["TypeA"] = desc_a  # noqa: SLF001
    mapping._structured_mappings["TypeB"] = desc_b  # noqa: SLF001

    assert (
        mapping.get_specified_property_type((ns, "nothing-here")) is None
    )


# ---------- get_associated_schema_object — fallback to schema factory ----


def test_get_associated_schema_object_falls_back_to_factory(
    mapping: TypeMapping,
    metadata: XMPMetadata,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 607-609: when ``XMPMetadata.create_and_add_default_schema_for_namespace``
    is unavailable, the helper falls back to returning the schema-factory
    record."""
    # Register a namespace that the mapping recognises as defined.
    ns = "http://example.com/factory-only-schema/"
    mapping.add_new_name_space(ns)
    factory = mapping.get_schema_factory(ns)
    assert factory is not None

    # Remove the creator method so the fallback arm is taken.
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata as _XMPMetadata

    monkeypatch.delattr(
        _XMPMetadata,
        "create_and_add_default_schema_for_namespace",
        raising=False,
    )
    result = mapping.get_associated_schema_object(metadata, ns, "fac")
    assert isinstance(result, _SchemaFactory)
