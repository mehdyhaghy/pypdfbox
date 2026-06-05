"""Pure-Python decode pins for ``PDShadingType4.collect_triangles`` —
the free-form Gouraud triangle-mesh stream decoder (PDF 32000-1
§8.7.4.5.5).

The live-oracle module ``tests/rendering/oracle/test_mesh_gouraud_flag_oracle.py``
already proves the *rendered* strip matches PDFBox 3.0.7 per RGB channel, but
that test is gated behind ``@requires_oracle`` (skipped without a live Java
PDFBox) and only checks painted pixels. This module pins the *decoded geometry
and colours* deterministically, with no oracle dependency, so the flag-0 /
flag-1 / flag-2 vertex-stitching, the ``/Decode`` interpolation, the EOF
termination, and every empty/error fallback branch stay observable on any host.

The vertex packing mirrors the oracle fixture exactly: each vertex is the six
bytes ``[flag, qx, qy, qr, qg, qb]`` where ``q`` quantises a value from its
``/Decode`` range into ``[0, 255]`` (8 BitsPerFlag / BitsPerCoordinate /
BitsPerComponent). ``/Decode`` is x,y in ``[0, 100]`` and three DeviceRGB
components in ``[0, 1]``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.shading import PDShadingType4


def _q(value: float, lo: float, hi: float, src_max: int = 255) -> int:
    if hi == lo:
        return 0
    raw = round((value - lo) / (hi - lo) * src_max)
    return max(0, min(src_max, raw))


def _vtx(flag: int, x: float, y: float, r: float, g: float, b: float) -> bytes:
    return bytes(
        [flag, _q(x, 0, 100), _q(y, 0, 100), _q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)]
    )


def _rgb_stream(decode_vals=(0, 100, 0, 100, 0, 1, 0, 1, 0, 1)) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 4)
    sh.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    arr = COSArray()
    for v in decode_vals:
        arr.add(COSFloat(float(v)))
    sh.set_item(COSName.get_pdf_name("Decode"), arr)
    return sh


# ---------------------------------------------------------------- happy path


def test_flag_strip_decodes_three_triangles_with_exact_geometry() -> None:
    """A flag-0 seed triangle followed by a flag-2 and a flag-1 continuation
    vertex (the strip the oracle fixture builds) decodes to three triangles
    that tile the unit square via shared edges. Pins both the stitched corner
    order and the per-vertex decoded colours."""
    sh = _rgb_stream()
    data = (
        _vtx(0, 0, 0, 1, 0, 0)  # red
        + _vtx(0, 100, 0, 0, 1, 0)  # green
        + _vtx(0, 0, 100, 0, 0, 1)  # blue
        + _vtx(2, 100, 100, 1, 1, 0)  # yellow (re-uses va=red, vc=blue)
        + _vtx(1, 100, 0, 0, 1, 0)  # green (re-uses last edge vb=blue, vc=yellow)
    )
    sh.set_raw_data(data)

    tris = PDShadingType4(sh).collect_triangles()
    assert len(tris) == 3

    # Triangle 1 (flag 0): (0,0)R (100,0)G (0,100)B.
    pts0, cols0 = tris[0]
    assert pts0 == ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    assert cols0 == ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])

    # Triangle 2 (flag 2): re-use (va=(0,0)R, vc=(0,100)B) + new (100,100)Y.
    pts1, cols1 = tris[1]
    assert pts1 == ((0.0, 0.0), (0.0, 100.0), (100.0, 100.0))
    assert cols1 == ([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [1.0, 1.0, 0.0])

    # Triangle 3 (flag 1): re-use last edge (vb=(0,100)B, vc=(100,100)Y) + green.
    pts2, cols2 = tris[2]
    assert pts2 == ((0.0, 100.0), (100.0, 100.0), (100.0, 0.0))
    assert cols2 == ([0.0, 0.0, 1.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0])


def test_single_flag0_triangle() -> None:
    sh = _rgb_stream()
    sh.set_raw_data(
        _vtx(0, 0, 0, 1, 0, 0) + _vtx(0, 100, 0, 0, 1, 0) + _vtx(0, 0, 100, 0, 0, 1)
    )
    tris = PDShadingType4(sh).collect_triangles()
    assert len(tris) == 1
    pts, cols = tris[0]
    assert pts == ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    assert cols == ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])


def test_two_independent_flag0_triangles() -> None:
    """Two consecutive flag-0 seed triangles produce two independent
    triangles (no edge sharing between them). The second triangle's corners
    are exactly the three vertices that follow the first three."""
    sh = _rgb_stream()
    sh.set_raw_data(
        _vtx(0, 0, 0, 1, 0, 0)
        + _vtx(0, 100, 0, 0, 1, 0)
        + _vtx(0, 0, 100, 0, 0, 1)
        + _vtx(0, 100, 100, 1, 1, 1)
        + _vtx(0, 0, 0, 0, 0, 0)
        + _vtx(0, 100, 100, 1, 0, 1)
    )
    tris = PDShadingType4(sh).collect_triangles()
    assert len(tris) == 2
    # First triangle is the flag-0 seed; second is wholly independent of it.
    assert tris[0][0] == ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    assert tris[1][0] == ((100.0, 100.0), (0.0, 0.0), (100.0, 100.0))
    assert tris[1][1] == ([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], [1.0, 0.0, 1.0])


# ---------------------------------------------------------------- termination


def test_unknown_flag_after_triangle_terminates_stream() -> None:
    """A flag whose low two bits are 3 (neither 0/1/2) ends decoding —
    upstream's ``else { break; }`` arm. The one preceding flag-0 triangle is
    retained; the flag-3 vertex and anything after it is dropped."""
    sh = _rgb_stream()
    sh.set_raw_data(
        _vtx(0, 0, 0, 0, 0, 0)
        + _vtx(0, 100, 0, 0, 0, 0)
        + _vtx(0, 0, 100, 0, 0, 0)
        + _vtx(3, 50, 50, 0, 0, 0)  # flag & 3 == 3 -> break
        + _vtx(0, 0, 0, 0, 0, 0)  # never reached
    )
    tris = PDShadingType4(sh).collect_triangles()
    assert len(tris) == 1


def test_flag1_before_any_triangle_terminates() -> None:
    """A continuation flag (1) with no prior triangle to extend has
    ``va is None``, so the dispatch falls through to the terminating
    ``else`` arm and yields nothing."""
    sh = _rgb_stream()
    sh.set_raw_data(_vtx(1, 0, 0, 0, 0, 0))
    assert PDShadingType4(sh).collect_triangles() == []


def test_flag2_before_any_triangle_terminates() -> None:
    sh = _rgb_stream()
    sh.set_raw_data(_vtx(2, 50, 50, 0, 0, 0))
    assert PDShadingType4(sh).collect_triangles() == []


def test_truncated_trailing_vertex_eof_is_swallowed() -> None:
    """Trailing bytes that cannot form a full vertex raise ``EOFError`` inside
    the read loop, which is caught — the completed triangles are returned and
    the partial tail is silently dropped (upstream stops on stream-exhaustion
    the same way)."""
    sh = _rgb_stream()
    full = (
        _vtx(0, 0, 0, 1, 0, 0) + _vtx(0, 100, 0, 0, 1, 0) + _vtx(0, 0, 100, 0, 0, 1)
    )
    # Append a single stray byte: a new flag-0 vertex begins but the stream
    # runs out before its coordinates/colours are read.
    sh.set_raw_data(full + bytes([0]))
    tris = PDShadingType4(sh).collect_triangles()
    assert len(tris) == 1


# ---------------------------------------------------------------- fallbacks


def test_non_stream_backing_returns_empty() -> None:
    """When the shading dictionary is not a COSStream there is no mesh body to
    decode; upstream returns an empty list."""
    assert PDShadingType4(COSDictionary()).collect_triangles() == []


def test_missing_decode_returns_empty() -> None:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 4)
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0, 0))
    assert PDShadingType4(sh).collect_triangles() == []


def test_degenerate_x_decode_range_returns_empty() -> None:
    """When the x-coordinate ``/Decode`` range collapses (lo == hi) the mesh
    cannot be interpolated, so decoding short-circuits to empty."""
    sh = _rgb_stream(decode_vals=(0, 0, 0, 100, 0, 1, 0, 1, 0, 1))
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0, 0))
    assert PDShadingType4(sh).collect_triangles() == []


def test_degenerate_y_decode_range_returns_empty() -> None:
    sh = _rgb_stream(decode_vals=(0, 100, 50, 50, 0, 1, 0, 1, 0, 1))
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0, 0))
    assert PDShadingType4(sh).collect_triangles() == []


def test_no_color_components_returns_empty() -> None:
    """No ``/Function`` and no resolvable colour space -> the component count is
    ``-1`` (``n <= 0``), so collection returns empty before reading any vertex."""
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 4)
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    arr = COSArray()
    for v in (0, 100, 0, 100, 0, 1):
        arr.add(COSFloat(float(v)))
    sh.set_item(COSName.get_pdf_name("Decode"), arr)
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0, 0))
    shading = PDShadingType4(sh)
    assert shading.get_number_of_color_components() == -1
    assert shading.collect_triangles() == []


def test_missing_color_decode_range_raises_oserror() -> None:
    """``/Decode`` declares x,y but omits the colour-component ranges while the
    colour space still reports 3 components — upstream raises
    ``IOException("Range missing in shading /Decode entry")``; pypdfbox mirrors
    it as ``OSError`` per the project's IOException->OSError convention."""
    sh = _rgb_stream(decode_vals=(0, 100, 0, 100))
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0, 0))
    with pytest.raises(OSError, match="Range missing in shading /Decode entry"):
        PDShadingType4(sh).collect_triangles()


def test_empty_stream_body_returns_empty() -> None:
    sh = _rgb_stream()
    sh.set_raw_data(b"")
    assert PDShadingType4(sh).collect_triangles() == []


def test_zero_bits_per_coordinate_returns_empty() -> None:
    """A non-positive ``/BitsPerCoordinate`` makes the bit layout undecodable;
    upstream's guard returns empty before reading the stream."""
    sh = _rgb_stream()
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 0)
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0, 0))
    assert PDShadingType4(sh).collect_triangles() == []


def test_xform_and_matrix_args_are_accepted_but_ignored() -> None:
    """``xform`` / ``matrix`` exist only for upstream-signature parity; the
    geometric transform is the renderer's job, so passing them changes
    nothing in the decoded output."""
    sh = _rgb_stream()
    sh.set_raw_data(
        _vtx(0, 0, 0, 1, 0, 0) + _vtx(0, 100, 0, 0, 1, 0) + _vtx(0, 0, 100, 0, 0, 1)
    )
    shading = PDShadingType4(sh)
    plain = shading.collect_triangles()
    with_args = shading.collect_triangles(xform=object(), matrix=object())
    assert with_args == plain
