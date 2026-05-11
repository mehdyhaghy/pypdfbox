"""Tests for the CIE/JPX/Gamma/Tristimulus colour classes (Wave 1281)."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color import (
    PDCIEBasedColorSpace,
    PDCIEDictionaryBasedColorSpace,
    PDGamma,
    PDJPXColorSpace,
    PDTristimulus,
)


def test_pd_tristimulus_default_is_zero():
    t = PDTristimulus()
    assert t.get_x() == 0
    assert t.get_y() == 0
    assert t.get_z() == 0


def test_pd_tristimulus_round_trip_from_array():
    arr = COSArray()
    arr.add(COSFloat(0.5))
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(2.0))
    t = PDTristimulus(arr)
    assert t.get_x() == pytest.approx(0.5)
    assert t.get_y() == pytest.approx(1.0)
    assert t.get_z() == pytest.approx(2.0)
    t.set_x(7.0)
    assert t.get_x() == pytest.approx(7.0)


def test_pd_tristimulus_from_float_list_truncates_to_three():
    t = PDTristimulus([0.1, 0.2, 0.3, 0.4])
    assert t.get_x() == pytest.approx(0.1)
    assert t.get_y() == pytest.approx(0.2)
    assert t.get_z() == pytest.approx(0.3)


def test_pd_gamma_defaults_and_accessors():
    g = PDGamma()
    assert g.get_r() == 0
    g.set_r(2.2)
    g.set_g(2.2)
    g.set_b(2.2)
    assert g.get_r() == pytest.approx(2.2)
    assert g.get_g() == pytest.approx(2.2)
    assert g.get_b() == pytest.approx(2.2)
    assert g.get_cos_array() is g.get_cos_object()


def test_pd_cie_based_is_abstract():
    with pytest.raises(TypeError):
        PDCIEBasedColorSpace()


class _Stub(PDCIEDictionaryBasedColorSpace):
    def to_rgb(self, value):
        return value[:3]

    def get_name(self):
        return "Stub"

    def get_number_of_components(self):
        return 3

    def get_default_decode(self, bits_per_component):
        return [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]

    def get_initial_color(self):
        return None


def test_pd_cie_dictionary_default_white_point_is_unity():
    cs = _Stub(COSName.get_pdf_name("CalGray"))
    assert cs.wp_x == 1
    assert cs.wp_y == 1
    assert cs.wp_z == 1
    assert cs.is_white_point() is True
    rgb = cs.conv_xyz_to_rgb(0.5, 0.5, 0.5)
    assert len(rgb) == 3


def test_pd_cie_dictionary_set_white_point_rejects_none():
    cs = _Stub(COSName.get_pdf_name("CalGray"))
    with pytest.raises(ValueError):
        cs.set_white_point(None)


def test_pd_jpx_color_space_min_max_decode():
    class _AWT:
        def get_num_components(self):
            return 3

        def get_min_value(self, i):
            return 0.0

        def get_max_value(self, i):
            return 1.0

        def to_rgb(self, value):
            return list(value)

    cs = PDJPXColorSpace(_AWT())
    assert cs.get_name() == "JPX"
    assert cs.get_number_of_components() == 3
    assert cs.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    with pytest.raises(NotImplementedError):
        cs.get_initial_color()
    with pytest.raises(NotImplementedError):
        cs.get_cos_object()
