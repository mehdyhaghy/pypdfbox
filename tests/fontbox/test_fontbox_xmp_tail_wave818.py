from __future__ import annotations

import logging

from pypdfbox.fontbox.cmap.cmap_parser import _increment
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.xmpbox import (
    AdobePDFSchema,
    PDFAExtensionSchema,
    PhotoshopSchema,
    TextType,
    XMPMetadata,
    XMPSchema,
)


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave818_increment_non_strict_reports_leading_overflow() -> None:
    value = bytearray(b"\xff")

    assert _increment(value, 0, use_strict_mode=False) is True
    assert value == b"\x00"


class _BeyondUCS4Start:
    def __gt__(self, _other: object) -> bool:
        return False

    def __ge__(self, _other: object) -> bool:
        return False

    def __rsub__(self, _other: object) -> int:
        return 0

    def __add__(self, other: object) -> int:
        return 0x110000 + int(other)


class _Format12Data:
    def __init__(self) -> None:
        self._values = iter([1, _BeyondUCS4Start(), 0, 1])

    def read_unsigned_int(self) -> object:
        return next(self._values)


def test_wave818_format12_logs_character_beyond_ucs4_defensively(
    caplog: object,
) -> None:
    subtable = CmapSubtable()
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable")

    subtable._process_subtype_12(_Format12Data(), num_glyphs=10)  # type: ignore[arg-type]  # noqa: SLF001

    assert "Format 12 cmap contains character beyond UCS-4" in caplog.text


def test_wave818_adobe_pdf_known_properties_unwraps_raw_text_type() -> None:
    metadata = _metadata()
    schema = AdobePDFSchema(metadata)
    producer = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        AdobePDFSchema.PRODUCER,
        "typed producer",
    )
    schema.set_property(AdobePDFSchema.PRODUCER, producer)

    assert schema.get_known_properties() == {AdobePDFSchema.PRODUCER: "typed producer"}


def test_wave818_pdfa_extension_unrecognized_schema_storage_returns_empty_list() -> None:
    schema = PDFAExtensionSchema(_metadata())
    schema.set_property(PDFAExtensionSchema.SCHEMAS, {"unexpected": "shape"})

    assert schema.get_extension_schemas() == []
    assert schema.get_schemas_element() == {"unexpected": "shape"}


def test_wave818_photoshop_integer_reader_ignores_non_text_container() -> None:
    schema = PhotoshopSchema(_metadata())
    schema.set_property(PhotoshopSchema.URGENCY, [object()])

    assert schema.get_urgency() is None


def test_wave818_xmp_schema_bag_reader_ignores_unknown_storage_shape() -> None:
    schema = XMPSchema(_metadata(), namespace_uri="urn:test", prefix="t")
    schema.set_property("bag", object())

    assert schema.get_unqualified_bag_value_list("bag") is None
