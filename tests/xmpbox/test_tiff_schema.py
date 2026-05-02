from __future__ import annotations

from pypdfbox.xmpbox import (
    AgentNameType,
    DateType,
    DomXmpParser,
    IntegerType,
    LangAlt,
    ProperNameType,
    RationalType,
    TextType,
    TiffSchema,
    XMPMetadata,
)


def _tiff() -> TiffSchema:
    return TiffSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _tiff()
    assert TiffSchema.NAMESPACE == "http://ns.adobe.com/tiff/1.0/"
    assert TiffSchema.PREFERRED_PREFIX == "tiff"
    assert schema.get_namespace() == "http://ns.adobe.com/tiff/1.0/"
    assert schema.get_prefix() == "tiff"


def test_local_name_constants_match_upstream() -> None:
    # Verify each upstream constant is mirrored verbatim.
    assert TiffSchema.IMAGE_DESCRIPTION == "ImageDescription"
    assert TiffSchema.COPYRIGHT == "Copyright"
    assert TiffSchema.ARTIST == "Artist"
    assert TiffSchema.IMAGE_WIDTH == "ImageWidth"
    assert TiffSchema.IMAGE_LENGTH == "ImageLength"
    assert TiffSchema.BITS_PER_SAMPLE == "BitsPerSample"
    assert TiffSchema.COMPRESSION == "Compression"
    assert TiffSchema.PHOTOMETRIC_INTERPRETATION == "PhotometricInterpretation"
    assert TiffSchema.ORIENTATION == "Orientation"
    assert TiffSchema.SAMPLES_PER_PIXEL == "SamplesPerPixel"
    assert TiffSchema.PLANAR_CONFIGURATION == "PlanarConfiguration"
    assert TiffSchema.YCB_CR_SUB_SAMPLING == "YCbCrSubSampling"
    assert TiffSchema.YCB_CR_POSITIONING == "YCbCrPositioning"
    assert TiffSchema.XRESOLUTION == "XResolution"
    assert TiffSchema.YRESOLUTION == "YResolution"
    assert TiffSchema.RESOLUTION_UNIT == "ResolutionUnit"
    assert TiffSchema.TRANSFER_FUNCTION == "TransferFunction"
    assert TiffSchema.WHITE_POINT == "WhitePoint"
    assert TiffSchema.PRIMARY_CHROMATICITIES == "PrimaryChromaticities"
    assert TiffSchema.YCB_CR_COEFFICIENTS == "YCbCrCoefficients"
    assert TiffSchema.REFERENCE_BLACK_WHITE == "ReferenceBlackWhite"
    assert TiffSchema.DATE_TIME == "DateTime"
    assert TiffSchema.SOFTWARE == "Software"
    assert TiffSchema.MAKE == "Make"
    assert TiffSchema.MODEL == "Model"
    assert TiffSchema.NATIVE_DIGEST == "NativeDigest"


def test_default_accessors_return_none() -> None:
    schema = _tiff()
    assert schema.get_image_description() is None
    assert schema.get_copyright() is None
    assert schema.get_artist() is None
    assert schema.get_make() is None
    assert schema.get_model() is None
    assert schema.get_software() is None
    assert schema.get_date_time() is None
    assert schema.get_image_width() is None
    assert schema.get_image_length() is None
    assert schema.get_compression() is None
    assert schema.get_photometric_interpretation() is None
    assert schema.get_orientation() is None
    assert schema.get_samples_per_pixel() is None
    assert schema.get_planar_configuration() is None
    assert schema.get_y_cb_cr_positioning() is None
    assert schema.get_resolution_unit() is None
    assert schema.get_bits_per_sample() is None
    assert schema.get_y_cb_cr_sub_sampling() is None
    assert schema.get_transfer_function() is None
    assert schema.get_x_resolution() is None
    assert schema.get_y_resolution() is None
    assert schema.get_white_point() is None
    assert schema.get_primary_chromaticities() is None
    assert schema.get_y_cb_cr_coefficients() is None
    assert schema.get_reference_black_white() is None


