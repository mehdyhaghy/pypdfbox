from __future__ import annotations

from pypdfbox.cos import COSName, COSObject, COSString
from pypdfbox.fontbox.afm import FontMetrics
from pypdfbox.pdmodel.fdf import FDFField
from pypdfbox.pdmodel.font.afm_loader import AfmMetrics
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0


def test_wave848_fdf_default_value_resolves_indirect_string() -> None:
    field = FDFField()
    field.get_cos_object().set_item(
        COSName.get_pdf_name("DV"),
        COSObject(12, resolved=COSString("wrapped default")),
    )

    assert field.get_default_value() == "wrapped default"


def test_wave848_afm_metrics_without_font_bbox_uses_zero_tuple() -> None:
    font_metrics = FontMetrics()
    font_metrics.set_font_name("Synthetic-NoBBox")
    afm = AfmMetrics("Synthetic-NoBBox", font_metrics)

    metrics = afm.get_font_metrics()

    assert metrics["FontName"] == "Synthetic-NoBBox"
    assert metrics["FontBBox"] == (0, 0, 0, 0)


def test_wave848_cid_font_absent_cid_to_gid_map_defaults_to_identity() -> None:
    font = PDCIDFontType0()

    assert font.get_cid_to_gid_map() is None
    assert font.is_identity_cid_to_gid_map() is True
