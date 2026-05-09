from __future__ import annotations

import math
from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSObject, COSString
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.font.afm_loader import AfmMetrics
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.graphics.blend_mode import _hsl_set_sat


class _MetricsWithoutBBox:
    def get_char_metrics(self) -> list[Any]:
        return []

    def get_font_b_box(self) -> None:
        return None

    def get_font_name(self) -> str:
        return "NoBBox"

    def get_italic_angle(self) -> float:
        return 0.0

    def get_ascender(self) -> float:
        return 0.0

    def get_descender(self) -> float:
        return 0.0

    def get_cap_height(self) -> float:
        return 0.0

    def get_x_height(self) -> float:
        return 0.0

    def get_standard_vertical_width(self) -> float:
        return 0.0

    def get_is_fixed_pitch(self) -> bool:
        return False


def test_wave817_hsl_set_sat_handles_unordered_nan_components() -> None:
    result = _hsl_set_sat(math.nan, 0.25, 0.5, 0.75)

    assert result == (0.0, 0.0, 0.0)


def test_wave817_afm_metrics_descriptor_uses_zero_bbox_when_missing() -> None:
    metrics = AfmMetrics("NoBBox", _MetricsWithoutBBox())  # type: ignore[arg-type]

    assert metrics.get_font_metrics()["FontBBox"] == (0, 0, 0, 0)


def test_wave817_cid_to_gid_map_defaults_to_identity_when_absent() -> None:
    font = PDCIDFontType2()

    assert font.get_cid_to_gid_map() is None
    assert font.is_identity_cid_to_gid_map() is True


def test_wave817_fdf_field_dereferences_indirect_cos_values() -> None:
    options = COSArray([COSObject(817, 0, resolved=COSString("indirect option"))])
    raw = COSDictionary()
    raw.set_item("Opt", options)

    assert FDFField(raw).get_options() == ["indirect option"]
