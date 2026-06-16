"""Fuzz/parity sweep for page-tree attribute inheritance (wave 1568).

Hammers the inheritable page-attribute resolution that both
:class:`~pypdfbox.pdmodel.pd_page.PDPage` and
:class:`~pypdfbox.pdmodel.pd_page_tree.PDPageTree` implement, pinning the
upstream Apache PDFBox 3.0.7 behaviour:

* ``/MediaBox``, ``/Resources``, ``/Rotate`` and ``/CropBox`` walk the
  ``/Parent`` (with the ``/P`` legacy fallback) chain, ascending only through
  intermediate ``/Pages`` nodes (``PDPageTree.getInheritableAttribute`` —
  ``parent != null && COSName.PAGES.equals(parent.getCOSName(COSName.TYPE))``).
* ``/Rotate`` is gated on ``angle % 90 == 0`` and then normalised with
  ``(angle % 360 + 360) % 360`` so negatives wrap and off-axis values report
  ``0`` (``PDPage.getRotation``).
* ``/CropBox`` (inheritable) defaults to the resolved ``/MediaBox`` when absent
  and is otherwise clipped to the media box bounds (``PDPage.getCropBox`` →
  ``clipToMediaBox``); ``/MediaBox`` defaults to U.S. Letter (612x792) when
  absent at every level.
* index descent (``PDPageTree.get(int)``) trusts each node's ``/Count`` while
  iteration walks the actual ``/Kids``, so an unbalanced tree still yields
  document order; cyclic ``/Parent`` chains are guarded against infinite loops.

No upstream divergence was found while writing these (the inheritance code is a
faithful port); this file is a regression net for the surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")
_PAGES = COSName.get_pdf_name("Pages")
_KIDS = COSName.get_pdf_name("Kids")
_COUNT = COSName.get_pdf_name("Count")
_PARENT = COSName.get_pdf_name("Parent")
_P = COSName.get_pdf_name("P")
_MEDIA_BOX = COSName.get_pdf_name("MediaBox")
_CROP_BOX = COSName.get_pdf_name("CropBox")
_RESOURCES = COSName.get_pdf_name("Resources")
_ROTATE = COSName.get_pdf_name("Rotate")
_FONT = COSName.get_pdf_name("Font")


# ---------- builders ----------


def _box(x0: float, y0: float, x1: float, y1: float) -> COSArray:
    arr = COSArray()
    for v in (x0, y0, x1, y1):
        arr.add(COSFloat(float(v)) if isinstance(v, float) else COSInteger.get(int(v)))
    return arr


def _page_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _PAGE)
    return d


def _pages_dict(*kids: COSDictionary, count: int | None = None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _PAGES)
    arr = COSArray()
    for kid in kids:
        arr.add(kid)
        kid.set_item(_PARENT, d)
    d.set_item(_KIDS, arr)
    d.set_int(_COUNT, count if count is not None else len(kids))
    return d


def _rect_tuple(r: PDRectangle) -> tuple[float, float, float, float]:
    return (r.lower_left_x, r.lower_left_y, r.upper_right_x, r.upper_right_y)


# ---------- /MediaBox inheritance ----------


def test_media_box_from_immediate_parent():
    root = _pages_dict()
    root.set_item(_MEDIA_BOX, _box(0, 0, 200, 300))
    leaf = _page_dict()
    leaf.set_item(_PARENT, root)
    root.get_dictionary_object(_KIDS).add(leaf)
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 200.0, 300.0)


def test_media_box_from_grandparent_three_levels():
    root = _pages_dict()
    root.set_item(_MEDIA_BOX, _box(0, 0, 200, 300))
    leaf = _page_dict()
    mid = _pages_dict(leaf)
    mid.set_item(_PARENT, root)
    root.get_dictionary_object(_KIDS).add(mid)
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 200.0, 300.0)


def test_media_box_deep_nesting_four_levels():
    leaf = _page_dict()
    n1 = _pages_dict(leaf)
    n2 = _pages_dict(n1)
    root = _pages_dict(n2)
    root.set_item(_MEDIA_BOX, _box(10, 20, 110, 220))
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (10.0, 20.0, 110.0, 220.0)


def test_media_box_leaf_override_wins():
    root = _pages_dict()
    root.set_item(_MEDIA_BOX, _box(0, 0, 999, 999))
    leaf = _page_dict()
    leaf.set_item(_PARENT, root)
    leaf.set_item(_MEDIA_BOX, _box(0, 0, 50, 50))
    root.get_dictionary_object(_KIDS).add(leaf)
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 50.0, 50.0)


def test_media_box_default_us_letter_when_absent_everywhere():
    leaf = _page_dict()
    _pages_dict(leaf)  # wire /Parent chain
    # neither level declares /MediaBox -> U.S. Letter.
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 612.0, 792.0)


def test_media_box_not_inherited_through_non_pages_parent():
    # Parent is /Type /Page (not /Pages): upstream stops the ascent.
    weird_parent = _page_dict()
    weird_parent.set_item(_MEDIA_BOX, _box(0, 0, 200, 200))
    leaf = _page_dict()
    leaf.set_item(_PARENT, weird_parent)
    # Falls back to default since ascent halts at the non-/Pages parent.
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 612.0, 792.0)


def test_media_box_inherited_via_p_legacy_alias():
    root = _pages_dict()
    root.set_item(_MEDIA_BOX, _box(0, 0, 144, 144))
    leaf = _page_dict()
    # No /Parent, only the legacy single-letter /P.
    leaf.set_item(_P, root)
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 144.0, 144.0)


# ---------- /Rotate inheritance + normalisation ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),
        (90, 90),
        (180, 180),
        (270, 270),
        (360, 0),
        (450, 90),
        (-90, 270),
        (-180, 180),
        (-270, 90),
        (-360, 0),
        (720, 0),
        (810, 90),
    ],
    ids=[
        "0",
        "90",
        "180",
        "270",
        "360",
        "450",
        "neg90",
        "neg180",
        "neg270",
        "neg360",
        "720",
        "810",
    ],
)
def test_rotation_normalised_mod_360(raw, expected):
    leaf = _page_dict()
    leaf.set_item(_ROTATE, COSInteger.get(raw))
    assert PDPage(leaf).get_rotation() == expected


@pytest.mark.parametrize(
    "off_axis",
    [45, 1, 89, 91, 135, -45, 271],
    ids=["45", "1", "89", "91", "135", "neg45", "271"],
)
def test_rotation_off_axis_reports_zero(off_axis):
    leaf = _page_dict()
    leaf.set_item(_ROTATE, COSInteger.get(off_axis))
    assert PDPage(leaf).get_rotation() == 0


def test_rotation_float_multiple_of_90_truncates():
    leaf = _page_dict()
    # intValue() truncates toward zero: 90.7 -> 90 (a multiple of 90).
    leaf.set_item(_ROTATE, COSFloat(90.7))
    assert PDPage(leaf).get_rotation() == 90


def test_rotation_float_off_axis_after_truncation_is_zero():
    leaf = _page_dict()
    # 89.9 -> 89 -> not a multiple of 90 -> 0.
    leaf.set_item(_ROTATE, COSFloat(89.9))
    assert PDPage(leaf).get_rotation() == 0


def test_rotation_inherited_from_grandparent():
    leaf = _page_dict()
    mid = _pages_dict(leaf)
    root = _pages_dict(mid)
    root.set_item(_ROTATE, COSInteger.get(-90))
    assert PDPage(leaf).get_rotation() == 270


def test_rotation_leaf_overrides_inherited():
    leaf = _page_dict()
    root = _pages_dict(leaf)
    root.set_item(_ROTATE, COSInteger.get(180))
    leaf.set_item(_ROTATE, COSInteger.get(90))
    assert PDPage(leaf).get_rotation() == 90


def test_rotation_default_zero_when_absent():
    leaf = _page_dict()
    _pages_dict(leaf)  # wire /Parent chain
    assert PDPage(leaf).get_rotation() == 0


def test_is_rotated_predicate_tracks_normalised_value():
    leaf = _page_dict()
    leaf.set_item(_ROTATE, COSInteger.get(-360))  # normalises to 0
    page = PDPage(leaf)
    assert not page.is_rotated()
    leaf.set_item(_ROTATE, COSInteger.get(-90))  # normalises to 270
    assert PDPage(leaf).is_rotated()


# ---------- /Resources inheritance ----------


def test_resources_inherited_from_parent():
    res = COSDictionary()
    res.set_item(_FONT, COSDictionary())
    root = _pages_dict()
    root.set_item(_RESOURCES, res)
    leaf = _page_dict()
    leaf.set_item(_PARENT, root)
    root.get_dictionary_object(_KIDS).add(leaf)
    resolved = PDPage(leaf).get_resources()
    assert resolved is not None
    assert resolved.get_cos_object() is res


def test_resources_inherited_from_grandparent():
    res = COSDictionary()
    leaf = _page_dict()
    mid = _pages_dict(leaf)
    root = _pages_dict(mid)
    root.set_item(_RESOURCES, res)
    resolved = PDPage(leaf).get_resources()
    assert resolved is not None
    assert resolved.get_cos_object() is res


def test_resources_absent_returns_none():
    leaf = _page_dict()
    _pages_dict(leaf)  # wire /Parent chain
    assert PDPage(leaf).get_resources() is None


def test_resources_leaf_override_wins():
    parent_res = COSDictionary()
    leaf_res = COSDictionary()
    root = _pages_dict()
    root.set_item(_RESOURCES, parent_res)
    leaf = _page_dict()
    leaf.set_item(_PARENT, root)
    leaf.set_item(_RESOURCES, leaf_res)
    root.get_dictionary_object(_KIDS).add(leaf)
    assert PDPage(leaf).get_resources().get_cos_object() is leaf_res


# ---------- /CropBox defaulting + clipping ----------


def test_crop_box_defaults_to_media_box_when_absent():
    leaf = _page_dict()
    leaf.set_item(_MEDIA_BOX, _box(0, 0, 100, 200))
    page = PDPage(leaf)
    assert _rect_tuple(page.get_crop_box()) == (0.0, 0.0, 100.0, 200.0)


def test_crop_box_clipped_to_media_box():
    leaf = _page_dict()
    leaf.set_item(_MEDIA_BOX, _box(0, 0, 100, 100))
    leaf.set_item(_CROP_BOX, _box(-50, -50, 200, 200))
    assert _rect_tuple(PDPage(leaf).get_crop_box()) == (0.0, 0.0, 100.0, 100.0)


def test_crop_box_within_media_box_unchanged():
    leaf = _page_dict()
    leaf.set_item(_MEDIA_BOX, _box(0, 0, 100, 100))
    leaf.set_item(_CROP_BOX, _box(10, 10, 90, 90))
    assert _rect_tuple(PDPage(leaf).get_crop_box()) == (10.0, 10.0, 90.0, 90.0)


def test_crop_box_inherited_and_clipped():
    root = _pages_dict()
    root.set_item(_MEDIA_BOX, _box(0, 0, 100, 100))
    root.set_item(_CROP_BOX, _box(-10, -10, 110, 110))
    leaf = _page_dict()
    leaf.set_item(_PARENT, root)
    root.get_dictionary_object(_KIDS).add(leaf)
    # CropBox inherited from /Pages parent, then clipped to the (also
    # inherited) media box.
    assert _rect_tuple(PDPage(leaf).get_crop_box()) == (0.0, 0.0, 100.0, 100.0)


def test_crop_box_default_us_letter_when_no_boxes_at_all():
    leaf = _page_dict()
    _pages_dict(leaf)  # wire /Parent chain
    # No MediaBox, no CropBox -> crop defaults to media -> Letter.
    assert _rect_tuple(PDPage(leaf).get_crop_box()) == (0.0, 0.0, 612.0, 792.0)


def test_bleed_trim_art_default_to_crop_box():
    leaf = _page_dict()
    leaf.set_item(_MEDIA_BOX, _box(0, 0, 100, 100))
    leaf.set_item(_CROP_BOX, _box(5, 5, 95, 95))
    page = PDPage(leaf)
    crop = _rect_tuple(page.get_crop_box())
    assert _rect_tuple(page.get_bleed_box()) == crop
    assert _rect_tuple(page.get_trim_box()) == crop
    assert _rect_tuple(page.get_art_box()) == crop


# ---------- static get_inheritable_attribute parity ----------


def test_static_inheritable_reaches_grandparent():
    leaf = _page_dict()
    mid = _pages_dict(leaf)
    root = _pages_dict(mid)
    root.set_item(_MEDIA_BOX, _box(0, 0, 42, 42))
    found = PDPageTree.get_inheritable_attribute(leaf, _MEDIA_BOX)
    assert isinstance(found, COSArray)


def test_static_inheritable_returns_none_when_absent():
    leaf = _page_dict()
    _pages_dict(leaf)
    assert PDPageTree.get_inheritable_attribute(leaf, _ROTATE) is None


def test_static_inheritable_stops_at_non_pages_parent():
    weird = _page_dict()  # /Type /Page, not /Pages
    weird.set_item(_ROTATE, COSInteger.get(90))
    leaf = _page_dict()
    leaf.set_item(_PARENT, weird)
    # Ascent halts because the parent is not a /Pages node.
    assert PDPageTree.get_inheritable_attribute(leaf, _ROTATE) is None


# ---------- cycle guards ----------


def test_cyclic_parent_chain_terminates_media_box():
    leaf = _page_dict()
    mid = COSDictionary()
    mid.set_item(_TYPE, _PAGES)
    leaf.set_item(_PARENT, mid)
    mid.set_item(_PARENT, leaf)  # cycle
    # Must not hang; falls back to default.
    assert _rect_tuple(PDPage(leaf).get_media_box()) == (0.0, 0.0, 612.0, 792.0)


def test_cyclic_parent_chain_terminates_static_lookup():
    a = COSDictionary()
    a.set_item(_TYPE, _PAGES)
    b = COSDictionary()
    b.set_item(_TYPE, _PAGES)
    a.set_item(_PARENT, b)
    b.set_item(_PARENT, a)
    assert PDPageTree.get_inheritable_attribute(a, _ROTATE) is None


def test_self_referential_parent_terminates():
    leaf = _page_dict()
    leaf.set_item(_PARENT, leaf)
    assert PDPage(leaf).get_rotation() == 0


# ---------- index traversal across unbalanced tree ----------


def _unbalanced_tree() -> tuple[PDPageTree, list[COSDictionary]]:
    a, b, c, d = (_page_dict() for _ in range(4))
    mid = _pages_dict(b, c)
    root = _pages_dict(a, mid, d, count=4)
    return PDPageTree(root), [a, b, c, d]


def test_unbalanced_tree_iteration_order():
    tree, order = _unbalanced_tree()
    walked = [p.get_cos_object() for p in tree]
    assert walked == order


def test_unbalanced_tree_index_access():
    tree, order = _unbalanced_tree()
    for i, expected in enumerate(order):
        assert tree[i].get_cos_object() is expected


def test_unbalanced_tree_negative_index():
    tree, order = _unbalanced_tree()
    assert tree[-1].get_cos_object() is order[-1]
    assert tree[-4].get_cos_object() is order[0]


def test_unbalanced_tree_len_matches_walk():
    tree, order = _unbalanced_tree()
    assert len(tree) == len(order)


def test_kids_count_mismatch_undercount_len_reflects_walk():
    a, b = _page_dict(), _page_dict()
    root = _pages_dict(a, b, count=1)  # lies: says 1, has 2
    tree = PDPageTree(root)
    # __len__ validates against the walk and reports the real count.
    assert len(tree) == 2
    # get_count() reports the raw (lying) stored value.
    assert tree.get_count() == 1


def test_kids_count_mismatch_overcount_get_raises():
    a, b = _page_dict(), _page_dict()
    root = _pages_dict(a, b, count=5)  # lies: says 5, has 2
    tree = PDPageTree(root)
    assert tree[0].get_cos_object() is a
    assert tree[1].get_cos_object() is b
    with pytest.raises(RuntimeError):
        tree[2]


def test_get_out_of_range_raises_index_error():
    a = _page_dict()
    tree = PDPageTree(_pages_dict(a))
    with pytest.raises(IndexError):
        tree[5]
