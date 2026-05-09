from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.text.pdf_text_stripper_by_area import _normalize_rect
from pypdfbox.xmpbox import (
    AdobePDFSchema,
    PDFAExtensionSchema,
    PhotoshopSchema,
    TextType,
    XMPMetadata,
)


class _RectLike:
    def get_lower_left_x(self) -> str:
        return "1.5"

    def get_lower_left_y(self) -> int:
        return 2

    def get_upper_right_x(self) -> int:
        return 3

    def get_upper_right_y(self) -> int:
        return 4


def test_wave850_text_area_normalizes_duck_typed_rectangle_accessors() -> None:
    assert _normalize_rect(_RectLike()) == (1.5, 2.0, 3.0, 4.0)


def test_wave850_adobe_pdf_known_properties_unwrap_text_type_values() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(metadata)
    keywords = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        AdobePDFSchema.KEYWORDS,
        "alpha beta",
    )

    schema.set_keywords_property(keywords)

    assert schema.get_known_properties() == {"Keywords": "alpha beta"}


def test_wave850_pdfa_extension_schema_ignores_unrecognized_schema_shape() -> None:
    schema = PDFAExtensionSchema(XMPMetadata.create_xmp_metadata())
    schema._properties[schema.SCHEMAS] = ["parser placeholder"]

    assert schema.get_extension_schemas() == []


def test_wave850_photoshop_integer_reader_returns_none_for_empty_list_shape() -> None:
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())
    schema._properties[schema.COLOR_MODE] = []

    assert schema.get_color_mode() is None


def test_wave850_destination_base_get_cos_object_is_abstract() -> None:
    with pytest.raises(NotImplementedError):
        PDDestination().get_cos_object()
