from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.interactive.annotation.pd_ink_list import PDInkList
from pypdfbox.pdmodel.interactive.annotation.pd_line_info import PDLineInfo
from pypdfbox.pdmodel.interactive.annotation.pd_path_info import PDPathInfo
from pypdfbox.pdmodel.interactive.annotation.pd_vertices import PDVertices


# ---------- PDPathInfo ----------


def test_path_info_round_trip() -> None:
    path = PDPathInfo()
    pts = [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)]
    path.set_points(pts)
    assert path.point_count() == 3
    assert path.get_points() == pts
    # Wire format: 6 floats flat.
    assert path.get_cos_array().size() == 6


def test_path_info_wraps_existing_array() -> None:
    arr = COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)])
    path = PDPathInfo(arr)
    assert path.get_cos_array() is arr
    assert path.get_points() == [(1.0, 2.0), (3.0, 4.0)]
    assert path.point_count() == 2


def test_path_info_default_empty() -> None:
    path = PDPathInfo()
    assert path.point_count() == 0
    assert path.get_points() == []


# ---------- PDLineInfo ----------


def test_line_info_round_trip() -> None:
    line = PDLineInfo()
    line.set_start(5.0, 5.0)
    line.set_end(95.0, 95.0)
    assert line.get_start() == (5.0, 5.0)
    assert line.get_end() == (95.0, 95.0)
    assert line.get_cos_array().size() == 4


def test_line_info_wraps_existing_array() -> None:
    arr = COSArray(
        [COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)]
    )
    line = PDLineInfo(arr)
    assert line.get_cos_array() is arr
    assert line.get_start() == (1.0, 2.0)
    assert line.get_end() == (3.0, 4.0)


def test_line_info_default_zero() -> None:
    line = PDLineInfo()
    assert line.get_start() == (0.0, 0.0)
    assert line.get_end() == (0.0, 0.0)


# ---------- PDInkList ----------


def test_ink_list_add_two_paths() -> None:
    ink = PDInkList()
    p1 = PDPathInfo()
    p1.set_points([(0.0, 0.0), (10.0, 10.0)])
    p2 = PDPathInfo()
    p2.set_points([(20.0, 20.0), (30.0, 30.0), (40.0, 40.0)])

    ink.add_path(p1)
    ink.add_path(p2)

    assert ink.path_count() == 2
    paths = ink.get_paths()
    assert len(paths) == 2
    assert all(isinstance(p, PDPathInfo) for p in paths)
    assert paths[0].get_points() == [(0.0, 0.0), (10.0, 10.0)]
    assert paths[1].get_points() == [(20.0, 20.0), (30.0, 30.0), (40.0, 40.0)]


def test_ink_list_remove_path() -> None:
    ink = PDInkList()
    p1 = PDPathInfo()
    p1.set_points([(0.0, 0.0)])
    p2 = PDPathInfo()
    p2.set_points([(1.0, 1.0)])
    ink.add_path(p1)
    ink.add_path(p2)
    ink.remove_path(0)
    assert ink.path_count() == 1
    assert ink.get_paths()[0].get_points() == [(1.0, 1.0)]


def test_ink_list_default_empty() -> None:
    ink = PDInkList()
    assert ink.path_count() == 0
    assert ink.get_paths() == []


def test_ink_list_is_empty_and_len() -> None:
    ink = PDInkList()
    assert ink.is_empty() is True
    assert len(ink) == 0

    p = PDPathInfo()
    p.set_points([(1.0, 2.0)])
    ink.add_path(p)
    assert ink.is_empty() is False
    assert len(ink) == 1


def test_ink_list_clear() -> None:
    ink = PDInkList()
    p1 = PDPathInfo()
    p1.set_points([(0.0, 0.0), (1.0, 1.0)])
    p2 = PDPathInfo()
    p2.set_points([(2.0, 2.0), (3.0, 3.0)])
    ink.add_path(p1)
    ink.add_path(p2)
    assert len(ink) == 2

    underlying = ink.get_cos_array()
    ink.clear()
    assert len(ink) == 0
    assert ink.is_empty() is True
    assert ink.get_paths() == []
    # clear mutates the wrapped COSArray in place — same identity preserved.
    assert ink.get_cos_array() is underlying


def test_ink_list_get_path_returns_wrapper() -> None:
    ink = PDInkList()
    p1 = PDPathInfo()
    p1.set_points([(10.0, 20.0)])
    p2 = PDPathInfo()
    p2.set_points([(30.0, 40.0), (50.0, 60.0)])
    ink.add_path(p1)
    ink.add_path(p2)

    fetched = ink.get_path(1)
    assert isinstance(fetched, PDPathInfo)
    assert fetched.get_points() == [(30.0, 40.0), (50.0, 60.0)]
    # The wrapper aliases the underlying COSArray, not a defensive copy.
    assert fetched.get_cos_array() is p2.get_cos_array()


def test_ink_list_get_path_out_of_range_raises() -> None:
    ink = PDInkList()
    import pytest

    with pytest.raises(IndexError):
        ink.get_path(0)

    p = PDPathInfo()
    p.set_points([(0.0, 0.0)])
    ink.add_path(p)
    with pytest.raises(IndexError):
        ink.get_path(5)


def test_ink_list_iteration_yields_paths() -> None:
    ink = PDInkList()
    p1 = PDPathInfo()
    p1.set_points([(0.0, 0.0)])
    p2 = PDPathInfo()
    p2.set_points([(1.0, 1.0), (2.0, 2.0)])
    ink.add_path(p1)
    ink.add_path(p2)

    collected = list(ink)
    assert len(collected) == 2
    assert all(isinstance(p, PDPathInfo) for p in collected)
    assert collected[0].get_points() == [(0.0, 0.0)]
    assert collected[1].get_points() == [(1.0, 1.0), (2.0, 2.0)]


def test_ink_list_get_cos_object_alias() -> None:
    ink = PDInkList()
    assert ink.get_cos_object() is ink.get_cos_array()


# ---------- PDVertices ----------


def test_vertices_round_trip() -> None:
    v = PDVertices()
    pts = [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)]
    v.set_points(pts)
    assert v.point_count() == 3
    assert v.get_points() == pts
    assert v.get_cos_array().size() == 6


def test_vertices_wraps_existing_array() -> None:
    arr = COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)])
    v = PDVertices(arr)
    assert v.get_cos_array() is arr
    assert v.get_points() == [(1.0, 2.0), (3.0, 4.0)]
    assert v.point_count() == 2


def test_vertices_default_empty() -> None:
    v = PDVertices()
    assert v.point_count() == 0
    assert v.get_points() == []
