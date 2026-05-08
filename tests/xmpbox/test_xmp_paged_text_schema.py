from __future__ import annotations

from pypdfbox.xmpbox import (
    ColorantType,
    DimensionsType,
    DomXmpParser,
    FontType,
    IntegerType,
    XMPageTextSchema,
    XMPMetadata,
)


def _pt() -> XMPageTextSchema:
    return XMPageTextSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _pt()
    assert XMPageTextSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/t/pg/"
    assert XMPageTextSchema.PREFERRED_PREFIX == "xmpTPg"
    assert schema.get_namespace() == "http://ns.adobe.com/xap/1.0/t/pg/"
    assert schema.get_prefix() == "xmpTPg"


def test_local_name_constants_match_upstream() -> None:
    assert XMPageTextSchema.MAX_PAGE_SIZE == "MaxPageSize"
    assert XMPageTextSchema.N_PAGES == "NPages"
    assert XMPageTextSchema.HAS_VISIBLE_TRANSPARENCY == "HasVisibleTransparency"
    assert XMPageTextSchema.HAS_VISIBLE_OVERPRINT == "HasVisibleOverprint"
    assert XMPageTextSchema.PLATENAMES == "PlateNames"
    assert XMPageTextSchema.COLORANTS == "Colorants"
    assert XMPageTextSchema.FONTS == "Fonts"


def test_default_accessors_return_none() -> None:
    schema = _pt()
    assert schema.get_n_pages() is None
    assert schema.get_n_pages_property() is None
    assert schema.get_max_page_size() is None
    assert schema.get_max_page_size_property() is None
    assert schema.get_plate_names() is None
    assert schema.get_colorants() is None
    assert schema.get_colorant_properties() is None
    assert schema.get_fonts() is None
    assert schema.get_font_properties() is None
    assert schema.get_has_visible_transparency() is None
    assert schema.get_has_visible_overprint() is None


def test_constructor_pre_registers_struct_namespaces() -> None:
    schema = _pt()
    namespaces = schema.get_namespaces()
    # Schema's own preferred prefix.
    assert namespaces.get(XMPageTextSchema.PREFERRED_PREFIX) == XMPageTextSchema.NAMESPACE
    # Pre-registered structured-type sub-namespaces.
    assert namespaces.get(DimensionsType.PREFERRED_PREFIX) == DimensionsType.NAMESPACE
    assert namespaces.get(FontType.PREFERRED_PREFIX) == FontType.NAMESPACE
    assert namespaces.get(ColorantType.PREFERRED_PREFIX) == ColorantType.NAMESPACE


def test_n_pages_round_trip() -> None:
    schema = _pt()
    schema.set_n_pages(42)
    assert schema.get_n_pages() == 42
    # Setting None clears.
    schema.set_n_pages(None)
    assert schema.get_n_pages() is None


def test_n_pages_returns_none_when_value_is_not_integer() -> None:
    schema = _pt()
    # Simulate a parser-stored bogus value.
    schema.set_property(XMPageTextSchema.N_PAGES, "not-a-number")
    assert schema.get_n_pages() is None


def test_n_pages_property_materializes_from_primitive_storage() -> None:
    schema = _pt()
    schema.set_n_pages(12)

    prop = schema.get_n_pages_property()

    assert isinstance(prop, IntegerType)
    assert prop.get_property_name() == XMPageTextSchema.N_PAGES
    assert prop.get_value() == 12


def test_n_pages_typed_property_visible_to_primitive_getter_and_clearable() -> None:
    schema = _pt()
    metadata = schema.get_metadata()
    prop = IntegerType(
        metadata,
        XMPageTextSchema.NAMESPACE,
        XMPageTextSchema.PREFERRED_PREFIX,
        XMPageTextSchema.N_PAGES,
        9,
    )

    schema.set_n_pages_property(prop)

    assert schema.get_n_pages_property() is prop
    assert schema.get_n_pages() == 9

    schema.set_n_pages_property(None)
    assert schema.get_n_pages() is None
    assert schema.get_n_pages_property() is None


def test_max_page_size_round_trip_dict_payload() -> None:
    schema = _pt()
    payload = {"w": "612", "h": "792", "unit": "Pt"}
    schema.set_max_page_size(payload)
    assert schema.get_max_page_size() == payload
    schema.set_max_page_size(None)
    assert schema.get_max_page_size() is None


def test_plate_names_seq_add_and_remove() -> None:
    schema = _pt()
    schema.add_plate_name("Cyan")
    schema.add_plate_name("Magenta")
    schema.add_plate_name("Yellow")
    schema.add_plate_name("Black")
    assert schema.get_plate_names() == ["Cyan", "Magenta", "Yellow", "Black"]
    schema.remove_plate_name("Magenta")
    assert schema.get_plate_names() == ["Cyan", "Yellow", "Black"]


