from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab

# ---------- defaults (PDF 32000-1 §8.6.5.4) ----------


def test_pd_lab_default_white_point_is_unity() -> None:
    assert PDLab().get_white_point() == [1.0, 1.0, 1.0]


def test_pd_lab_default_black_point_is_zero() -> None:
    assert PDLab().get_black_point() == [0.0, 0.0, 0.0]


def test_pd_lab_default_range_is_full_ab() -> None:
    assert PDLab().get_range() == [-100.0, 100.0, -100.0, 100.0]


# ---------- round-trips ----------


def test_pd_lab_white_point_round_trip() -> None:
    cs = PDLab()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.get_white_point() == pytest.approx([0.9505, 1.0, 1.0890])


def test_pd_lab_black_point_round_trip() -> None:
    cs = PDLab()
    cs.set_black_point([0.01, 0.02, 0.03])
    assert cs.get_black_point() == pytest.approx([0.01, 0.02, 0.03])


def test_pd_lab_range_round_trip() -> None:
    cs = PDLab()
    cs.set_range([-80.0, 80.0, -60.0, 60.0])
    assert cs.get_range() == [-80.0, 80.0, -60.0, 60.0]


# ---------- entries land in the params dict at array index 1 ----------


def test_pd_lab_setters_write_to_params_dict() -> None:
    cs = PDLab()
    cs.set_white_point([0.95, 1.0, 1.09])
    cs.set_black_point([0.0, 0.0, 0.0])
    cs.set_range([-50.0, 50.0, -50.0, 50.0])
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert isinstance(arr.get(0), COSName)
    assert arr.get_name(0) == "Lab"
    params = arr.get_object(1)
    assert isinstance(params, COSDictionary)
    wp = params.get_dictionary_object(COSName.get_pdf_name("WhitePoint"))
    bp = params.get_dictionary_object(COSName.get_pdf_name("BlackPoint"))
    rng = params.get_dictionary_object(COSName.get_pdf_name("Range"))
    assert isinstance(wp, COSArray)
    assert isinstance(bp, COSArray)
    assert isinstance(rng, COSArray)
    assert wp.to_float_array() == pytest.approx([0.95, 1.0, 1.09])
    assert bp.to_float_array() == pytest.approx([0.0, 0.0, 0.0])
    assert rng.to_float_array() == pytest.approx([-50.0, 50.0, -50.0, 50.0])
