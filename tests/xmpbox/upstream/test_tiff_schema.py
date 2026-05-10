"""
Upstream-test stub for ``org.apache.xmpbox.schema.TIFFSchema``.

Apache PDFBox 3.0 does **not** ship a dedicated ``TIFFSchemaTest.java``
under ``xmpbox/src/test/java/org/apache/xmpbox/schema/`` — the upstream
test surface for the TIFF schema lives only inside the reflection-driven
``SchemaTester`` invocations on neighbouring schemas.

Rather than leave the upstream slot empty, this file mirrors the
upstream ``@PropertyType`` declarations from the ``TIFFSchema`` source
and exercises the ``testInitializedToNull`` / ``testSettingValue`` /
``testRandomSettingValue`` contracts that ``SchemaTester`` would have
applied if Apache had wired one up.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TiffSchema, XMPMetadata

# Upstream @PropertyType declarations for every TIFF schema property.
# Format: (FIELD_NAME, type_token, cardinality).
_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    # LangAlt — image description / copyright.
    ("ImageDescription", "LangAlt", "Simple"),
    ("Copyright", "LangAlt", "Simple"),
    # ProperName / AgentName / Date / Text — descriptive metadata.
    ("Artist", "ProperName", "Simple"),
    ("Make", "ProperName", "Simple"),
    ("Model", "ProperName", "Simple"),
    ("Software", "AgentName", "Simple"),
    ("DateTime", "Date", "Simple"),
    ("NativeDigest", "Text", "Simple"),
    # Integer — image-data structure tags.
    ("ImageWidth", "Integer", "Simple"),
    ("ImageLength", "Integer", "Simple"),
    ("Compression", "Integer", "Simple"),
    ("PhotometricInterpretation", "Integer", "Simple"),
    ("Orientation", "Integer", "Simple"),
    ("SamplesPerPixel", "Integer", "Simple"),
    ("PlanarConfiguration", "Integer", "Simple"),
    ("YCbCrPositioning", "Integer", "Simple"),
    ("ResolutionUnit", "Integer", "Simple"),
    # Rational — resolution.
    ("XResolution", "Rational", "Simple"),
    ("YResolution", "Rational", "Simple"),
    # Seq<Integer>.
    ("BitsPerSample", "Integer", "Seq"),
    ("YCbCrSubSampling", "Integer", "Seq"),
    ("TransferFunction", "Integer", "Seq"),
    # Seq<Rational>.
    ("WhitePoint", "Rational", "Seq"),
    ("PrimaryChromaticities", "Rational", "Seq"),
    ("YCbCrCoefficients", "Rational", "Seq"),
    ("ReferenceBlackWhite", "Rational", "Seq"),
)


# Map upstream constant name -> (getter, setter or adder).
# Seq properties expose ``add_*`` only; for those tests the "setter" slot
# points at the adder and the test paths branch on cardinality.
_ACCESSORS: dict[str, tuple[str, str]] = {
    "ImageDescription": ("get_image_description", "set_image_description"),
    "Copyright": ("get_copyright", "set_copyright"),
    "Artist": ("get_artist", "set_artist"),
    "Make": ("get_make", "set_make"),
    "Model": ("get_model", "set_model"),
    "Software": ("get_software", "set_software"),
    "DateTime": ("get_date_time", "set_date_time"),
    "NativeDigest": ("get_native_digest", "set_native_digest"),
    "ImageWidth": ("get_image_width", "set_image_width"),
    "ImageLength": ("get_image_length", "set_image_length"),
    "Compression": ("get_compression", "set_compression"),
    "PhotometricInterpretation": (
        "get_photometric_interpretation",
        "set_photometric_interpretation",
    ),
    "Orientation": ("get_orientation", "set_orientation"),
    "SamplesPerPixel": ("get_samples_per_pixel", "set_samples_per_pixel"),
    "PlanarConfiguration": ("get_planar_configuration", "set_planar_configuration"),
    "YCbCrPositioning": ("get_y_cb_cr_positioning", "set_y_cb_cr_positioning"),
    "ResolutionUnit": ("get_resolution_unit", "set_resolution_unit"),
    "XResolution": ("get_x_resolution", "set_x_resolution"),
    "YResolution": ("get_y_resolution", "set_y_resolution"),
    "BitsPerSample": ("get_bits_per_sample", "add_bits_per_sample"),
    "YCbCrSubSampling": ("get_y_cb_cr_sub_sampling", "add_y_cb_cr_sub_sampling"),
    "TransferFunction": ("get_transfer_function", "add_transfer_function"),
    "WhitePoint": ("get_white_point", "add_white_point"),
    "PrimaryChromaticities": (
        "get_primary_chromaticities",
        "add_primary_chromaticities",
    ),
    "YCbCrCoefficients": ("get_y_cb_cr_coefficients", "add_y_cb_cr_coefficients"),
    "ReferenceBlackWhite": (
        "get_reference_black_white",
        "add_reference_black_white",
    ),
}


def _sample_value(type_token: str) -> object:
    """Pick a per-type sample value matching the upstream PropertyType column."""
    if type_token == "Integer":
        return 7
    if type_token == "Rational":
        # Upstream RationalType serialises to "<num>/<den>" text.
        return "1/2"
    # Text / ProperName / AgentName / Date / LangAlt all serialise to strings.
    return "sample-value"


@pytest.fixture
def metadata() -> XMPMetadata:
    """Translates upstream ``@BeforeEach initMetadata`` setUp."""
    return XMPMetadata.create_xmp_metadata()


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_initialized_to_null(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Mirrors upstream ``SchemaTester.testInitializedToNull``: a freshly-built
    schema reports ``None`` for every typed accessor.
    """
    del type_token, card
    schema = TiffSchema(metadata)
    getter_name, _ = _ACCESSORS[field_name]
    assert getattr(schema, getter_name)() is None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_setting_value(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Mirrors upstream ``SchemaTester.testSettingValue``: setting the property
    via the typed setter (or adder for Seq) must round-trip through the typed
    getter and surface on the raw property store under the upstream local-name.
    """
    schema = TiffSchema(metadata)
    getter_name, setter_or_adder_name = _ACCESSORS[field_name]
    value = _sample_value(type_token)
    getattr(schema, setter_or_adder_name)(value)
    if card == "Seq":
        # Adder appends; getter returns a list.
        result = getattr(schema, getter_name)()
        assert isinstance(result, list)
        assert result == [str(value)]
    else:
        assert getattr(schema, getter_name)() == value
    # Stored under the upstream constant local-name.
    assert schema.get_property(field_name) is not None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_random_setting_value(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Mirrors upstream ``SchemaTester.testRandomSettingValue``: upstream draws a
    random value of the right type. We substitute a deterministic second
    sample so the test stays reproducible while still exercising the "set,
    then read back the same value" contract.
    """
    schema = TiffSchema(metadata)
    getter_name, setter_or_adder_name = _ACCESSORS[field_name]
    if type_token == "Integer":
        value: object = 42
    elif type_token == "Rational":
        value = "300/1"
    else:
        value = "another-value"
    getattr(schema, setter_or_adder_name)(value)
    if card == "Seq":
        result = getattr(schema, getter_name)()
        assert isinstance(result, list)
        assert result == [str(value)]
    else:
        assert getattr(schema, getter_name)() == value


def test_namespace_uri_matches_upstream() -> None:
    """Mirror of upstream ``TIFFSchema.NAMESPACE`` constant."""
    assert TiffSchema.NAMESPACE == "http://ns.adobe.com/tiff/1.0/"


def test_preferred_prefix_matches_upstream() -> None:
    """Mirror of upstream ``TIFFSchema.PREFERRED_PREFIX`` constant."""
    assert TiffSchema.PREFERRED_PREFIX == "tiff"
