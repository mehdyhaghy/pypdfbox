from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSObject, COSString
from pypdfbox.fontbox.afm import FontMetrics
from pypdfbox.pdmodel.fdf import FDFField
from pypdfbox.pdmodel.font.afm_loader import AfmMetrics
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2


def test_wave827_fdf_value_conversion_resolves_indirect_object_in_array() -> None:
    field = FDFField()
    raw_values = COSArray(
        [
            COSObject(1, resolved=COSString("wrapped")),
            COSName.get_pdf_name("On"),
        ]
    )
    field.get_cos_object().set_item("V", raw_values)

    assert field.get_value() == ["wrapped", "On"]


def test_wave827_fdf_option_pair_rejects_wrong_shape() -> None:
    field = FDFField()

    with pytest.raises(TypeError, match="exactly two strings"):
        field.set_options([("export", "display", "extra")])


def test_wave827_afm_metrics_without_bbox_uses_zero_descriptor_bbox() -> None:
    font_metrics = FontMetrics()
    font_metrics.set_font_name("NoBBox")

    afm = AfmMetrics("NoBBox", font_metrics)

    assert afm.get_font_metrics()["FontBBox"] == (0, 0, 0, 0)


def test_wave827_cid_to_gid_map_absent_is_identity_default() -> None:
    font = PDCIDFontType2()

    assert font.get_cid_to_gid_map() is None
    assert font.is_identity_cid_to_gid_map() is True


def test_wave827_cid_to_gid_map_identity_name_and_non_identity_name() -> None:
    font = PDCIDFontType2()

    font.set_cid_to_gid_map("Identity")
    assert font.get_cid_to_gid_map() == "Identity"
    assert font.is_identity_cid_to_gid_map() is True

    font.set_cid_to_gid_map("Custom")
    assert font.is_identity_cid_to_gid_map() is False

    font.set_cid_to_gid_map(None)
    assert font.is_identity_cid_to_gid_map() is True
