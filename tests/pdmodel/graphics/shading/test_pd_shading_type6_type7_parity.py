"""Parity tests for the Coons-patch (Type 6) and tensor-product (Type 7)
patch-mesh shading wrappers.

Covers the per-PDF-spec metadata accessors required by PDF 32000-1
§8.7.4.5.7-8 (Tables 88-89): ``/BitsPerCoordinate``, ``/BitsPerComponent``,
``/BitsPerFlag``, ``/Decode``, and ``/Function``. Round-trips each accessor
and verifies the documented defaults when the entry is absent.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType2,
)
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType6,
    PDShadingType7,
)

# ---------- helpers ----------


def _make_function_type2_dict() -> COSDictionary:
    """Build a minimal Type 2 (exponential-interpolation) function dict."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    domain = COSArray()
    for v in (0.0, 1.0):
        domain.add(COSFloat(v))
    d.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_int("N", 1)
    return d


# ---------- BitsPerCoordinate ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16, 24, 32])
def test_bits_per_coordinate_round_trip(cls, bits):
    s = cls()
    s.set_bits_per_coordinate(bits)
    assert s.get_bits_per_coordinate() == bits


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_bits_per_coordinate_default_when_absent(cls):
    # COSDictionary.get_int returns -1 when the key is missing; the upstream
    # accessor relies on the same sentinel.
    assert cls().get_bits_per_coordinate() == -1


# ---------- BitsPerComponent ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
@pytest.mark.parametrize("bits", [1, 2, 4, 8, 12, 16])
def test_bits_per_component_round_trip(cls, bits):
    s = cls()
    s.set_bits_per_component(bits)
    assert s.get_bits_per_component() == bits


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_bits_per_component_default_when_absent(cls):
    assert cls().get_bits_per_component() == -1


# ---------- BitsPerFlag ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
@pytest.mark.parametrize("bits", [2, 4, 8])
def test_bits_per_flag_round_trip(cls, bits):
    s = cls()
    s.set_bits_per_flag(bits)
    assert s.get_bits_per_flag() == bits


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_bits_per_flag_default_when_absent(cls):
    assert cls().get_bits_per_flag() == -1


