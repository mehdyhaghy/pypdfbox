"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/PhotoshopSchemaTest.java

Upstream's tests rely on a reflection-driven ``SchemaTester`` helper that
exercises generic ``getXxxProperty`` / ``setXxxProperty`` accessors plus the
typed ``addProperty(AbstractField)`` machinery. Wave 32 lands the typed
``*_property`` accessors so the upstream parameterisation can run end-to-end
against the new wrappers; the translation below covers the simple-cardinality
parameter rows. ``*InArray`` rows that depend on ``getContainer().getAllProperties()``
introspection (none for PhotoshopSchema in upstream — the schema has no
array-cardinality entries) are left as no-op skips with a one-line marker.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    DateType,
    IntegerType,
    LayerType,
    PhotoshopSchema,
    ProperNameType,
    TextType,
    URIType,
    XMPMetadata,
)

# Upstream initializeParameters() — kept verbatim so future re-syncs are diffable.
_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    ("AncestorID", "URI", "Simple"),
    ("AuthorsPosition", "Text", "Simple"),
    ("CaptionWriter", "ProperName", "Simple"),
    ("Category", "Text", "Simple"),
    ("City", "Text", "Simple"),
    ("ColorMode", "Integer", "Simple"),
    ("Country", "Text", "Simple"),
    ("Credit", "Text", "Simple"),
    ("DateCreated", "Date", "Simple"),
    ("Headline", "Text", "Simple"),
    ("History", "Text", "Simple"),
    ("ICCProfile", "Text", "Simple"),
    ("Instructions", "Text", "Simple"),
    ("Source", "Text", "Simple"),
    ("State", "Text", "Simple"),
    ("SupplementalCategories", "Text", "Simple"),
    ("TransmissionReference", "Text", "Simple"),
    ("Urgency", "Integer", "Simple"),
)


# Map upstream PropertyType field names to (getter_name, setter_name).
# Upstream's typed accessor names are camelCase; pypdfbox uses snake_case.
_ACCESSORS: dict[str, tuple[str, str]] = {
    "AncestorID": ("get_ancestor_id", "set_ancestor_id"),
    "AuthorsPosition": ("get_authors_position", "set_authors_position"),
    "CaptionWriter": ("get_caption_writer", "set_caption_writer"),
    "Category": ("get_category", "set_category"),
    "City": ("get_city", "set_city"),
    "ColorMode": ("get_color_mode", "set_color_mode"),
    "Country": ("get_country", "set_country"),
    "Credit": ("get_credit", "set_credit"),
    "DateCreated": ("get_date_created", "set_date_created"),
    "Headline": ("get_headline", "set_headline"),
    "History": ("get_history", "set_history"),
    "ICCProfile": ("get_icc_profile", "set_icc_profile"),
    "Instructions": ("get_instructions", "set_instructions"),
    "Source": ("get_source", "set_source"),
    "State": ("get_state", "set_state"),
    "SupplementalCategories": ("get_supplemental_categories", "set_supplemental_categories"),
    "TransmissionReference": ("get_transmission_reference", "set_transmission_reference"),
    "Urgency": ("get_urgency", "set_urgency"),
}


def _sample_value(type_token: str) -> object:
    """Pick a per-type sample value matching the upstream PropertyType column."""
    if type_token == "Integer":
        return 7
    # Text / URI / ProperName / Date all serialise to strings in cluster #1.
    return "sample-value"


def _expected_read_back(type_token: str, value: object) -> object:
    """How the value comes back through the typed getter (Integer vs string)."""
    return value