def test_proper_name_text_round_trip() -> None:
    schema = _tiff()
    schema.set_artist("Ansel Adams")
    schema.set_make("Canon")
    schema.set_model("EOS R5")
    schema.set_software("Adobe Camera Raw 16.0")
    schema.set_date_time("2026-04-27T09:30:00Z")

    assert schema.get_artist() == "Ansel Adams"
    assert schema.get_make() == "Canon"
    assert schema.get_model() == "EOS R5"
    assert schema.get_software() == "Adobe Camera Raw 16.0"
    assert schema.get_date_time() == "2026-04-27T09:30:00Z"

    # set_*(None) clears the property.
    schema.set_artist(None)
    schema.set_make(None)
    schema.set_model(None)
    schema.set_software(None)
    schema.set_date_time(None)

    assert schema.get_artist() is None
    assert schema.get_make() is None
    assert schema.get_model() is None
    assert schema.get_software() is None
    assert schema.get_date_time() is None


def test_image_description_lang_alt_round_trip() -> None:
    schema = _tiff()
    schema.set_image_description("Sunset")
    schema.add_image_description("fr", "Coucher de soleil")
    assert schema.get_image_description() == "Sunset"
    assert schema.get_image_description("fr") == "Coucher de soleil"
    languages = schema.get_image_description_languages()
    assert languages is not None
    assert "x-default" in languages
    assert "fr" in languages


def test_copyright_lang_alt_round_trip() -> None:
    schema = _tiff()
    schema.set_copyright("(c) 2026 Acme")
    schema.add_copyright("ja", "(c) 2026 Acme (ja)")
    assert schema.get_copyright() == "(c) 2026 Acme"
    assert schema.get_copyright("ja") == "(c) 2026 Acme (ja)"
    languages = schema.get_copyright_languages()
    assert languages is not None
    assert "x-default" in languages
    assert "ja" in languages


def test_simple_integer_round_trip() -> None:
    schema = _tiff()
    schema.set_image_width(4000)
    schema.set_image_length(3000)
    schema.set_compression(1)
    schema.set_photometric_interpretation(2)
    schema.set_orientation(1)
    schema.set_samples_per_pixel(3)
    schema.set_planar_configuration(1)
    schema.set_y_cb_cr_positioning(1)
    schema.set_resolution_unit(2)

    assert schema.get_image_width() == 4000
    assert schema.get_image_length() == 3000
    assert schema.get_compression() == 1
    assert schema.get_photometric_interpretation() == 2
    assert schema.get_orientation() == 1
    assert schema.get_samples_per_pixel() == 3
    assert schema.get_planar_configuration() == 1
    assert schema.get_y_cb_cr_positioning() == 1
    assert schema.get_resolution_unit() == 2

    # IntegerType serialises as the decimal string in upstream.
    assert schema.get_unqualified_text_property_value(TiffSchema.IMAGE_WIDTH) == "4000"

    # set_*(None) clears.
    schema.set_image_width(None)
    schema.set_orientation(None)
    assert schema.get_image_width() is None
    assert schema.get_orientation() is None


def test_integer_accepts_string_form_for_parser_round_trip() -> None:
    schema = _tiff()
    # Parser stores attribute-form values as raw strings.
    schema.set_text_property_value(TiffSchema.ORIENTATION, "8")
    assert schema.get_orientation() == 8
    schema.set_text_property_value(TiffSchema.ORIENTATION, "junk")
    assert schema.get_orientation() is None


def test_integer_string_setter_overload() -> None:
    schema = _tiff()
    schema.set_image_width("4000")
    assert schema.get_image_width() == 4000


def test_bits_per_sample_seq_round_trip() -> None:
    schema = _tiff()
    schema.add_bits_per_sample(8)
    schema.add_bits_per_sample(8)
    schema.add_bits_per_sample(8)
    assert schema.get_bits_per_sample() == ["8", "8", "8"]


def test_y_cb_cr_sub_sampling_seq_round_trip() -> None:
    schema = _tiff()
    schema.add_y_cb_cr_sub_sampling(2)
    schema.add_y_cb_cr_sub_sampling(1)
    assert schema.get_y_cb_cr_sub_sampling() == ["2", "1"]


