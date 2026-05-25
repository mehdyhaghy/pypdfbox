"""Wave 1397 branch-coverage tests for ``DomXmpParser``.

Closes False-branch arrows in the alias parsers and the structured-li
builder:

* ``get_namespace_table`` 369->367 — schema class with empty
  ``PREFERRED_PREFIX`` is skipped
* ``parse_describe_element`` 388->390 — caller supplies a non-None
  ``per_ns`` accumulator (skip lazy allocation)
* ``_build_structured_from_li`` 866->862 — attribute-form unknown attr
  (not in field_types) is skipped
* ``_build_structured_from_li`` 875->884 — single child whose
  inner_ns/local isn't rdf:Description — falls through to element-form
* ``_build_structured_from_li`` 881->877 — Description wrapper carrying
  an unknown attr (not in field_types)
* ``parse_description_root`` 1204->1206 — caller supplies a non-None
  namespace_prefixes dict
* ``parse_description_root_attr`` 1223->1225 — caller supplies a
  non-None namespace_prefixes dict
* ``parse_children_as_properties`` 1244->1246 — caller supplies a
  non-None namespace_prefixes dict
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.type.layer_type import LayerType

_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _parser() -> DomXmpParser:
    return DomXmpParser()


def test_get_namespace_table_skips_schemas_with_empty_preferred_prefix(monkeypatch) -> None:
    """Closes 369->367: a schema class with an empty
    ``PREFERRED_PREFIX`` is filtered out of the prefix → URI table."""
    from pypdfbox.xmpbox import dom_xmp_parser as dxp

    class _EmptyPrefixSchema:
        PREFERRED_PREFIX = ""

    monkeypatch.setitem(
        dxp._SCHEMA_REGISTRY, "http://example/empty-prefix/", _EmptyPrefixSchema  # noqa: SLF001
    )
    table = _parser().get_namespace_table()
    # The empty-prefix schema did NOT contribute an entry; "rdf" + "xml"
    # are still the only pre-registered keys, plus the genuine registered
    # schemas (their PREFERRED_PREFIX is non-empty).
    assert "" not in table
    assert table.get("rdf") == _RDF_NS


def test_parse_describe_element_with_supplied_per_ns_accumulator() -> None:
    """Closes 388->390: caller passes a pre-built per_ns accumulator —
    the lazy ``per_ns = {}`` branch is skipped."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    desc = ET.fromstring(
        f'<rdf:Description xmlns:rdf="{_RDF_NS}" rdf:about=""/>'
    )
    existing: dict[str, object] = {"seeded": object()}
    out = parser.parse_describe_element(desc, metadata, existing)  # type: ignore[arg-type]
    # The same dict instance is returned (no fresh allocation).
    assert out is existing
    assert "seeded" in out


def test_build_structured_from_li_skips_unknown_attr_form_attr() -> None:
    """Closes 866->862: an attribute-form li attr whose local name is
    not in the field's ``_FIELD_TYPES`` is silently skipped."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    schema = type("_S", (), {"get_metadata": lambda self: metadata, "_prefix": "x"})()
    # Build a LayerType-style li with a known attr AND an unknown attr.
    li_xml = (
        f'<rdf:li xmlns:rdf="{_RDF_NS}" '
        f'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/" '
        f'photoshop:LayerName="L1" '
        f'photoshop:Unknown="ignored"/>'
    )
    li = ET.fromstring(li_xml)
    instance = parser._build_structured_from_li(li, LayerType, schema)  # type: ignore[arg-type]  # noqa: SLF001
    assert instance is not None
    # LayerName was captured; Unknown was filtered.
    assert instance.get_layer_name() == "L1"


def test_build_structured_from_li_single_non_description_child_treated_as_field() -> None:
    """Closes 875->884: a single child whose tag is NOT rdf:Description
    falls through to the element-form loop directly (no Description-attr
    unwrap)."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    schema = type("_S", (), {"get_metadata": lambda self: metadata, "_prefix": "x"})()
    li_xml = (
        f'<rdf:li xmlns:rdf="{_RDF_NS}" '
        f'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">'
        f'<photoshop:LayerName>directName</photoshop:LayerName>'
        f'</rdf:li>'
    )
    li = ET.fromstring(li_xml)
    instance = parser._build_structured_from_li(li, LayerType, schema)  # type: ignore[arg-type]  # noqa: SLF001
    assert instance is not None
    assert instance.get_layer_name() == "directName"


def test_build_structured_from_li_description_wrapper_with_unknown_attr() -> None:
    """Closes 881->877: an rdf:Description wrapper carrying an attribute
    whose local-name isn't in the field's _FIELD_TYPES is skipped."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    schema = type("_S", (), {"get_metadata": lambda self: metadata, "_prefix": "x"})()
    li_xml = (
        f'<rdf:li xmlns:rdf="{_RDF_NS}" '
        f'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">'
        f'<rdf:Description '
        f'photoshop:LayerName="WrappedName" '
        f'photoshop:Unknown="ignored"/>'
        f'</rdf:li>'
    )
    li = ET.fromstring(li_xml)
    instance = parser._build_structured_from_li(li, LayerType, schema)  # type: ignore[arg-type]  # noqa: SLF001
    assert instance is not None
    assert instance.get_layer_name() == "WrappedName"


def test_parse_description_root_with_supplied_namespace_prefixes() -> None:
    """Closes 1204->1206: caller supplies a non-None
    namespace_prefixes dict — skip lazy allocation."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    desc = ET.fromstring(
        f'<rdf:Description xmlns:rdf="{_RDF_NS}" rdf:about=""/>'
    )
    nsp = {"existing": "http://example/"}
    out = parser.parse_description_root(metadata, desc, None, nsp)
    assert isinstance(out, dict)


def test_parse_description_root_attr_with_supplied_namespace_prefixes() -> None:
    """Closes 1223->1225: caller supplies a non-None
    namespace_prefixes dict — skip lazy allocation."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    desc = ET.fromstring(
        f'<rdf:Description xmlns:rdf="{_RDF_NS}" '
        f'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        f'rdf:about=""/>'
    )
    nsp = {"dc": "http://purl.org/dc/elements/1.1/"}
    parser.parse_description_root_attr(
        metadata,
        desc,
        "{http://purl.org/dc/elements/1.1/}identifier",
        "test-id",
        {},
        nsp,
    )


def test_parse_children_as_properties_with_supplied_namespace_prefixes() -> None:
    """Closes 1244->1246: caller supplies a non-None
    namespace_prefixes dict — skip lazy allocation."""
    parser = _parser()
    metadata = XMPMetadata.create_xmp_metadata()
    desc = ET.fromstring(
        f'<rdf:Description xmlns:rdf="{_RDF_NS}" rdf:about=""/>'
    )
    nsp = {"dc": "http://purl.org/dc/elements/1.1/"}
    parser.parse_children_as_properties(metadata, desc, {}, nsp)
