"""Pure-Python decode pins for ``PDShadingType5.collect_triangles`` — the
lattice-form Gouraud triangle-mesh stream decoder (PDF 32000-1 §8.7.4.5.6).

Type 5 has no per-vertex flag byte: vertices are stored row-major with
``/VerticesPerRow`` columns, and each pair of adjacent rows is stitched into
``2 * (verticesPerRow - 1)`` triangles. This module pins that lattice stitching
and every empty/error fallback without an oracle dependency, complementing the
live render-parity coverage (``tests/rendering/oracle/test_mesh_shading_oracle.py``).

Each vertex is the five bytes ``[qx, qy, qr, qg, qb]`` where ``q`` quantises a
value from its ``/Decode`` range into ``[0, 255]`` (8 BitsPerCoordinate /
BitsPerComponent). ``/Decode`` is x,y in ``[0, 100]`` and three DeviceRGB
components in ``[0, 1]``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.shading import PDShadingType5

# 50 in [0, 100] quantises to round(50/100*255) = 128, which decodes back to
# 128/255*100 == 50.196..., not 50.0 — pin the real round-trip value.
_MID = 128 / 255 * 100


def _q(value: float, lo: float, hi: float, src_max: int = 255) -> int:
    if hi == lo:
        return 0
    raw = round((value - lo) / (hi - lo) * src_max)
    return max(0, min(src_max, raw))


def _vtx(x: float, y: float, r: float, g: float, b: float) -> bytes:
    return bytes([_q(x, 0, 100), _q(y, 0, 100), _q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)])


def _lattice_stream(
    verts_per_row: int,
    data: bytes,
    decode_vals=(0, 100, 0, 100, 0, 1, 0, 1, 0, 1),
    *,
    color_space: bool = True,
    bits_per_coordinate: int = 8,
    bits_per_component: int = 8,
) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 5)
    if color_space:
        sh.set_item(
            COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
        )
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), bits_per_coordinate)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), bits_per_component)
    sh.set_int(COSName.get_pdf_name("VerticesPerRow"), verts_per_row)
    arr = COSArray()
    for v in decode_vals:
        arr.add(COSFloat(float(v)))
    sh.set_item(COSName.get_pdf_name("Decode"), arr)
    sh.set_raw_data(data)
    return sh


# ---------------------------------------------------------------- happy path


def test_two_row_three_column_lattice_decodes_four_triangles() -> None:
    """A 2-row x 3-column lattice yields ``2 * (3 - 1) == 4`` triangles. Each
    2x2 cell ``(v1=top-left, v2=top-right, v3=bottom-left, v4=bottom-right)``
    splits into ``(v1, v2, v3)`` and ``(v2, v3, v4)`` — the same vertex order
    as upstream ``PDShadingType5.createShadedTriangleList``."""
    data = (
        _vtx(0, 0, 1, 0, 0)
        + _vtx(50, 0, 0, 1, 0)
        + _vtx(100, 0, 0, 0, 1)
        + _vtx(0, 100, 1, 1, 0)
        + _vtx(50, 100, 0, 1, 1)
        + _vtx(100, 100, 1, 0, 1)
    )
    tris = PDShadingType5(_lattice_stream(3, data)).collect_triangles()
    assert len(tris) == 4

    # Cell 0 (columns 0..1): v1=(0,0) v2=(50,0) v3=(0,100) v4=(50,100).
    assert tris[0][0] == ((0.0, 0.0), (_MID, 0.0), (0.0, 100.0))
    assert tris[1][0] == ((_MID, 0.0), (0.0, 100.0), (_MID, 100.0))
    # Cell 1 (columns 1..2): v1=(50,0) v2=(100,0) v3=(50,100) v4=(100,100).
    assert tris[2][0] == ((_MID, 0.0), (100.0, 0.0), (_MID, 100.0))
    assert tris[3][0] == ((100.0, 0.0), (_MID, 100.0), (100.0, 100.0))


def test_lattice_carries_per_vertex_colors() -> None:
    """The first triangle of the lattice carries the decoded colours of its
    three corner vertices in lattice order (v1, v2, v3)."""
    data = (
        _vtx(0, 0, 1, 0, 0)
        + _vtx(100, 0, 0, 1, 0)
        + _vtx(0, 100, 0, 0, 1)
        + _vtx(100, 100, 1, 1, 1)
    )
    tris = PDShadingType5(_lattice_stream(2, data)).collect_triangles()
    assert len(tris) == 2
    _pts, cols = tris[0]
    assert cols == ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])


def test_three_rows_two_columns() -> None:
    """A 3-row x 2-column lattice has two cell-rows, each producing two
    triangles -> ``2 * (3 - 1) == 4`` triangles total."""
    data = b"".join(
        _vtx(x, y, 0, 0, 0)
        for y in (0, 50, 100)
        for x in (0, 100)
    )
    tris = PDShadingType5(_lattice_stream(2, data)).collect_triangles()
    assert len(tris) == 4


# ---------------------------------------------------------------- truncation


def test_single_row_yields_no_triangles() -> None:
    """One complete row cannot form a cell (needs two rows), so no triangles
    are produced."""
    data = _vtx(0, 0, 0, 0, 0) + _vtx(100, 0, 0, 0, 0)
    assert PDShadingType5(_lattice_stream(2, data)).collect_triangles() == []


def test_partial_trailing_row_is_discarded() -> None:
    """Two complete rows plus a partial third row: the truncated row raises
    ``EOFError`` mid-read and never reaches ``rows``, so only the two complete
    rows are stitched (2 triangles)."""
    full = (
        _vtx(0, 0, 0, 0, 0)
        + _vtx(100, 0, 0, 0, 0)
        + _vtx(0, 100, 0, 0, 0)
        + _vtx(100, 100, 0, 0, 0)
    )
    data = full + _vtx(0, 50, 0, 0, 0)  # lone vertex of a would-be third row
    tris = PDShadingType5(_lattice_stream(2, data)).collect_triangles()
    assert len(tris) == 2


# ---------------------------------------------------------------- fallbacks


def test_non_stream_backing_returns_empty() -> None:
    assert PDShadingType5(COSDictionary()).collect_triangles() == []


def test_vertices_per_row_below_two_returns_empty() -> None:
    """A lattice needs at least two columns to form a cell; ``/VerticesPerRow``
    of 1 short-circuits to empty."""
    assert PDShadingType5(_lattice_stream(1, _vtx(0, 0, 0, 0, 0))).collect_triangles() == []


def test_degenerate_x_decode_range_returns_empty() -> None:
    sh = _lattice_stream(
        2, _vtx(0, 0, 0, 0, 0), decode_vals=(0, 0, 0, 100, 0, 1, 0, 1, 0, 1)
    )
    assert PDShadingType5(sh).collect_triangles() == []


def test_degenerate_y_decode_range_returns_empty() -> None:
    sh = _lattice_stream(
        2, _vtx(0, 0, 0, 0, 0), decode_vals=(0, 100, 50, 50, 0, 1, 0, 1, 0, 1)
    )
    assert PDShadingType5(sh).collect_triangles() == []


def test_missing_decode_returns_empty() -> None:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 5)
    sh.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_int(COSName.get_pdf_name("VerticesPerRow"), 2)
    sh.set_raw_data(_vtx(0, 0, 0, 0, 0))
    assert PDShadingType5(sh).collect_triangles() == []


def test_no_color_components_returns_empty() -> None:
    """No ``/Function`` and no colour space -> component count is ``-1``
    (``n <= 0``), so collection returns empty before reading vertices."""
    sh = _lattice_stream(
        2, _vtx(0, 0, 0, 0, 0), decode_vals=(0, 100, 0, 100, 0, 1), color_space=False
    )
    shading = PDShadingType5(sh)
    assert shading.get_number_of_color_components() == -1
    assert shading.collect_triangles() == []


def test_missing_color_decode_range_raises_oserror() -> None:
    sh = _lattice_stream(2, _vtx(0, 0, 0, 0, 0), decode_vals=(0, 100, 0, 100))
    with pytest.raises(OSError, match="Range missing in shading /Decode entry"):
        PDShadingType5(sh).collect_triangles()


def test_empty_stream_body_returns_empty() -> None:
    assert PDShadingType5(_lattice_stream(2, b"")).collect_triangles() == []


def test_zero_bits_per_coordinate_returns_empty() -> None:
    sh = _lattice_stream(2, _vtx(0, 0, 0, 0, 0), bits_per_coordinate=0)
    assert PDShadingType5(sh).collect_triangles() == []


def test_xform_and_matrix_args_are_accepted_but_ignored() -> None:
    data = (
        _vtx(0, 0, 1, 0, 0)
        + _vtx(100, 0, 0, 1, 0)
        + _vtx(0, 100, 0, 0, 1)
        + _vtx(100, 100, 1, 1, 1)
    )
    shading = PDShadingType5(_lattice_stream(2, data))
    plain = shading.collect_triangles()
    with_args = shading.collect_triangles(xform=object(), matrix=object())
    assert with_args == plain