def test_transfer_function_seq_round_trip() -> None:
    schema = _tiff()
    schema.add_transfer_function("0")
    schema.add_transfer_function(255)
    assert schema.get_transfer_function() == ["0", "255"]


def test_rational_resolution_round_trip() -> None:
    schema = _tiff()
    schema.set_x_resolution("300/1")
    schema.set_y_resolution("300/1")
    assert schema.get_x_resolution() == "300/1"
    assert schema.get_y_resolution() == "300/1"
    schema.set_x_resolution(None)
    assert schema.get_x_resolution() is None


def test_seq_of_rational_white_point_and_chromaticities() -> None:
    schema = _tiff()
    schema.add_white_point("3127/10000")
    schema.add_white_point("3290/10000")
    assert schema.get_white_point() == ["3127/10000", "3290/10000"]

    schema.add_primary_chromaticities("64/100")
    schema.add_primary_chromaticities("33/100")
    assert schema.get_primary_chromaticities() == ["64/100", "33/100"]

    schema.add_y_cb_cr_coefficients("299/1000")
    schema.add_y_cb_cr_coefficients("587/1000")
    assert schema.get_y_cb_cr_coefficients() == ["299/1000", "587/1000"]

    schema.add_reference_black_white("0/1")
    schema.add_reference_black_white("255/1")
    assert schema.get_reference_black_white() == ["0/1", "255/1"]


def test_xmp_metadata_add_tiff_schema_idempotent() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_tiff_schema() is None
    schema = metadata.add_tiff_schema()
    assert isinstance(schema, TiffSchema)
    # Idempotent — repeat add returns the same instance.
    assert metadata.add_tiff_schema() is schema
    assert metadata.get_tiff_schema() is schema


def test_create_and_add_tiff_schema_alias() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_tiff_schema()
    assert isinstance(schema, TiffSchema)
    # Alias is also idempotent through add_tiff_schema.
    assert metadata.create_and_add_tiff_schema() is schema


def test_dom_parser_dispatches_attribute_form_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:tiff='http://ns.adobe.com/tiff/1.0/'"
        b" tiff:Make='Canon'"
        b" tiff:Model='EOS R5'"
        b" tiff:ImageWidth='4000'"
        b" tiff:Orientation='1'"
        b" tiff:XResolution='300/1'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(TiffSchema)
    assert isinstance(schema, TiffSchema)
    assert schema.get_make() == "Canon"
    assert schema.get_model() == "EOS R5"
    assert schema.get_image_width() == 4000
    assert schema.get_orientation() == 1
    assert schema.get_x_resolution() == "300/1"


def test_dom_parser_dispatches_bits_per_sample_seq_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:tiff='http://ns.adobe.com/tiff/1.0/'>"
        b"<tiff:BitsPerSample>"
        b"<rdf:Seq>"
        b"<rdf:li>8</rdf:li>"
        b"<rdf:li>8</rdf:li>"
        b"<rdf:li>8</rdf:li>"
        b"</rdf:Seq>"
        b"</tiff:BitsPerSample>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(TiffSchema)
    assert isinstance(schema, TiffSchema)
    assert schema.get_bits_per_sample() == ["8", "8", "8"]


def test_dom_parser_dispatches_image_description_lang_alt_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:tiff='http://ns.adobe.com/tiff/1.0/'"
        b" xmlns:xml='http://www.w3.org/XML/1998/namespace'>"
        b"<tiff:ImageDescription>"
        b"<rdf:Alt>"
        b"<rdf:li xml:lang='x-default'>Sunset</rdf:li>"
        b"<rdf:li xml:lang='fr'>Coucher de soleil</rdf:li>"
        b"</rdf:Alt>"
        b"</tiff:ImageDescription>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(TiffSchema)
    assert isinstance(schema, TiffSchema)
    assert schema.get_image_description() == "Sunset"
    assert schema.get_image_description("fr") == "Coucher de soleil"


def test_dom_parser_get_namespace_table_includes_tiff() -> None:
    table = DomXmpParser().get_namespace_table()
    assert table.get("tiff") == "http://ns.adobe.com/tiff/1.0/"


# --- Wave 39 round-out: typed-property accessors -----------------------