# ---------- Decode ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_default_when_absent(cls):
    assert cls().get_decode() is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_round_trip_from_iterable(cls):
    s = cls()
    # 2 * (2 + N) entries: xy pair + 1 color component (N = 1 → 6 floats).
    expected = [0.0, 100.0, 0.0, 100.0, 0.0, 1.0]
    s.set_decode(expected)
    assert s.get_decode() == expected
    # And the underlying COSArray was populated.
    arr = s.get_cos_object().get_dictionary_object("Decode")
    assert isinstance(arr, COSArray)
    assert arr.size() == 6


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_round_trip_from_cos_array(cls):
    s = cls()
    arr = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):  # N = 2 → 8 floats
        arr.add(COSFloat(v))
    s.set_decode(arr)
    # COSArray identity preserved (set_item stores it as-is).
    assert s.get_cos_object().get_dictionary_object("Decode") is arr
    # And the typed getter materializes the float view.
    assert s.get_decode() == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_decode_set_none_removes_entry(cls):
    s = cls()
    s.set_decode([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    assert s.get_decode() is not None
    s.set_decode(None)
    assert s.get_decode() is None
    assert s.get_cos_object().get_dictionary_object("Decode") is None


# ---------- Function ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_default_when_absent(cls):
    assert cls().get_function() is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_round_trip_from_pd_function(cls):
    s = cls()
    func = PDFunctionType2(_make_function_type2_dict())
    s.set_function(func)
    got = s.get_function()
    assert isinstance(got, PDFunction)
    assert isinstance(got, PDFunctionType2)
    assert got.get_function_type() == 2
    # The COS object stored under /Function is the function's backing dict.
    assert (
        s.get_cos_object().get_dictionary_object("Function")
        is func.get_cos_object()
    )


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_round_trip_from_cos_dictionary(cls):
    s = cls()
    raw = _make_function_type2_dict()
    s.set_function(raw)
    got = s.get_function()
    assert isinstance(got, PDFunctionType2)
    assert s.get_cos_object().get_dictionary_object("Function") is raw


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_set_none_removes_entry(cls):
    s = cls()
    s.set_function(_make_function_type2_dict())
    assert s.get_function() is not None
    s.set_function(None)
    assert s.get_function() is None
    assert s.get_cos_object().get_dictionary_object("Function") is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_function_rejects_unsupported_type(cls):
    s = cls()
    with pytest.raises(TypeError):
        s.set_function(42)  # type: ignore[arg-type]


# ---------- backing-stream sanity ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_metadata_lives_on_backing_stream(cls):
    s = cls()
    s.set_bits_per_coordinate(16)
    s.set_bits_per_component(8)
    s.set_bits_per_flag(4)
    backing = s.get_cos_object()
    # Type 6/7 are stream-based per Tables 88-89.
    assert isinstance(backing, COSStream)
    assert backing.get_int("BitsPerCoordinate") == 16
    assert backing.get_int("BitsPerComponent") == 8
    assert backing.get_int("BitsPerFlag") == 4


# ---------- to_paint / get_bounds (lite-surface rendering hooks) ----------


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_to_paint_lite_surface_returns_none(cls):
    # Mirrors upstream toPaint(Matrix) which returns a Type6/7ShadingPaint.
    # The Pillow-based renderer doesn't use AWT Paint; lite surface returns None.
    assert cls().to_paint() is None
    assert cls().to_paint(matrix=object()) is None


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_get_bounds_lite_surface_returns_none(cls):
    # Mirrors upstream getBounds(AffineTransform, Matrix) → 12 / 16 control
    # points; bounds requires patch decoding which belongs to rendering.
    assert cls().get_bounds() is None
    assert cls().get_bounds(None, None) is None
    assert cls().get_bounds(object(), object()) is None


# ---------- generate_patch (control-point arity validation) ----------


def _make_points(n):
    return [(float(i), float(i)) for i in range(n)]


def _make_colors(n_components=1):
    return [[0.5] * n_components for _ in range(4)]


def test_type6_generate_patch_returns_coons_descriptor():
    s = PDShadingType6()
    out = s.generate_patch(_make_points(12), _make_colors(1))
    assert out["kind"] == "coons"
    assert len(out["points"]) == 12
    assert len(out["color"]) == 4


def test_type7_generate_patch_returns_tensor_descriptor():
    s = PDShadingType7()
    out = s.generate_patch(_make_points(16), _make_colors(3))
    assert out["kind"] == "tensor"
    assert len(out["points"]) == 16
    assert len(out["color"]) == 4
    assert all(len(c) == 3 for c in out["color"])


@pytest.mark.parametrize(
    "cls,expected_count",
    [(PDShadingType6, 12), (PDShadingType7, 16)],
)
def test_generate_patch_rejects_wrong_control_point_count(cls, expected_count):
    s = cls()
    with pytest.raises(ValueError):
        s.generate_patch(_make_points(expected_count - 1), _make_colors())
    with pytest.raises(ValueError):
        s.generate_patch(_make_points(expected_count + 1), _make_colors())


@pytest.mark.parametrize(
    "cls,n_points",
    [(PDShadingType6, 12), (PDShadingType7, 16)],
)
def test_generate_patch_rejects_wrong_corner_color_count(cls, n_points):
    s = cls()
    with pytest.raises(ValueError):
        s.generate_patch(_make_points(n_points), [[0.0]] * 3)
    with pytest.raises(ValueError):
        s.generate_patch(_make_points(n_points), [[0.0]] * 5)


@pytest.mark.parametrize("cls", [PDShadingType6, PDShadingType7])
def test_generate_patch_copies_input_sequences(cls):
    # The descriptor's lists must not alias caller-mutable inputs.
    n = 12 if cls is PDShadingType6 else 16
    pts = _make_points(n)
    colors = _make_colors(2)
    out = cls().generate_patch(pts, colors)
    out["points"].append((999.0, 999.0))
    out["color"][0].append(123.0)
    assert len(pts) == n
    assert len(colors[0]) == 2
