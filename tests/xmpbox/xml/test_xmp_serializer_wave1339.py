"""Coverage-boost wave 1339 tests for
:class:`pypdfbox.xmpbox.xml.xmp_serializer.XmpSerializer`.

Targets the flat-dict-to-AbstractField conversion path introduced in
wave 1337 — :meth:`_normalize_schema_fields`, :meth:`_iter_flat_typed`,
:meth:`_wrap_primitive`, and the per-schema cardinality hooks
(``_FIELD_CARDINALITIES`` / ``get_property_cardinality``).
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.boolean_type import BooleanType
from pypdfbox.xmpbox.type.date_type import DateType
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.lang_alt import LangAlt
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from pypdfbox.xmpbox.xmp_schema import XMPSchema

_NS = "urn:pypdfbox:wave1339"
_PREFIX = "w1339"


# ---------------------------------------------------------------------
# Helpers — a schema that stores values as flat-dict primitives (default
# XMPSchema behaviour), and a variant exposing schema-level cardinality
# overrides.
# ---------------------------------------------------------------------


class _PrimSchema(XMPSchema):
    NAMESPACE = _NS
    PREFERRED_PREFIX = _PREFIX

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata, _NS, _PREFIX)


class _SeqMappingSchema(_PrimSchema):
    """Schema whose ``_FIELD_CARDINALITIES`` declares an Seq override."""

    _FIELD_CARDINALITIES = {"ordered": Cardinality.Seq}


class _AltMethodSchema(_PrimSchema):
    """Schema with a method-based cardinality hook."""

    def get_property_cardinality(self, name: str):
        if name == "choices":
            return Cardinality.Alt
        return None


class _BadHookSchema(_PrimSchema):
    """Schema whose cardinality hook raises — serializer must fall back."""

    def get_property_cardinality(self, name: str):
        raise RuntimeError("hook is broken")


class _NonEnumHookSchema(_PrimSchema):
    """Schema whose hook returns a non-Cardinality value — must be ignored."""

    def get_property_cardinality(self, name: str):
        return "not-a-cardinality"


# ---------------------------------------------------------------------
# _wrap_primitive — each type branch
# ---------------------------------------------------------------------


def _serialize(metadata: XMPMetadata) -> bytes:
    out = io.BytesIO()
    XmpSerializer().serialize(metadata, out, with_xpacket=False)
    return out.getvalue()


def test_wrap_primitive_bool_to_boolean_type_serialises_capitalised() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["enabled"] = True
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">True<" in blob
    assert b"w1339:enabled" in blob


def test_wrap_primitive_bool_false_renders_as_false() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["enabled"] = False
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">False<" in blob


def test_wrap_primitive_int_to_integer_type() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["count"] = 42
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">42<" in blob
    assert b"w1339:count" in blob


def test_wrap_primitive_datetime_to_date_type() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["when"] = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"2026-05-17" in blob
    assert b"w1339:when" in blob


def test_wrap_primitive_str_to_text_type() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["title"] = "Hello"
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">Hello<" in blob


def test_wrap_primitive_list_defaults_to_bag() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["tags"] = ["alpha", "beta", "gamma"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"rdf:Bag" in blob
    assert b">alpha<" in blob
    assert b">beta<" in blob
    assert b">gamma<" in blob


def test_wrap_primitive_list_skips_non_string_items() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["mixed"] = ["a", 99, None, "b"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">a<" in blob
    assert b">b<" in blob
    # Numeric/None items are skipped.
    assert b">99<" not in blob


def test_wrap_primitive_dict_to_lang_alt() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["title"] = {"x-default": "Hello", "fr": "Bonjour"}
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"rdf:Alt" in blob
    assert b"Hello" in blob
    assert b"Bonjour" in blob


def test_wrap_primitive_dict_skips_non_string_values() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["title"] = {"x-default": "ok", "broken": 17}
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">ok<" in blob
    assert b">17<" not in blob


def test_wrap_primitive_none_value_is_skipped() -> None:
    """An unrecognised value type (None) yields None — caller drops it."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["nope"] = None
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    # Property doesn't appear in output.
    assert b"w1339:nope" not in blob


def test_wrap_primitive_unknown_type_is_skipped() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    schema._properties["odd"] = object()  # arbitrary, untyped
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"w1339:odd" not in blob


# ---------------------------------------------------------------------
# Cardinality hook — class mapping + method-based
# ---------------------------------------------------------------------


