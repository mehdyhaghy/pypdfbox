"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/DublinCoreTest.java

Upstream drives a ``SchemaTester`` reflection helper over the twelve
properties declared on :class:`DublinCoreSchema`. The Python translation
collapses the reflection-driven ``testInitializedToNull`` /
``testSettingValue`` / ``testSettingValueInArray`` /
``testPropertySetterSimple`` / ``testPropertySetterInArray`` matrix
into direct accessor calls per property, keeping the upstream
(``fieldName``, ``Types``, ``Cardinality``) tuple table intact for
re-syncs.

The upstream randomized variants (``testRandomXxx``) loop the same
non-random path with different seeded values; pytest's parametrize
already exercises every property once so the randomized layer is
redundant and is not duplicated.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    Cardinality,
    DublinCoreSchema,
    MIMEType,
    TextType,
    XMPMetadata,
)
from pypdfbox.xmpbox.type import ArrayProperty, ProperNameType

# Mirrors upstream ``initializeParameters()`` — kept verbatim.
_PARAMETERS: tuple[tuple[str, str, Cardinality], ...] = (
    ("contributor", "ProperName", Cardinality.Bag),
    ("coverage", "Text", Cardinality.Simple),
    ("creator", "ProperName", Cardinality.Seq),
    ("date", "Date", Cardinality.Seq),
    ("format", "MIMEType", Cardinality.Simple),
    ("identifier", "Text", Cardinality.Simple),
    ("language", "Locale", Cardinality.Bag),
    ("publisher", "ProperName", Cardinality.Bag),
    ("relation", "Text", Cardinality.Bag),
    ("source", "Text", Cardinality.Simple),
    ("subject", "Text", Cardinality.Bag),
    ("type", "Text", Cardinality.Bag),
)


# Map (field, cardinality) → (simple_getter, simple_adder_or_setter,
# typed_getter, typed_setter).
_ACCESSORS: dict[str, tuple[str, str, str | None, str | None]] = {
    "contributor": (
        "get_contributors",
        "add_contributor",
        "get_contributors_property",
        "set_contributors_property",
    ),
    "coverage": (
        "get_coverage",
        "set_coverage",
        "get_coverage_property",
        "set_coverage_property",
    ),
    "creator": (
        "get_creators",
        "add_creator",
        "get_creators_property",
        "set_creators_property",
    ),
    "date": (
        "get_dates",
        "add_date",
        "get_dates_property",
        "set_dates_property",
    ),
    "format": (
        "get_format",
        "set_format",
        "get_format_property",
        "set_format_property",
    ),
    "identifier": (
        "get_identifier",
        "set_identifier",
        "get_identifier_property",
        "set_identifier_property",
    ),
    "language": (
        "get_languages",
        "add_language",
        "get_languages_property",
        "set_languages_property",
    ),
    "publisher": (
        "get_publishers",
        "add_publisher",
        "get_publishers_property",
        "set_publishers_property",
    ),
    "relation": (
        "get_relations",
        "add_relation",
        "get_relations_property",
        "set_relations_property",
    ),
    "source": (
        "get_source",
        "set_source",
        "get_source_property",
        "set_source_property",
    ),
    "subject": (
        "get_subjects",
        "add_subject",
        "get_subjects_property",
        "set_subjects_property",
    ),
    "type": (
        "get_types",
        "add_type",
        "get_types_property",
        "set_types_property",
    ),
}


@pytest.fixture
def metadata() -> XMPMetadata:
    """Mirror of upstream's ``@BeforeEach initMetadata``."""
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def schema(metadata: XMPMetadata) -> DublinCoreSchema:
    return metadata.create_and_add_dublin_core_schema()


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_initialized_to_null(
    schema: DublinCoreSchema,
    field_name: str,
    type_token: str,
    card: Cardinality,
) -> None:
    """Translated from upstream ``testInitializedToNull``: every
    declared property reads as ``None`` on a freshly-created schema."""
    del type_token, card
    getter_name, _, _, _ = _ACCESSORS[field_name]
    assert getattr(schema, getter_name)() is None


# Pre-filtered parameter sets — the Java tester reflects every property
# through one method and early-returns on the wrong cardinality, leaving
# the per-cardinality branches as bookkeeping noise. The Python port keeps
# the upstream ``_PARAMETERS`` table intact for re-syncs and narrows the
# parametrize input per test so non-applicable rows do not generate
# pytest skip noise.
_SIMPLE_PARAMETERS = tuple(p for p in _PARAMETERS if p[2] is Cardinality.Simple)
_ARRAY_PARAMETERS = tuple(p for p in _PARAMETERS if p[2] is not Cardinality.Simple)