@pytest.fixture
def metadata() -> XMPMetadata:
    """Translates upstream ``@BeforeEach initMetadata`` setUp."""
    return XMPMetadata.create_xmp_metadata()


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_initialized_to_null(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Translated from upstream ``testInitializedToNull``: a freshly-built schema
    must report ``None`` for every typed accessor.
    """
    del card
    schema = PhotoshopSchema(metadata)
    getter_name, _ = _ACCESSORS[field_name]
    assert getattr(schema, getter_name)() is None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_setting_value(metadata: XMPMetadata, field_name: str, type_token: str, card: str) -> None:
    """
    Translated from upstream ``testSettingValue``: setting the property via the
    typed setter must round-trip through the typed getter and surface on the
    raw property store under the upstream local-name.
    """
    del card
    schema = PhotoshopSchema(metadata)
    getter_name, setter_name = _ACCESSORS[field_name]
    value = _sample_value(type_token)
    getattr(schema, setter_name)(value)
    assert getattr(schema, getter_name)() == _expected_read_back(type_token, value)
    # Stored under the upstream constant local-name.
    assert schema.get_property(field_name) is not None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_random_setting_value(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Translated from upstream ``testRandomSettingValue``: upstream draws a
    random value of the right type. Cluster #1 substitutes a deterministic
    second sample so the test stays reproducible while still exercising the
    "set, then read back the same value" contract.
    """
    del card
    schema = PhotoshopSchema(metadata)
    getter_name, setter_name = _ACCESSORS[field_name]
    if type_token == "Integer":
        value: object = 42
    else:
        value = "another-value"
    getattr(schema, setter_name)(value)
    assert getattr(schema, getter_name)() == _expected_read_back(type_token, value)


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_property_setter_simple(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Translated subset of upstream ``testPropertySetterSimple``: upstream verifies
    that ``setXxxProperty(field)`` (via ``addProperty(AbstractField)``) produces
    the same value as the simple ``setXxx(value)`` form. Cluster #1 only ships
    the simple-string form; we pin equivalence here by setting the value and
    confirming it appears on the raw property store, mirroring the read path
    upstream tests rely on.
    """
    del card
    schema = PhotoshopSchema(metadata)
    _, setter_name = _ACCESSORS[field_name]
    value = _sample_value(type_token)
    getattr(schema, setter_name)(value)
    raw = schema.get_property(field_name)
    assert raw is not None


# --- Wave 32: typed *_property accessors landed --------------------
#
# PhotoshopSchema has no array-cardinality simple-typed parameter rows in
# upstream's parameter set (DocumentAncestors is bag-of-text and exposes its
# own dedicated accessors, not the typed *_property pair). The upstream
# ``*InArray`` SchemaTester branches therefore short-circuit on Cardinality
# checks and never run for PhotoshopSchema; we mirror that with a one-line
# skip marker so the parity log stays one-to-one with upstream.

# Map upstream PropertyType field names to (typed_getter, typed_setter,
# wrapper class) for the ``*Property`` form covered by SchemaTester
# ``testPropertySetterSimple``.
_TYPED_ACCESSORS: dict[str, tuple[str, str, type]] = {
    "AncestorID": ("get_ancestor_id_property", "set_ancestor_id_property", URIType),
    "AuthorsPosition": (
        "get_authors_position_property",
        "set_authors_position_property",
        TextType,
    ),
    "CaptionWriter": (
        "get_caption_writer_property",
        "set_caption_writer_property",
        ProperNameType,
    ),
    "Category": ("get_category_property", "set_category_property", TextType),
    "City": ("get_city_property", "set_city_property", TextType),
    "ColorMode": ("get_color_mode_property", "set_color_mode_property", IntegerType),
    "Country": ("get_country_property", "set_country_property", TextType),
    "Credit": ("get_credit_property", "set_credit_property", TextType),
    "DateCreated": ("get_date_created_property", "set_date_created_property", DateType),
    "Headline": ("get_headline_property", "set_headline_property", TextType),
    "History": ("get_history_property", "set_history_property", TextType),
    "ICCProfile": ("get_icc_profile_property", "set_icc_profile_property", TextType),
    "Instructions": (
        "get_instructions_property",
        "set_instructions_property",
        TextType,
    ),
    "Source": ("get_source_property", "set_source_property", TextType),
    "State": ("get_state_property", "set_state_property", TextType),
    "SupplementalCategories": (
        "get_supplemental_categories_property",
        "set_supplemental_categories_property",
        TextType,
    ),
    "TransmissionReference": (
        "get_transmission_reference_property",
        "set_transmission_reference_property",
        TextType,
    ),
    "Urgency": ("get_urgency_property", "set_urgency_property", IntegerType),
}


def _wrapper_sample_value(type_token: str) -> object:
    """
    Pick a sample value the upstream wrapper constructor accepts. ``Date``
    requires an ISO 8601 string (or :class:`datetime`); the other simple-typed
    properties accept plain strings (or ints for ``Integer``).
    """
    if type_token == "Integer":
        return 7
    if type_token == "Date":
        return "2026-04-27T12:00:00Z"
    return "sample-value"


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_property_setter_simple_typed_round_trip(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Wave 32 typed-property variant of upstream ``testPropertySetterSimple``:
    instantiate a typed field via the wrapper constructor (the pypdfbox
    equivalent of ``typeMapping.instanciateSimpleProperty``), call
    ``setXxxProperty`` and verify the typed getter returns it back. Lives
    alongside the original-named ``test_property_setter_simple`` (cluster #1's
    string-form pin) so both shapes stay covered.
    """
    del card
    schema = PhotoshopSchema(metadata)
    getter_name, setter_name, wrapper_cls = _TYPED_ACCESSORS[field_name]
    value = _wrapper_sample_value(type_token)
    field = wrapper_cls(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        field_name,
        value,
    )
    getattr(schema, setter_name)(field)
    stored = schema.get_property(field_name)
    assert stored is field
    typed = getattr(schema, getter_name)()
    assert typed is field
    # Wrapper class must match upstream's expected implementing class.
    assert isinstance(typed, wrapper_cls)


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_random_property_setter_simple(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Translated from upstream ``testRandomPropertySetterSimple``: upstream
    runs the simple variant in a loop with random values; we substitute a
    deterministic alternate sample so the parity coverage stays reproducible
    and exercise the same typed-property setter path.
    """
    del card
    schema = PhotoshopSchema(metadata)
    getter_name, setter_name, wrapper_cls = _TYPED_ACCESSORS[field_name]
    if type_token == "Integer":
        value: object = 42
    elif type_token == "Date":
        value = "1999-12-31T23:59:59Z"
    else:
        value = "another-value"
    field = wrapper_cls(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        field_name,
        value,
    )
    getattr(schema, setter_name)(field)
    assert getattr(schema, getter_name)() is field


# ---------------------------------------------------------------------------
# *InArray rows — upstream ``SchemaTester.internalTest*InArray`` returns early
# for ``cardinality == Simple``. PhotoshopSchema's upstream parameter set is
# Simple-only, so the upstream tests are no-ops there; but the schema does
# carry two genuine array properties outside that parameter set —
# ``DocumentAncestors`` (Bag of Text) and ``TextLayers`` (Seq of LayerType).
# Cluster #1 covers those array properties here, mirroring the upstream
# ``*InArray`` contracts (multi-value append preserves order, the typed
# ``*Property`` accessor returns a populated ``ArrayProperty``) against the
# two array-shaped local-names the schema actually exposes.
# ---------------------------------------------------------------------------


def test_setting_value_in_array(metadata: XMPMetadata) -> None:
    """
    Translated from upstream ``SchemaTester.testSettingValueInArray``: append
    a string to the ``DocumentAncestors`` Bag and verify it is retrievable
    via the bag-list accessor. Upstream's parameterised driver short-circuits
    on Cardinality.Simple, so for PhotoshopSchema this exercises the only
    Bag-of-Text property the schema declares.
    """
    schema = PhotoshopSchema(metadata)
    schema.add_document_ancestors("uuid:first")
    schema.add_document_ancestors("uuid:second")
    assert schema.get_document_ancestors() == ["uuid:first", "uuid:second"]


def test_random_setting_value_in_array(metadata: XMPMetadata) -> None:
    """
    Translated from upstream ``testRandomSettingValueInArray``: upstream loops
    ``RAND_LOOP_COUNT`` (50) random values through the bag-add accessor. We
    substitute a deterministic three-value sample so the test stays
    reproducible while still exercising the "multi-add preserves ordering"
    contract.
    """
    schema = PhotoshopSchema(metadata)
    values = ["uuid:a", "uuid:b", "uuid:c"]
    for value in values:
        schema.add_document_ancestors(value)
    assert schema.get_document_ancestors() == values


def test_property_setter_in_array(metadata: XMPMetadata) -> None:
    """
    Translated from upstream ``SchemaTester.testPropertySetterInArray``:
    after appending a value via the bag-add accessor, the typed
    ``getXxxProperty`` round-trip yields a populated :class:`ArrayProperty`.
    For PhotoshopSchema this exercises the ``DocumentAncestors`` array.
    """
    schema = PhotoshopSchema(metadata)
    schema.add_document_ancestors("uuid:first")
    bag = schema.get_document_ancestors_property()
    assert isinstance(bag, ArrayProperty)
    children = bag.get_all_properties()
    assert len(children) == 1
    schema.add_document_ancestors("uuid:second")
    bag2 = schema.get_document_ancestors_property()
    assert isinstance(bag2, ArrayProperty)
    assert len(bag2.get_all_properties()) == 2


def test_random_property_setter_in_array(metadata: XMPMetadata) -> None:
    """
    Translated from upstream ``testRandomPropertySetterInArray``: same
    typed-array round-trip with a few sample values. Cluster #1 substitutes a
    deterministic two-layer sample for the ``TextLayers`` Seq (the other
    array-shaped property the schema declares) so both array slots are
    covered. Upstream uses ``LayerType`` here when ``Types.Layer`` enters
    the parameter set.
    """
    schema = PhotoshopSchema(metadata)
    schema.add_text_layers("Layer 1", "First layer text")
    schema.add_text_layers("Layer 2", "Second layer text")
    seq = schema.get_text_layers_property()
    assert isinstance(seq, ArrayProperty)
    assert seq.get_array_type() == Cardinality.Seq
    layers = seq.get_all_properties()
    assert len(layers) == 2
    assert all(isinstance(layer, LayerType) for layer in layers)
    assert layers[0].get_layer_name() == "Layer 1"
    assert layers[1].get_layer_text() == "Second layer text"


# Upstream's ``testRandomSetterSimple`` excludes ``Urgency`` / ``ColorMode``
# (Integer return type does not match the String parameter) and
# ``DateCreated`` (random Calendar input is not what the String-form setter
# expects). Narrow the parametrize input so those rows do not generate
# pytest skip noise — the exclusion is upstream-faithful, not a deviation
# placeholder.
_RANDOM_EXCLUDED = {"Urgency", "ColorMode", "DateCreated"}
_RANDOM_SIMPLE_PARAMETERS = tuple(
    p for p in _PARAMETERS if p[0] not in _RANDOM_EXCLUDED
)


@pytest.mark.parametrize(("field_name", "type_token", "card"), _RANDOM_SIMPLE_PARAMETERS)
def test_random_setter_simple(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Translated from upstream ``testRandomSetterSimple``: upstream loops
    ``RAND_LOOP_COUNT`` (50) random values through the string-form simple
    setter, asserting both the typed property store and the string getter
    round-trip the assigned value. Cluster #1 substitutes a small deterministic
    sequence so the test stays reproducible while still exercising the same
    contract.

    Upstream excludes ``Urgency`` / ``ColorMode`` / ``DateCreated`` — the
    narrowed parametrize input above mirrors that exclusion.
    """
    del card
    schema = PhotoshopSchema(metadata)
    getter_name, setter_name = _ACCESSORS[field_name]
    samples = (_sample_value(type_token), "another-value-2", "another-value-3")
    for value in samples:
        getattr(schema, setter_name)(value)
        assert getattr(schema, getter_name)() == _expected_read_back(type_token, value)
        # Stored under the upstream constant local-name.
        assert schema.get_property(field_name) is not None
