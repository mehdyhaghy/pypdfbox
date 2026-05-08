from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB

# ---------- PDCalGray defaults (PDF 32000-1 §8.6.5.2 Table 65) ----------


def test_pd_cal_gray_default_white_point_is_unity() -> None:
    assert PDCalGray().get_white_point() == [1.0, 1.0, 1.0]


def test_pd_cal_gray_default_black_point_is_zero() -> None:
    assert PDCalGray().get_black_point() == [0.0, 0.0, 0.0]


def test_pd_cal_gray_default_gamma_is_one_scalar() -> None:
    g = PDCalGray().get_gamma()
    assert isinstance(g, float)
    assert g == 1.0


# ---------- PDCalGray round-trips ----------


def test_pd_cal_gray_white_point_round_trip() -> None:
    cs = PDCalGray()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.get_white_point() == pytest.approx([0.9505, 1.0, 1.0890])


def test_pd_cal_gray_black_point_round_trip() -> None:
    cs = PDCalGray()
    cs.set_black_point([0.01, 0.02, 0.03])
    assert cs.get_black_point() == pytest.approx([0.01, 0.02, 0.03])


def test_pd_cal_gray_gamma_round_trip() -> None:
    cs = PDCalGray()
    cs.set_gamma(2.2)
    assert cs.get_gamma() == pytest.approx(2.2)


def test_pd_cal_gray_setters_write_to_params_dict() -> None:
    cs = PDCalGray()
    cs.set_white_point([0.95, 1.0, 1.09])
    cs.set_black_point([0.0, 0.0, 0.0])
    cs.set_gamma(1.8)
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert isinstance(arr.get(0), COSName)
    assert arr.get_name(0) == "CalGray"
    params = arr.get_object(1)
    assert isinstance(params, COSDictionary)
    wp = params.get_dictionary_object(COSName.get_pdf_name("WhitePoint"))
    bp = params.get_dictionary_object(COSName.get_pdf_name("BlackPoint"))
    assert isinstance(wp, COSArray)
    assert isinstance(bp, COSArray)
    assert wp.to_float_array() == pytest.approx([0.95, 1.0, 1.09])
    assert bp.to_float_array() == pytest.approx([0.0, 0.0, 0.0])
    assert params.get_float(COSName.get_pdf_name("Gamma")) == pytest.approx(1.8)


# ---------- PDCalRGB defaults (PDF 32000-1 §8.6.5.3 Table 66) ----------


def test_pd_cal_rgb_default_white_point_is_unity() -> None:
    assert PDCalRGB().get_white_point() == [1.0, 1.0, 1.0]


def test_pd_cal_rgb_default_black_point_is_zero() -> None:
    assert PDCalRGB().get_black_point() == [0.0, 0.0, 0.0]


def test_pd_cal_rgb_default_gamma_is_unit_triple() -> None:
    g = PDCalRGB().get_gamma()
    assert g == [1.0, 1.0, 1.0]
    assert len(g) == 3


def test_pd_cal_rgb_default_matrix_is_identity() -> None:
    # Per §8.6.5.3 and upstream PDFBox, when /Matrix is absent the
    # accessor returns the flattened identity matrix default.
    assert PDCalRGB().get_matrix() == [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]


# ---------- PDCalRGB round-trips ----------


def test_pd_cal_rgb_white_point_round_trip() -> None:
    cs = PDCalRGB()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.get_white_point() == pytest.approx([0.9505, 1.0, 1.0890])


def test_pd_cal_rgb_black_point_round_trip() -> None:
    cs = PDCalRGB()
    cs.set_black_point([0.01, 0.02, 0.03])
    assert cs.get_black_point() == pytest.approx([0.01, 0.02, 0.03])


def test_pd_cal_rgb_gamma_round_trip_triple() -> None:
    cs = PDCalRGB()
    cs.set_gamma([2.2, 2.2, 2.2])
    g = cs.get_gamma()
    assert g == pytest.approx([2.2, 2.2, 2.2])
    assert len(g) == 3


def test_pd_cal_rgb_matrix_round_trip() -> None:
    cs = PDCalRGB()
    matrix = [
        0.4124, 0.3576, 0.1805,
        0.2126, 0.7152, 0.0722,
        0.0193, 0.1192, 0.9505,
    ]
    cs.set_matrix(matrix)
    assert cs.get_matrix() == pytest.approx(matrix)


def test_pd_cal_rgb_matrix_clear_returns_identity_default() -> None:
    cs = PDCalRGB()
    cs.set_matrix([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
    assert cs.has_matrix()
    cs.set_matrix(None)
    assert not cs.has_matrix()
    assert cs.get_matrix() == [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]


def test_pd_cal_rgb_setters_write_to_params_dict() -> None:
    cs = PDCalRGB()
    cs.set_white_point([0.95, 1.0, 1.09])
    cs.set_black_point([0.0, 0.0, 0.0])
    cs.set_gamma([1.8, 1.8, 1.8])
    cs.set_matrix([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert isinstance(arr.get(0), COSName)
    assert arr.get_name(0) == "CalRGB"
    params = arr.get_object(1)
    assert isinstance(params, COSDictionary)
    wp = params.get_dictionary_object(COSName.get_pdf_name("WhitePoint"))
    bp = params.get_dictionary_object(COSName.get_pdf_name("BlackPoint"))
    gm = params.get_dictionary_object(COSName.get_pdf_name("Gamma"))
    mx = params.get_dictionary_object(COSName.get_pdf_name("Matrix"))
    assert isinstance(wp, COSArray)
    assert isinstance(bp, COSArray)
    assert isinstance(gm, COSArray)
    assert isinstance(mx, COSArray)
    assert wp.to_float_array() == pytest.approx([0.95, 1.0, 1.09])
    assert bp.to_float_array() == pytest.approx([0.0, 0.0, 0.0])
    assert gm.to_float_array() == pytest.approx([1.8, 1.8, 1.8])
    assert mx.to_float_array() == pytest.approx(
        [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    )