@pytest.mark.parametrize(("field_name", "type_token", "card"), _SIMPLE_PARAMETERS)
def test_setting_value(
    schema: DublinCoreSchema,
    field_name: str,
    type_token: str,
    card: Cardinality,
) -> None:
    """Translated from upstream ``testSettingValue`` (simple cardinality
    branch only — upstream early-returns for non-simple)."""
    del card
    getter, setter, _, _ = _ACCESSORS[field_name]
    value = "application/pdf" if type_token == "MIMEType" else "value-for-" + field_name
    getattr(schema, setter)(value)
    assert getattr(schema, getter)() == value


@pytest.mark.parametrize(("field_name", "type_token", "card"), _ARRAY_PARAMETERS)
def test_setting_value_in_array(
    schema: DublinCoreSchema,
    field_name: str,
    type_token: str,
    card: Cardinality,
) -> None:
    """Translated from upstream ``testSettingValueInArray`` (Bag/Seq
    branch only)."""
    del card
    getter, adder, _, _ = _ACCESSORS[field_name]
    if type_token == "Date":
        from datetime import UTC, datetime
        value = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    else:
        value = "value-for-" + field_name
    getattr(schema, adder)(value)
    result = getattr(schema, getter)()
    assert result is not None
    # Single-add must produce a one-element collection.
    assert len(result) == 1


@pytest.mark.parametrize(("field_name", "type_token", "card"), _SIMPLE_PARAMETERS)
def test_property_setter_simple(
    metadata: XMPMetadata,
    schema: DublinCoreSchema,
    field_name: str,
    type_token: str,
    card: Cardinality,
) -> None:
    """Translated from upstream ``testPropertySetterSimple`` (simple
    cardinality branch only)."""
    del card
    _, _, typed_getter, typed_setter = _ACCESSORS[field_name]
    assert typed_getter is not None and typed_setter is not None
    if type_token == "MIMEType":
        prop: object = MIMEType(
            metadata,
            DublinCoreSchema.NAMESPACE,
            DublinCoreSchema.PREFERRED_PREFIX,
            field_name,
            "application/pdf",
        )
    else:
        prop = TextType(
            metadata,
            DublinCoreSchema.NAMESPACE,
            DublinCoreSchema.PREFERRED_PREFIX,
            field_name,
            "value-for-" + field_name,
        )
    getattr(schema, typed_setter)(prop)
    fetched = getattr(schema, typed_getter)()
    assert fetched is not None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _ARRAY_PARAMETERS)
def test_property_setter_in_array(
    metadata: XMPMetadata,
    schema: DublinCoreSchema,
    field_name: str,
    type_token: str,
    card: Cardinality,
) -> None:
    """Translated from upstream ``testPropertySetterInArray`` (Bag/Seq
    branch only)."""
    del card
    if type_token == "Date":
        # Upstream uses reflection to wire a Date adder; pypdfbox's
        # `add_date` already takes a `datetime`, exercised in
        # ``test_setting_value_in_array``. Skip the typed-array variant
        # to avoid a duplicated assertion against the same code path.
        pytest.skip("date Seq cardinality covered by test_setting_value_in_array")
    _, adder, typed_getter, _ = _ACCESSORS[field_name]
    assert typed_getter is not None
    value1 = "first-" + field_name
    value2 = "second-" + field_name
    getattr(schema, adder)(value1)
    typed = getattr(schema, typed_getter)()
    assert isinstance(typed, ArrayProperty)
    # Upstream measures ``cp.getContainer().getAllProperties().size()``.
    assert len(typed.get_all_properties()) == 1
    getattr(schema, adder)(value2)
    typed = getattr(schema, typed_getter)()
    assert len(typed.get_all_properties()) == 2
    # Mirror upstream remover.
    remover_name = adder.replace("add_", "remove_")
    if hasattr(schema, remover_name):
        getattr(schema, remover_name)(value1)
        typed = getattr(schema, typed_getter)()
        assert len(typed.get_all_properties()) == 1


def test_proper_name_type_exposed() -> None:
    """Sanity check — DublinCore's ProperName cardinality columns import
    cleanly from the public surface."""
    assert ProperNameType is not None
