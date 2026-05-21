"""Deep parity tests for the ``/BitsPerCoordinate`` / ``/BitsPerComponent``
/ ``/BitsPerFlag`` metadata round-trip on every mesh-based shading type
(4, 5, 6, 7). These three entries are spec-required (PDF 32000-1 §8.7.4.5
Tables 86-89) but pypdfbox does not assert their values — round-trip
fidelity is what callers and the eventual renderer rely on.

Also pins:
  * default-getter behavior when the entry is unset (``-1`` mirrors
    upstream's ``COSDictionary.getInt`` default).
  * ``/BitsPerFlag`` absent on Type 5 (lattice form has no flag stream).
  * Setter accepts every spec-listed legal value without normalising.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)

_BPC_TYPES = (PDShadingType4, PDShadingType5, PDShadingType6, PDShadingType7)
# Types 4, 6, 7 have a /BitsPerFlag — Type 5 (lattice) does not.
_BPF_TYPES = (PDShadingType4, PDShadingType6, PDShadingType7)


@pytest.mark.parametrize("cls", _BPC_TYPES)
def test_bits_per_coordinate_default_minus_one(cls):
    assert cls().get_bits_per_coordinate() == -1


@pytest.mark.parametrize("cls", _BPC_TYPES)
def test_bits_per_component_default_minus_one(cls):
    assert cls().get_bits_per_component() == -1


@pytest.mark.parametrize("cls", _BPF_TYPES)
def test_bits_per_flag_default_minus_one(cls):
    assert cls().get_bits_per_flag() == -1


# Type 5 — no /BitsPerFlag accessor on the wrapper (lattice form skips it).
def test_type5_does_not_expose_bits_per_flag():
    assert not hasattr(PDShadingType5(), "get_bits_per_flag")


@pytest.mark.parametrize("cls", _BPC_TYPES)
@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16, 24, 32])
def test_bits_per_coordinate_round_trip(cls, bits):
    shading = cls()
    shading.set_bits_per_coordinate(bits)
    assert shading.get_bits_per_coordinate() == bits
    assert shading.get_cos_object().get_int("BitsPerCoordinate") == bits


@pytest.mark.parametrize("cls", _BPC_TYPES)
@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16])
def test_bits_per_component_round_trip(cls, bits):
    shading = cls()
    shading.set_bits_per_component(bits)
    assert shading.get_bits_per_component() == bits
    assert shading.get_cos_object().get_int("BitsPerComponent") == bits


@pytest.mark.parametrize("cls", _BPF_TYPES)
@pytest.mark.parametrize("bits", [2, 4, 8])
def test_bits_per_flag_round_trip(cls, bits):
    shading = cls()
    shading.set_bits_per_flag(bits)
    assert shading.get_bits_per_flag() == bits


@pytest.mark.parametrize("cls", _BPC_TYPES)
def test_setters_do_not_normalise_unusual_values(cls):
    # Upstream stores any int we hand it — validation belongs to the
    # parser layer, not the wrapper. Mirror that contract.
    shading = cls()
    shading.set_bits_per_coordinate(7)  # not a legal spec value
    assert shading.get_bits_per_coordinate() == 7
    shading.set_bits_per_component(3)
    assert shading.get_bits_per_component() == 3


# ---------------------------------------------------------------------------
# Type 5 specifically — /VerticesPerRow
# ---------------------------------------------------------------------------


def test_type5_vertices_per_row_default_is_unset():
    assert PDShadingType5().get_vertices_per_row() == -1


@pytest.mark.parametrize("count", [2, 3, 5, 10, 100, 1000])
def test_type5_vertices_per_row_round_trip(count):
    shading = PDShadingType5()
    shading.set_vertices_per_row(count)
    assert shading.get_vertices_per_row() == count
    assert shading.get_cos_object().get_int("VerticesPerRow") == count


def test_type5_create_shaded_triangle_list_degenerate_row_or_col_returns_empty():
    # Both axes need at least 2 vertices to form any lattice cell.
    s = PDShadingType5()
    assert s.create_shaded_triangle_list(1, 5, []) == []
    assert s.create_shaded_triangle_list(5, 1, []) == []
    assert s.create_shaded_triangle_list(0, 0, []) == []


def test_type5_create_shaded_triangle_list_emits_2_triangles_per_cell():
    s = PDShadingType5()
    # Build a 2×3 lattice — 1 row of cells × 2 columns of cells = 2 cells.
    # Each cell emits 2 triangles for a total of 4.
    lattice = [
        [((0.0, 0.0), (0.1,)), ((1.0, 0.0), (0.2,)), ((2.0, 0.0), (0.3,))],
        [((0.0, 1.0), (0.4,)), ((1.0, 1.0), (0.5,)), ((2.0, 1.0), (0.6,))],
    ]
    triangles = s.create_shaded_triangle_list(2, 3, lattice)
    assert len(triangles) == 4