def test_colorants_seq_add_and_get() -> None:
    schema = _pt()
    schema.add_colorant("PANTONE 185 C")
    schema.add_colorant({"swatchName": "PANTONE 116 C", "type": "SPOT"})
    colorants = schema.get_colorants()
    assert colorants is not None
    assert len(colorants) == 2
    assert colorants[0] == "PANTONE 185 C"
    assert colorants[1] == {"swatchName": "PANTONE 116 C", "type": "SPOT"}


def test_fonts_bag_add_and_get() -> None:
    schema = _pt()
    schema.add_font("Helvetica")
    schema.add_font("TimesNewRoman")
    fonts = schema.get_fonts()
    assert fonts is not None
    assert set(fonts) == {"Helvetica", "TimesNewRoman"}


def test_xmp_metadata_create_and_add_returns_typed_wrapper() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_page_text_schema() is None

    schema = metadata.create_and_add_page_text_schema()
    assert isinstance(schema, XMPageTextSchema)
    # rdf:about defaults to "" (empty string) per upstream semantics.
    assert schema.get_about() == ""
    # The lookup accessor finds the same instance.
    assert metadata.get_page_text_schema() is schema


def test_round_trip_through_xmp_packet_attribute_form() -> None:
    # Exercise the parser path: xmpTPg:NPages as an attribute on rdf:Description.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpTPg='http://ns.adobe.com/xap/1.0/t/pg/'"
        b" xmpTPg:NPages='12'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPageTextSchema)
    assert isinstance(schema, XMPageTextSchema)
    assert schema.get_n_pages() == 12
    # Convenience accessor finds the same schema instance.
    assert metadata.get_page_text_schema() is schema


def test_round_trip_through_xmp_packet_seq_and_bag() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpTPg='http://ns.adobe.com/xap/1.0/t/pg/'>"
        b"<xmpTPg:NPages>3</xmpTPg:NPages>"
        b"<xmpTPg:PlateNames>"
        b"<rdf:Seq>"
        b"<rdf:li>Cyan</rdf:li>"
        b"<rdf:li>Magenta</rdf:li>"
        b"<rdf:li>Yellow</rdf:li>"
        b"</rdf:Seq>"
        b"</xmpTPg:PlateNames>"
        b"<xmpTPg:Fonts>"
        b"<rdf:Bag>"
        b"<rdf:li>Helvetica</rdf:li>"
        b"<rdf:li>Arial</rdf:li>"
        b"</rdf:Bag>"
        b"</xmpTPg:Fonts>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPageTextSchema)
    assert isinstance(schema, XMPageTextSchema)
    assert schema.get_n_pages() == 3
    assert schema.get_plate_names() == ["Cyan", "Magenta", "Yellow"]
    fonts = schema.get_fonts()
    assert fonts is not None
    assert set(fonts) == {"Helvetica", "Arial"}


def test_subclass_constructor_accepts_custom_prefix() -> None:
    # Upstream supports a (metadata, prefix) constructor variant; mirror that.
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPageTextSchema(metadata, "customTPg")
    assert schema.get_prefix() == "customTPg"
    assert schema.get_namespace() == XMPageTextSchema.NAMESPACE


# --- HasVisibleTransparency / HasVisibleOverprint -----------------------


def test_has_visible_transparency_round_trip() -> None:
    schema = _pt()
    schema.set_has_visible_transparency(True)
    assert schema.get_has_visible_transparency() is True
    # Stored on the wire as capitalised "True" per XMP Boolean spec.
    assert schema.get_unqualified_text_property_value(
        XMPageTextSchema.HAS_VISIBLE_TRANSPARENCY
    ) == "True"
    schema.set_has_visible_transparency(False)
    assert schema.get_has_visible_transparency() is False
    assert schema.get_unqualified_text_property_value(
        XMPageTextSchema.HAS_VISIBLE_TRANSPARENCY
    ) == "False"
    schema.set_has_visible_transparency(None)
    assert schema.get_has_visible_transparency() is None


def test_has_visible_overprint_round_trip() -> None:
    schema = _pt()
    schema.set_has_visible_overprint(True)
    assert schema.get_has_visible_overprint() is True
    schema.set_has_visible_overprint(False)
    assert schema.get_has_visible_overprint() is False
    schema.set_has_visible_overprint(None)
    assert schema.get_has_visible_overprint() is None


def test_has_visible_boolean_accepts_lowercase_storage() -> None:
    schema = _pt()
    # Defensive coercion: parser-stored lowercase value still reads as bool.
    schema.set_property(XMPageTextSchema.HAS_VISIBLE_TRANSPARENCY, "true")
    assert schema.get_has_visible_transparency() is True
    schema.set_property(XMPageTextSchema.HAS_VISIBLE_OVERPRINT, "false")
    assert schema.get_has_visible_overprint() is False


