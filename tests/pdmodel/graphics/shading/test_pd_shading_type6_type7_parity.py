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


# ---------- collect_patches (wave 1507: working render path) ----------
#
# The concrete Type 6 / 7 shadings now extend ``PDMeshBasedShadingType``
# (mirroring upstream's hierarchy) and inherit a WORKING ``collect_patches``
# that builds triangulated ``CoonsPatch`` / ``TensorPatch`` objects — the
# orphan that ``PatchMeshesShadingContext`` calls is no longer a stub. The
# decoded geometry itself is pinned bit-for-bit against PDFBox by the live
# oracle in ``tests/rendering/oracle/test_patch_mesh_decode_oracle.py``; here
# we assert the model-layer contract (right Patch subclass, triangulated,
# corner colours preserved, fallbacks).


class _BitWriter:
    def __init__(self):
        self._bits = []

    def write(self, value, n):
        for i in range(n - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def to_bytes(self):
        bits = list(self._bits)
        while len(bits) % 8 != 0:
            bits.append(0)
        out = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i + j]
            out.append(byte)
        return bytes(out)


def _decode_rgb():
    arr = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        arr.add(COSFloat(v))
    return arr


def _free_patch_shading(cls, control_points):
    sh = COSStream()
    sh.set_int("ShadingType", 6 if cls is PDShadingType6 else 7)
    from pypdfbox.cos import COSName

    sh.set_item("ColorSpace", COSName.get_pdf_name("DeviceRGB"))
    sh.set_int("BitsPerCoordinate", 8)
    sh.set_int("BitsPerComponent", 8)
    sh.set_int("BitsPerFlag", 8)
    sh.set_item("Decode", _decode_rgb())
    bw = _BitWriter()
    bw.write(0, 8)  # free patch
    pts = [(float(i * 5 % 100), float((i * 7) % 100)) for i in range(control_points)]
    for x, y in pts:
        bw.write(round(x / 100 * 255), 8)
        bw.write(round(y / 100 * 255), 8)
    for rgb in ((1, 0, 0), (0, 1, 0), (1, 1, 1), (0, 0, 1)):
        for c in rgb:
            bw.write(round(c * 255), 8)
    sh.set_raw_data(bw.to_bytes())
    return cls(sh)


def test_type6_collect_patches_builds_triangulated_coons_patch():
    from pypdfbox.pdmodel.graphics.shading.coons_patch import CoonsPatch

    s = _free_patch_shading(PDShadingType6, 12)
    patches = s.collect_patches(None, None, 12)
    assert len(patches) == 1
    assert isinstance(patches[0], CoonsPatch)
    assert len(patches[0].list_of_triangles) > 0
    assert patches[0].corner_color == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 1.0],
    ]


def test_type7_collect_patches_builds_triangulated_tensor_patch():
    from pypdfbox.pdmodel.graphics.shading.tensor_patch import TensorPatch

    s = _free_patch_shading(PDShadingType7, 16)
    patches = s.collect_patches(None, None, 16)
    assert len(patches) == 1
    assert isinstance(patches[0], TensorPatch)
    assert len(patches[0].list_of_triangles) > 0


def test_collect_patches_returns_empty_when_backing_is_dictionary():
    # No-arg constructor backs a COSStream, but a shading wrapping a bare
    # COSDictionary (no stream body) yields no patches — mirrors upstream's
    # ``collectPatches`` empty-list guard.
    s = PDShadingType6(COSDictionary())
    assert s.collect_patches(None, None, 12) == []


def test_collect_patches_applies_matrix_transform():
    # A matrix exposing transform_point must shift every control point; the
    # transformed corner geometry differs from the untransformed parse.
    s = _free_patch_shading(PDShadingType6, 12)

    class _Shift:
        def transform_point(self, x, y):
            return (x + 1000.0, y + 2000.0)

    plain = s.collect_patches(None, None, 12)[0]
    shifted = s.collect_patches(None, _Shift(), 12)[0]
    pcp = plain.control_points[0][0]
    scp = shifted.control_points[0][0]
    assert abs(scp[0] - (pcp[0] + 1000.0)) < 1e-6
    assert abs(scp[1] - (pcp[1] + 2000.0)) < 1e-6


def test_patch_meshes_context_wires_to_real_type6_shading():
    from pypdfbox.pdmodel.graphics.shading.patch_meshes_shading_context import (
        PatchMeshesShadingContext,
    )

    s = _free_patch_shading(PDShadingType6, 12)
    ctx = PatchMeshesShadingContext(s, None, None, None, (0, 0, 100, 100), 12)
    assert ctx.is_data_empty() is False
    filled = any(
        ctx.get_value_from_array(x, y) >= 0
        for x in range(0, 101, 20)
        for y in range(0, 101, 20)
    )
    assert filled is True