def test_native_digest_round_trip() -> None:
    schema = _tiff()
    assert schema.get_native_digest() is None
    schema.set_native_digest("AABBCCDD11223344")
    assert schema.get_native_digest() == "AABBCCDD11223344"
    schema.set_native_digest(None)
    assert schema.get_native_digest() is None


def test_native_digest_typed_property() -> None:
    schema = _tiff()
    metadata = schema._metadata
    prop = TextType(
        metadata,
        TiffSchema.NAMESPACE,
        TiffSchema.PREFERRED_PREFIX,
        TiffSchema.NATIVE_DIGEST,
        "DEADBEEF",
    )
    schema.set_native_digest_property(prop)
    fetched = schema.get_native_digest_property()
    assert isinstance(fetched, TextType)
    assert fetched.get_string_value() == "DEADBEEF"
    # Round-trip through string accessor.
    assert schema.get_native_digest() == "DEADBEEF"


def test_make_model_artist_typed_property() -> None:
    schema = _tiff()
    metadata = schema._metadata
    schema.set_make_property(
        ProperNameType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.MAKE, "Canon"
        )
    )
    schema.set_model_property(
        ProperNameType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.MODEL, "EOS R5"
        )
    )
    schema.set_artist_property(
        ProperNameType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.ARTIST, "Ansel"
        )
    )
    assert isinstance(schema.get_make_property(), ProperNameType)
    assert schema.get_make_property().get_string_value() == "Canon"
    assert isinstance(schema.get_model_property(), ProperNameType)
    assert schema.get_model_property().get_string_value() == "EOS R5"
    assert isinstance(schema.get_artist_property(), ProperNameType)
    assert schema.get_artist_property().get_string_value() == "Ansel"


def test_software_typed_property() -> None:
    schema = _tiff()
    metadata = schema._metadata
    schema.set_software_property(
        AgentNameType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.SOFTWARE, "ACR 16"
        )
    )
    fetched = schema.get_software_property()
    assert isinstance(fetched, AgentNameType)
    assert fetched.get_string_value() == "ACR 16"
    # String getter sees the same value.
    assert schema.get_software() == "ACR 16"


def test_date_time_typed_property() -> None:
    schema = _tiff()
    metadata = schema._metadata
    schema.set_date_time_property(
        DateType(
            metadata,
            TiffSchema.NAMESPACE,
            "tiff",
            TiffSchema.DATE_TIME,
            "2026-04-27T12:34:56Z",
        )
    )
    fetched = schema.get_date_time_property()
    assert isinstance(fetched, DateType)
    # ``DateType`` normalises ``Z`` into the explicit ``+00:00`` offset; the
    # round-trip preserves the same timezone moment regardless of spelling.
    assert fetched.get_string_value().startswith("2026-04-27T12:34:56")
    assert schema.get_date_time().startswith("2026-04-27T12:34:56")


def test_integer_typed_property_round_trip() -> None:
    schema = _tiff()
    metadata = schema._metadata
    schema.set_image_width_property(
        IntegerType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.IMAGE_WIDTH, 4000
        )
    )
    schema.set_orientation_property(
        IntegerType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.ORIENTATION, 1
        )
    )
    assert isinstance(schema.get_image_width_property(), IntegerType)
    assert schema.get_image_width_property().get_value() == 4000
    assert schema.get_image_width() == 4000
    assert schema.get_orientation_property().get_value() == 1


def test_integer_typed_property_promotes_string_form() -> None:
    """If a parser stored a raw string, the typed getter still returns IntegerType."""
    schema = _tiff()
    schema.set_text_property_value(TiffSchema.IMAGE_LENGTH, "3000")
    fetched = schema.get_image_length_property()
    assert isinstance(fetched, IntegerType)
    assert fetched.get_value() == 3000


def test_rational_typed_property_round_trip() -> None:
    schema = _tiff()
    metadata = schema._metadata
    schema.set_x_resolution_property(
        RationalType(
            metadata, TiffSchema.NAMESPACE, "tiff", TiffSchema.XRESOLUTION, "300/1"
        )
    )
    fetched = schema.get_x_resolution_property()
    assert isinstance(fetched, RationalType)
    assert fetched.get_string_value() == "300/1"
    # String form sees the same value.
    assert schema.get_x_resolution() == "300/1"
    # Fraction helper.
    fr = fetched.as_fraction()
    assert fr is not None
    assert fr.numerator == 300
    assert fr.denominator == 1


