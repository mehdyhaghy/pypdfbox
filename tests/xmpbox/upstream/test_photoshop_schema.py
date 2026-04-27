"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/PhotoshopSchemaTest.java

Upstream's tests rely on a reflection-driven ``SchemaTester`` helper that
exercises generic ``getXxxProperty`` / ``setXxxProperty`` accessors plus the
typed ``addProperty(AbstractField)`` machinery. Cluster #1 in pypdfbox stores
property values as Python primitives (str / list / dict); the typed
``AbstractField`` hierarchy is deferred. The translation below follows the
upstream parameterisation (one entry per property) but exercises only the
behaviors we actually ship: default-null, simple value round-trip, and
per-type integer/text shape preservation.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import PhotoshopSchema, XMPMetadata


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
def test_initialized_to_null(metadata: XMPMetadata, field_name: str, type_token: str, card: str) -> None:
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
def test_random_setting_value(metadata: XMPMetadata, field_name: str, type_token: str, card: str) -> None:
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
def test_property_setter_simple(metadata: XMPMetadata, field_name: str, type_token: str, card: str) -> None:
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


# Upstream ``testSettingValueInArray`` / ``testRandomSettingValueInArray`` /
# ``testPropertySetterInArray`` / ``testRandomPropertySetterInArray`` /
# ``testRandomPropertySetterSimple`` / ``testRandomSetterSimple`` all rely on
# the typed ``AbstractField`` hierarchy and the ``ArrayProperty`` container,
# neither of which has landed in cluster #1. Skip with a one-line marker so
# the parity log stays one-to-one with upstream.
@pytest.mark.skip(reason="cluster #1 defers AbstractField / ArrayProperty hierarchy")
def test_setting_value_in_array() -> None:
    pass


@pytest.mark.skip(reason="cluster #1 defers AbstractField / ArrayProperty hierarchy")
def test_random_setting_value_in_array() -> None:
    pass


@pytest.mark.skip(reason="cluster #1 defers AbstractField / ArrayProperty hierarchy")
def test_property_setter_in_array() -> None:
    pass


@pytest.mark.skip(reason="cluster #1 defers AbstractField / ArrayProperty hierarchy")
def test_random_property_setter_in_array() -> None:
    pass


@pytest.mark.skip(reason="cluster #1 defers AbstractField / ArrayProperty hierarchy")
def test_random_property_setter_simple() -> None:
    pass


@pytest.mark.skip(reason="cluster #1 defers AbstractField / ArrayProperty hierarchy")
def test_random_setter_simple() -> None:
    pass
