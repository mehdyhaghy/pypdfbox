"""Per-vertex byte alignment in the Type 4 / 5 mesh-stream decoder.

PDF 32000-1 §8.7.4.5.5 / §8.7.4.5.6: each vertex's coordinate + colour data
occupies a whole number of bytes; any trailing partial bits are padding that
shall be ignored. Apache PDFBox enforces this in
``PDTriangleBasedShadingType.readVertex`` (getBitOffset → readBits(8-offset)).

When ``BitsPerCoordinate`` / ``BitsPerComponent`` / ``BitsPerFlag`` are chosen
so a vertex does not fill a whole number of bytes, a decoder that omits the
padding desyncs after the first vertex and corrupts the entire mesh. These
hand-written tests pin the alignment without needing the live Java oracle, by
hand-packing a deterministic non-byte-aligned mesh and asserting the decoded
points / colours land back on the encoded values.

Patch meshes (Types 6/7) are deliberately *not* aligned per control point
(upstream ``PDMeshBasedShadingType.readPatch`` has no getBitOffset call), so a
companion test confirms the patch decoder leaves the cross-patch bit cursor
untouched.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.shading.pd_mesh_based_shading_type import (
    _PatchBitReader,
    parse_patch_stream,
)
from pypdfbox.pdmodel.graphics.shading.pd_shading_type4 import PDShadingType4
from pypdfbox.pdmodel.graphics.shading.pd_shading_type5 import PDShadingType5

_BC = 12
_BCOMP = 12
_BF = 8


class _BitWriter:
    def __init__(self) -> None:
        self._bits: list[int] = []

    def write(self, value: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def align(self) -> None:
        while len(self._bits) % 8 != 0:
            self._bits.append(0)

    def to_bytes(self) -> bytes:
        self.align()
        out = bytearray()
        for i in range(0, len(self._bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | self._bits[i + j]
            out.append(byte)
        return bytes(out)


def _q(value: float, lo: float, hi: float, bits: int) -> int:
    src_max = (1 << bits) - 1
    return max(0, min(src_max, round((value - lo) / (hi - lo) * src_max)))


def _decode() -> COSArray:
    arr = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        arr.add(COSFloat(v))
    return arr


_CORNERS = [
    (0.0, 0.0, 1.0, 0.0, 0.0),
    (100.0, 0.0, 0.0, 1.0, 0.0),
    (0.0, 100.0, 0.0, 0.0, 1.0),
    (100.0, 100.0, 1.0, 1.0, 1.0),
]


def _approx(decoded: tuple[float, float], expected: tuple[float, float]) -> None:
    assert decoded[0] == pytest.approx(expected[0], abs=0.05)
    assert decoded[1] == pytest.approx(expected[1], abs=0.05)


def test_vertex_layout_is_non_byte_aligned() -> None:
    # type4 vertex: flag + 2 coords + 3 components, none a byte multiple.
    assert (_BF + 2 * _BC + 3 * _BCOMP) % 8 != 0
    # type5 vertex: 2 coords + 3 components.
    assert (2 * _BC + 3 * _BCOMP) % 8 != 0


def test_type4_unaligned_decode_round_trips() -> None:
    sh = PDShadingType4()
    cos: COSStream = sh.get_cos_object()
    cos.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    cos.set_int(COSName.get_pdf_name("BitsPerCoordinate"), _BC)
    cos.set_int(COSName.get_pdf_name("BitsPerComponent"), _BCOMP)
    cos.set_int(COSName.get_pdf_name("BitsPerFlag"), _BF)
    cos.set_item(COSName.get_pdf_name("Decode"), _decode())

    bw = _BitWriter()

    def vtx(flag: int, x: float, y: float, r: float, g: float, b: float) -> None:
        bw.write(flag, _BF)
        bw.write(_q(x, 0, 100, _BC), _BC)
        bw.write(_q(y, 0, 100, _BC), _BC)
        bw.write(_q(r, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(g, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(b, 0, 1, _BCOMP), _BCOMP)
        bw.align()

    vtx(0, *_CORNERS[0])
    vtx(0, *_CORNERS[1])
    vtx(0, *_CORNERS[2])
    vtx(0, *_CORNERS[1])
    vtx(0, *_CORNERS[2])
    vtx(0, *_CORNERS[3])
    cos.set_raw_data(bw.to_bytes())

    triangles = sh.collect_triangles()
    assert len(triangles) == 2
    (p0, p1, p2), (c0, c1, c2) = triangles[0]
    _approx(p0, (0.0, 0.0))
    _approx(p1, (100.0, 0.0))
    _approx(p2, (0.0, 100.0))
    assert c0[0] == pytest.approx(1.0, abs=0.01)  # red
    assert c1[1] == pytest.approx(1.0, abs=0.01)  # green
    assert c2[2] == pytest.approx(1.0, abs=0.01)  # blue
    # Second triangle's last corner is white.
    (_a, _b, p2b), (_ca, _cb, c2b) = triangles[1]
    _approx(p2b, (100.0, 100.0))
    assert all(v == pytest.approx(1.0, abs=0.01) for v in c2b)


def test_type5_unaligned_decode_round_trips() -> None:
    sh = PDShadingType5()
    cos: COSStream = sh.get_cos_object()
    cos.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    cos.set_int(COSName.get_pdf_name("BitsPerCoordinate"), _BC)
    cos.set_int(COSName.get_pdf_name("BitsPerComponent"), _BCOMP)
    cos.set_int(COSName.get_pdf_name("VerticesPerRow"), 2)
    cos.set_item(COSName.get_pdf_name("Decode"), _decode())

    bw = _BitWriter()

    def vtx(x: float, y: float, r: float, g: float, b: float) -> None:
        bw.write(_q(x, 0, 100, _BC), _BC)
        bw.write(_q(y, 0, 100, _BC), _BC)
        bw.write(_q(r, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(g, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(b, 0, 1, _BCOMP), _BCOMP)
        bw.align()

    for x, y, r, g, b in _CORNERS:
        vtx(x, y, r, g, b)
    cos.set_raw_data(bw.to_bytes())

    triangles = sh.collect_triangles()
    # 2x2 lattice -> one cell -> two triangles.
    assert len(triangles) == 2
    # All four corners must appear across the two triangles at their encoded
    # positions; check the lattice corners are reproduced exactly.
    all_points = {
        (round(x), round(y))
        for pts, _ in triangles
        for (x, y) in pts
    }
    assert (0, 0) in all_points
    assert (100, 0) in all_points
    assert (0, 100) in all_points
    assert (100, 100) in all_points


def test_align_to_byte_skips_partial_bits() -> None:
    reader = _PatchBitReader(bytes([0b10110000, 0b11110000]))
    assert reader.read_bits(4) == 0b1011
    assert reader.get_bit_offset() == 4
    reader.align_to_byte()
    assert reader.get_bit_offset() == 0
    # Next read starts at the second byte.
    assert reader.read_bits(4) == 0b1111


def test_align_to_byte_noop_on_boundary() -> None:
    reader = _PatchBitReader(bytes([0xAB, 0xCD]))
    assert reader.read_bits(8) == 0xAB
    assert reader.get_bit_offset() == 0
    reader.align_to_byte()  # already aligned -> no byte skipped
    assert reader.read_bits(8) == 0xCD


def test_patch_stream_does_not_byte_align_between_control_points() -> None:
    """Patch control points (Types 6/7) are NOT padded per point — only the
    leading flag + 12/16 coord pairs + corner colours, read contiguously.
    A single 12-bit-coord Coons patch packs into a contiguous bit run; if the
    patch decoder spuriously aligned per control point it would desync."""
    bw = _BitWriter()
    coons = [
        (0, 0), (33, 0), (66, 0), (100, 0),
        (100, 33), (100, 66), (100, 100),
        (66, 100), (33, 100), (0, 100), (0, 66), (0, 33),
    ]
    corner_colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]
    bw.write(0, _BF)  # flag, no alignment
    for x, y in coons:
        bw.write(_q(x, 0, 100, _BC), _BC)
        bw.write(_q(y, 0, 100, _BC), _BC)
    for r, g, b in corner_colors:
        bw.write(_q(r, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(g, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(b, 0, 1, _BCOMP), _BCOMP)

    patches = parse_patch_stream(
        bw.to_bytes(),
        bits_per_coordinate=_BC,
        bits_per_component=_BCOMP,
        bits_per_flag=_BF,
        decode=[0, 100, 0, 100, 0, 1, 0, 1, 0, 1],
        num_color_components=3,
        control_points=12,
    )
    assert len(patches) == 1
    patch = patches[0]
    assert len(patch.points) == 12
    # First and fourth control points are the bottom-edge endpoints.
    assert patch.points[0][0] == pytest.approx(0.0, abs=0.05)
    assert patch.points[3][0] == pytest.approx(100.0, abs=0.05)
    # The seventh point (index 6) is the top-right corner (100, 100).
    assert patch.points[6][0] == pytest.approx(100.0, abs=0.05)
    assert patch.points[6][1] == pytest.approx(100.0, abs=0.05)
    # Corner colours decode to the encoded RGB.
    assert patch.colors[0][0] == pytest.approx(1.0, abs=0.01)
    assert patch.colors[3] == pytest.approx([1.0, 1.0, 1.0], abs=0.01)
