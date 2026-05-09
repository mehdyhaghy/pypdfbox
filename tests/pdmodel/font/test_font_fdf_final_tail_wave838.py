from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSObject, COSString
from pypdfbox.fontbox.afm import FontMetrics
from pypdfbox.pdmodel.fdf import FDFField
from pypdfbox.pdmodel.font import (
    PDCIDFontType0,
    PDFontFactory,
    PDType1Font,
    Standard14Fonts,
)
from pypdfbox.pdmodel.font.afm_loader import AfmMetrics


def test_wave838_fdf_default_value_resolves_indirect_cos_object() -> None:
    field = FDFField()
    field.get_cos_object().set_item("DV", COSObject(838, resolved=COSInteger.get(7)))

    assert field.get_default_value() == 7


def test_wave838_fdf_options_resolve_wrapped_cos_values() -> None:
    field = FDFField()
    options = COSArray(
        [
            COSObject(1, resolved=COSString("Wrapped")),
            COSName.get_pdf_name("Named"),
        ]
    )
    field.get_cos_object().set_item("Opt", options)

    assert field.get_options() == ["Wrapped", "Named"]


def test_wave838_fdf_rich_text_rejects_non_rich_text_values() -> None:
    field = FDFField()

    with pytest.raises(TypeError, match="set_rich_text expected"):
        field.set_rich_text(COSInteger.get(1))  # type: ignore[arg-type]


def test_wave838_afm_metrics_without_bbox_reports_zero_descriptor() -> None:
    font_metrics = FontMetrics()
    font_metrics.set_font_name("NoBBox")

    metrics = AfmMetrics("NoBBox", font_metrics)

    assert metrics.get_font_b_box() is None
    assert metrics.has_font_b_box() is False
    assert metrics.get_font_metrics()["FontBBox"] == (0, 0, 0, 0)


def test_wave838_cid_to_gid_absent_is_identity_for_type0_descendant() -> None:
    font = PDCIDFontType0()

    assert font.get_cid_to_gid_map() is None
    assert font.has_cid_to_gid_map_stream() is False
    assert font.is_identity_cid_to_gid_map() is True


def test_wave838_font_factory_default_font_falls_back_to_helvetica() -> None:
    font = PDFontFactory.create_default_font("NotAStandard14Alias")

    assert isinstance(font, PDType1Font)
    assert font.get_name() == Standard14Fonts.HELVETICA
    assert font.get_subtype() == PDType1Font.SUB_TYPE


def test_wave838_font_factory_header_kind_classifies_tails() -> None:
    assert PDFontFactory.get_font_program_kind(b"\x00\x01\x00\x00") == "TrueType"
    assert PDFontFactory.get_font_program_kind(b"ttcf") == "TrueTypeCollection"
    assert PDFontFactory.get_font_program_kind(b"OTTO") == "OpenType"
    assert PDFontFactory.get_font_program_kind(b"%!PS") == "Type1"
    assert PDFontFactory.get_font_program_kind(bytes([0x80, 0x01, 0x00, 0x00])) == "PFB"
    assert PDFontFactory.get_font_program_kind(bytes([0x01, 0x00, 0x04, 0x04])) == "CFF"
