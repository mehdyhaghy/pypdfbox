from __future__ import annotations

from datetime import timedelta

import pytest

from pypdfbox.xmpbox import XMPMetadata, XMPSchema
from pypdfbox.xmpbox.date_converter import to_calendar


class _NoNamespaceSchema:
    pass


class _SchemaWithMovedNamespace(XMPSchema):
    NAMESPACE = "http://example.com/expected/"
    PREFERRED_PREFIX = "ex"


def test_get_schema_returns_none_for_class_without_namespace() -> None:
    metadata = XMPMetadata.create_xmp_metadata()

    assert metadata.get_schema(_NoNamespaceSchema) is None


def test_get_schema_class_falls_back_to_instance_when_namespace_differs() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = _SchemaWithMovedNamespace(
        metadata,
        namespace_uri="http://example.com/actual/",
        prefix="act",
    )
    metadata.add_schema(schema)

    assert metadata.get_schema(_SchemaWithMovedNamespace) is schema


def test_get_schema_by_prefix_returns_none_when_no_schema_matches() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    metadata.add_schema(
        XMPSchema(
            metadata,
            namespace_uri="http://example.com/ns/",
            prefix="ex",
        )
    )

    assert metadata.get_schema_by_prefix("missing", "http://example.com/ns/") is None


def test_date_converter_invalid_iso_raises_oserror() -> None:
    with pytest.raises(OSError):
        to_calendar("2024-02-31T00:00:00")


def test_date_converter_out_of_range_pdf_timezone_folds_modulo_day() -> None:
    # PDFBox's DateConverter does NOT reject an out-of-range TZ designation —
    # ``restrainTZoffset`` folds it modulo a day. ``+99'00'`` therefore parses
    # to +03:00 (verified against the live PDFBox 3.0.7 oracle, which returns
    # 2024-01-01 00:00:00+03:00, not null). A prior wave wrongly expected this
    # to raise.
    parsed = to_calendar("D:20240101000000+99'00'")
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(hours=3)


def test_date_converter_pdf_offset_without_minutes() -> None:
    parsed = to_calendar("D:20240101000000-05")

    assert parsed is not None
    assert parsed.utcoffset() == -timedelta(hours=5)