def test_typed_setter_clears_with_none() -> None:
    schema = _tiff()
    schema.set_image_width(4000)
    schema.set_image_width_property(None)
    assert schema.get_image_width() is None
    assert schema.get_image_width_property() is None


def test_all_typed_property_getters_return_none_when_empty() -> None:
    schema = _tiff()
    assert schema.get_native_digest_property() is None
    assert schema.get_make_property() is None
    assert schema.get_model_property() is None
    assert schema.get_artist_property() is None
    assert schema.get_software_property() is None
    assert schema.get_date_time_property() is None
    assert schema.get_image_width_property() is None
    assert schema.get_image_length_property() is None
    assert schema.get_compression_property() is None
    assert schema.get_photometric_interpretation_property() is None
    assert schema.get_orientation_property() is None
    assert schema.get_samples_per_pixel_property() is None
    assert schema.get_planar_configuration_property() is None
    assert schema.get_y_cb_cr_positioning_property() is None
    assert schema.get_resolution_unit_property() is None
    assert schema.get_x_resolution_property() is None
    assert schema.get_y_resolution_property() is None


def test_image_description_property_returns_lang_alt() -> None:
    """Wave round-out: parity with upstream ``getImageDescriptionProperty``."""
    schema = _tiff()
    assert schema.get_image_description_property() is None
    schema.set_image_description("Sunset")
    schema.add_image_description("fr", "Coucher de soleil")
    la = schema.get_image_description_property()
    assert isinstance(la, LangAlt)
    assert la.get_language_value("x-default") == "Sunset"
    assert la.get_language_value("fr") == "Coucher de soleil"
    # x-default must be the first child (matches upstream reorganizeAltOrder).
    children = la.get_all_properties()
    assert len(children) == 2
    first_attr = children[0].get_attribute("xml:lang")
    assert first_attr is not None
    assert first_attr.get_value() == "x-default"


def test_copyright_property_returns_lang_alt() -> None:
    """Wave round-out: parity with upstream ``getCopyrightProperty``."""
    schema = _tiff()
    assert schema.get_copyright_property() is None
    schema.set_copyright("(c) 2026 Example")
    schema.add_copyright("de", "(c) 2026 Beispiel")
    la = schema.get_copyright_property()
    assert isinstance(la, LangAlt)
    assert la.get_language_value("x-default") == "(c) 2026 Example"
    assert la.get_language_value("de") == "(c) 2026 Beispiel"


def test_lang_alt_property_accessors_none_when_empty() -> None:
    schema = _tiff()
    assert schema.get_image_description_property() is None
    assert schema.get_copyright_property() is None


def test_remove_image_description_drops_language_slot() -> None:
    """Wave round-out: per-language removal mirror for ``ImageDescription``."""
    schema = _tiff()
    schema.set_image_description("Sunset")
    schema.add_image_description("fr", "Coucher de soleil")
    schema.remove_image_description("fr")
    assert schema.get_image_description("fr") is None
    assert schema.get_image_description() == "Sunset"
    # Removing the default slot leaves an empty per-language dict.
    schema.remove_image_description()
    assert schema.get_image_description() is None
    # No-op when called on an absent / fresh schema.
    fresh = _tiff()
    fresh.remove_image_description("en")  # must not raise


def test_remove_copyright_drops_language_slot() -> None:
    """Wave round-out: per-language removal mirror for ``Copyright``."""
    schema = _tiff()
    schema.set_copyright("(c) 2026 Acme")
    schema.add_copyright("ja", "(c) 2026 Acme (ja)")
    schema.remove_copyright("ja")
    assert schema.get_copyright("ja") is None
    assert schema.get_copyright() == "(c) 2026 Acme"
    schema.remove_copyright()
    assert schema.get_copyright() is None
    # No-op on a fresh schema.
    _tiff().remove_copyright()