def test_cardinality_hint_class_mapping_uses_seq() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _SeqMappingSchema(metadata)
    schema._properties["ordered"] = ["one", "two"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"rdf:Seq" in blob
    assert b"rdf:Bag" not in blob


def test_cardinality_hint_method_returns_alt() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _AltMethodSchema(metadata)
    schema._properties["choices"] = ["red", "green"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"rdf:Alt" in blob


def test_cardinality_hint_method_returns_none_falls_back_to_bag() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _AltMethodSchema(metadata)
    schema._properties["other"] = ["x", "y"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    # ``other`` isn't in the override -> Bag.
    assert b"rdf:Bag" in blob


def test_cardinality_hook_raising_falls_back_to_bag() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _BadHookSchema(metadata)
    schema._properties["broken"] = ["a", "b"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    # Hook raised -> default Bag.
    assert b"rdf:Bag" in blob


def test_cardinality_hook_non_enum_value_ignored() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _NonEnumHookSchema(metadata)
    schema._properties["weird"] = ["a"]
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"rdf:Bag" in blob


def test_cardinality_hint_static_method_returns_none_for_no_schema() -> None:
    """Direct unit test for the static helper, hitting the schema=None
    early return."""
    result = XmpSerializer._cardinality_hint(None, "anything")
    assert result is None


# ---------------------------------------------------------------------
# _iter_flat_typed — preference for cached typed-properties
# ---------------------------------------------------------------------


def test_iter_flat_typed_prefers_cached_typed_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    # Wire a typed wrapper into the cache; the raw dict still holds the
    # primitive but the serialiser should honour the cached object.
    cached = TextType(metadata, _NS, _PREFIX, "tag", "TYPED-WINS")
    schema._properties["tag"] = "raw"
    schema._typed_properties["tag"] = cached
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b"TYPED-WINS" in blob
    assert b">raw<" not in blob


# ---------------------------------------------------------------------
# _normalize_schema_fields — non-dict iterable passthrough + empty
# ---------------------------------------------------------------------


def test_normalize_schema_fields_empty_dict_yields_nothing() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    # Schema rendered with no properties.
    assert b"rdf:Description" in blob


def test_normalize_schema_fields_passthrough_list_input() -> None:
    """Schema returning a list (not a dict) goes through the passthrough."""

    class _ListSchema(_PrimSchema):
        def get_all_properties(self):
            return [TextType(metadata, _NS, _PREFIX, "passthrough", "hi")]

    metadata = XMPMetadata.create_xmp_metadata()
    schema = _ListSchema(metadata)
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    assert b">hi<" in blob


def test_normalize_schema_fields_none_raw_fields_returns_empty() -> None:
    """Schema whose ``get_all_properties`` returns ``None`` triggers the
    ``if raw_fields:`` falsy branch."""

    class _NoneSchema(_PrimSchema):
        def get_all_properties(self):
            return None

    metadata = XMPMetadata.create_xmp_metadata()
    schema = _NoneSchema(metadata)
    metadata.add_schema(schema)
    blob = _serialize(metadata)
    # No crash; just an empty description.
    assert b"rdf:Description" in blob


# ---------------------------------------------------------------------
# _wrap_primitive — direct unit tests of the helper
# ---------------------------------------------------------------------


def test_wrap_primitive_direct_invocation_for_each_type() -> None:
    ser = XmpSerializer()
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _PrimSchema(metadata)
    metadata.add_schema(schema)
    # Bool
    field = ser._wrap_primitive(metadata, _NS, _PREFIX, "b", True, schema=schema)
    assert isinstance(field, BooleanType)
    # Int
    field = ser._wrap_primitive(metadata, _NS, _PREFIX, "i", 1, schema=schema)
    assert isinstance(field, IntegerType)
    # Datetime
    field = ser._wrap_primitive(
        metadata, _NS, _PREFIX, "d", datetime(2026, 1, 1), schema=schema
    )
    assert isinstance(field, DateType)
    # Str
    field = ser._wrap_primitive(metadata, _NS, _PREFIX, "s", "x", schema=schema)
    assert isinstance(field, TextType)
    # List
    field = ser._wrap_primitive(metadata, _NS, _PREFIX, "l", ["a"], schema=schema)
    assert isinstance(field, ArrayProperty)
    # Dict
    field = ser._wrap_primitive(
        metadata, _NS, _PREFIX, "alt", {"x-default": "v"}, schema=schema
    )
    assert isinstance(field, LangAlt)


def test_wrap_primitive_no_schema_uses_bag_default() -> None:
    """Calling without ``schema=`` (kwarg default) still works for lists."""
    ser = XmpSerializer()
    metadata = XMPMetadata.create_xmp_metadata()
    field = ser._wrap_primitive(metadata, _NS, _PREFIX, "items", ["a", "b"])
    assert isinstance(field, ArrayProperty)
    assert field.get_array_type() == Cardinality.Bag


# ---------------------------------------------------------------------
# _append_field — non-AbstractField primitive skip + simple-property
# fallback to ``get_raw_value`` when no ``get_string_value``
# ---------------------------------------------------------------------


def test_append_field_skips_non_abstract_field_input() -> None:
    """Calling ``serialize_fields`` directly with a raw primitive must not
    crash — the dispatcher silently drops the entry."""
    from xml.dom.minidom import Document

    ser = XmpSerializer()
    doc = Document()
    root = doc.createElement("root")
    doc.appendChild(root)
    # Hand the dispatcher a raw primitive — must not crash, must not append.
    ser.serialize_fields(doc, root, ["not-a-field"], "", None, True)
    assert root.firstChild is None


def test_append_field_uses_raw_value_when_no_string_value() -> None:
    """A simple-property-shaped object missing ``get_string_value`` is
    rendered via ``get_raw_value`` instead — covers the ``else`` branch
    of the value-extraction dispatch."""
    from xml.dom.minidom import Document

    from pypdfbox.xmpbox.type.abstract_field import AbstractField
    from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty

    class _NoStrSimple:
        """Minimal AbstractField-shaped object for the raw_value branch.

        Registered as an ``AbstractSimpleProperty`` virtual subclass so
        ``isinstance`` passes, but lacks ``get_string_value`` so the
        serializer falls back to ``get_raw_value``.
        """

        def get_property_name(self):
            return "bare"

        def get_prefix(self):
            return _PREFIX

        def get_namespace(self):
            return _NS

        def get_raw_value(self):
            return "RAW-VAL"

    AbstractField.register(_NoStrSimple)
    AbstractSimpleProperty.register(_NoStrSimple)

    ser = XmpSerializer()
    doc = Document()
    root = doc.createElement("root")
    doc.appendChild(root)
    ser._append_field(doc, root, _NoStrSimple(), _NS, _PREFIX)
    assert root.firstChild.firstChild.nodeValue == "RAW-VAL"