def test_has_visible_boolean_returns_none_for_garbage_value() -> None:
    schema = _pt()
    schema.set_property(XMPageTextSchema.HAS_VISIBLE_TRANSPARENCY, "not-a-bool")
    assert schema.get_has_visible_transparency() is None


# --- Typed MaxPageSize (DimensionsType) ---------------------------------


def test_max_page_size_typed_round_trip() -> None:
    schema = _pt()
    metadata = schema.get_metadata()
    dim = DimensionsType(metadata)
    dim.set_w(612.0)
    dim.set_h(792.0)
    dim.set_unit("Pt")

    schema.set_max_page_size_property(dim)
    out = schema.get_max_page_size_property()
    assert out is dim
    assert out.get_w() == 612.0
    assert out.get_h() == 792.0
    assert out.get_unit() == "Pt"


def test_max_page_size_typed_materialised_from_dict() -> None:
    schema = _pt()
    schema.set_max_page_size({"w": "612", "h": "792", "unit": "Pt"})

    dim = schema.get_max_page_size_property()
    assert isinstance(dim, DimensionsType)
    assert dim.get_w() == 612.0
    assert dim.get_h() == 792.0
    assert dim.get_unit() == "Pt"


def test_max_page_size_typed_returns_none_for_unknown_storage() -> None:
    schema = _pt()
    # Storing a plain string is not a Dimensions struct — typed accessor
    # should return None, but the legacy accessor still returns the raw value.
    schema.set_max_page_size("612x792 Pt")
    assert schema.get_max_page_size_property() is None
    assert schema.get_max_page_size() == "612x792 Pt"


# --- Typed Fonts (FontType) ---------------------------------------------


def test_fonts_typed_round_trip() -> None:
    schema = _pt()
    metadata = schema.get_metadata()
    helv = FontType(metadata)
    helv.add_simple_property(FontType.FONT_NAME, "Helvetica")
    helv.add_simple_property(FontType.FONT_FAMILY, "Helvetica")
    helv.add_simple_property(FontType.COMPOSITE, False)

    times = FontType(metadata)
    times.add_simple_property(FontType.FONT_NAME, "Times-Roman")

    schema.add_font_property(helv)
    schema.add_font_property(times)

    typed = schema.get_font_properties()
    assert typed is not None
    assert len(typed) == 2
    assert typed[0] is helv
    assert typed[1] is times


def test_fonts_typed_skips_untyped_entries() -> None:
    schema = _pt()
    schema.add_font("Helvetica")
    schema.add_font_property(FontType(schema.get_metadata()))

    # Legacy accessor surfaces both shapes.
    fonts = schema.get_fonts()
    assert fonts is not None
    assert len(fonts) == 2
    # Typed accessor filters down to FontType instances.
    typed = schema.get_font_properties()
    assert typed is not None
    assert len(typed) == 1
    assert isinstance(typed[0], FontType)


# --- Typed Colorants (ColorantType) -------------------------------------


def test_colorants_typed_round_trip() -> None:
    schema = _pt()
    metadata = schema.get_metadata()
    spot = ColorantType(metadata)
    spot.add_simple_property(ColorantType.SWATCH_NAME, "PANTONE 185 C")
    spot.add_simple_property(ColorantType.TYPE, "SPOT")
    spot.add_simple_property(ColorantType.MODE, "RGB")

    schema.add_colorant_property(spot)
    typed = schema.get_colorant_properties()
    assert typed is not None
    assert len(typed) == 1
    assert typed[0] is spot


def test_colorants_typed_skips_untyped_entries() -> None:
    schema = _pt()
    schema.add_colorant("PANTONE 185 C")
    schema.add_colorant_property(ColorantType(schema.get_metadata()))
    schema.add_colorant({"swatchName": "PANTONE 116 C"})

    # Legacy accessor surfaces all three shapes.
    raw = schema.get_colorants()
    assert raw is not None
    assert len(raw) == 3
    # Typed accessor filters to ColorantType only.
    typed = schema.get_colorant_properties()
    assert typed is not None
    assert len(typed) == 1
    assert isinstance(typed[0], ColorantType)


def test_full_round_trip_packet_with_booleans() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:xmpTPg='http://ns.adobe.com/xap/1.0/t/pg/'"
        b" xmpTPg:NPages='5'"
        b" xmpTPg:HasVisibleTransparency='True'"
        b" xmpTPg:HasVisibleOverprint='False'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(XMPageTextSchema)
    assert isinstance(schema, XMPageTextSchema)
    assert schema.get_n_pages() == 5
    assert schema.get_has_visible_transparency() is True
    assert schema.get_has_visible_overprint() is False
