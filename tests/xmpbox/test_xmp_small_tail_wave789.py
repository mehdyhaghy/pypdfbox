from __future__ import annotations

from datetime import date, timedelta

import pytest

from pypdfbox.xmpbox import RationalType, TextType, TypeMapping, XMPMetadata, XMPSchema
from pypdfbox.xmpbox.date_converter import to_calendar
from pypdfbox.xmpbox.type import AbstractStructuredType


class _NoNamespaceSchema:
    pass


class _FallbackSchema(XMPSchema):
    NAMESPACE = "http://example.com/expected/"
    PREFERRED_PREFIX = "ex"


class _BareStructured(AbstractStructuredType):
    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(
            metadata,
            "http://example.com/struct/",
            "st",
            "Struct",
        )


def test_wave789_date_converter_invalid_iso_and_pdf_value_errors() -> None:
    # An impossible ISO calendar date (Feb 31) is rejected — PDFBox returns
    # null; pypdfbox surfaces the rejection as OSError.
    with pytest.raises(OSError):
        to_calendar("2024-02-31T00:00:00")

    # An out-of-range PDF TZ designation is NOT rejected — PDFBox's
    # ``restrainTZoffset`` folds it modulo a day, so ``+99'00'`` parses to
    # +03:00 (verified against the live PDFBox 3.0.7 oracle).
    parsed = to_calendar("D:20240101000000+99'00'")
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(hours=3)


def test_wave789_date_converter_pdf_offset_without_minutes() -> None:
    parsed = to_calendar("D:20240101000000-05")

    assert parsed is not None
    assert parsed.utcoffset() == -timedelta(hours=5)


def test_wave789_metadata_schema_lookup_tails() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _FallbackSchema(
        metadata,
        namespace_uri="http://example.com/actual/",
        prefix="act",
    )
    metadata.add_schema(schema)

    assert metadata.get_schema(_NoNamespaceSchema) is None
    assert metadata.get_schema(_FallbackSchema) is schema
    assert metadata.get_schema_by_prefix("missing", "http://example.com/actual/") is None


def test_wave789_type_mapping_unknown_structured_and_rational_factory() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    mapping = TypeMapping(metadata)

    with pytest.raises(ValueError, match="Unknown structured property type"):
        mapping.instanciate_structured_type("NoSuchType")

    rational = mapping.create_rational("ns", "p", "ExposureTime", "1/125")
    assert isinstance(rational, RationalType)
    assert rational.as_fraction() is not None


def test_wave789_abstract_structured_conversion_helpers() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    structured = _BareStructured(metadata)

    assert structured._is_calendar_like(date(2026, 5, 9)) is True  # noqa: SLF001
    assert structured._is_calendar_like("2026-05-09") is False  # noqa: SLF001

    attr = structured._new_attribute("http://example.com/ns/", "kind", "value")  # noqa: SLF001
    assert attr.get_namespace() == "http://example.com/ns/"
    assert attr.get_name() == "kind"
    assert attr.get_value() == "value"

    text = TextType(metadata, structured.get_namespace(), structured.get_prefix(), "name", "v")
    structured.add_property(text)
    structured.clear()
    assert structured.get_all_properties() == []
