"""Parity tests for ``PDViewportDictionary`` ``getBBox`` / ``setBBox``
aliases and the COSArray-direct overload of ``set_bbox``.

The auto camelCase→snake_case rule splits at every uppercase boundary
producing ``get_b_box``, but PDFBox developers reach for ``get_bbox``
first since "BBox" reads as a single acronym. This module verifies the
canonical ``get_bbox`` / ``set_bbox`` aliases delegate to the same
underlying ``/BBox`` slot as ``get_b_box`` / ``set_b_box`` and that
``set_bbox`` accepts a ``COSArray`` directly (mirroring upstream's
``setItem(BBox, rectangle)`` which round-trips any ``COSObjectable``).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.interactive.measurement import PDViewportDictionary
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_BBOX = COSName.get_pdf_name("BBox")


def test_get_bbox_alias_delegates_to_get_b_box() -> None:
    vp = PDViewportDictionary()
    vp.set_b_box(PDRectangle(1.0, 2.0, 3.0, 4.0))
    rect = vp.get_bbox()
    assert rect is not None
    assert rect.get_lower_left_x() == 1.0
    assert rect.get_upper_right_y() == 4.0


def test_set_bbox_alias_writes_same_slot() -> None:
    vp = PDViewportDictionary()
    vp.set_bbox(PDRectangle(10.0, 20.0, 30.0, 40.0))
    via_canonical = vp.get_b_box()
    via_alias = vp.get_bbox()
    assert via_canonical is not None
    assert via_alias is not None
    # Both spellings read the same /BBox slot — the parsed PDRectangle is
    # a fresh value object, but its corner coordinates round-trip exactly.
    for rect in (via_canonical, via_alias):
        assert rect.get_lower_left_x() == 10.0
        assert rect.get_lower_left_y() == 20.0
        assert rect.get_upper_right_x() == 30.0
        assert rect.get_upper_right_y() == 40.0


def test_set_bbox_alias_reads_back_through_b_box_setter() -> None:
    # Reverse direction: write via the original spelling, read via the
    # upstream-spelled alias.
    vp = PDViewportDictionary()
    vp.set_b_box(PDRectangle(11.0, 22.0, 33.0, 44.0))
    rect = vp.get_bbox()
    assert rect is not None
    assert rect.get_lower_left_x() == 11.0
    assert rect.get_upper_right_x() == 33.0


def test_set_bbox_accepts_cos_array_directly() -> None:
    vp = PDViewportDictionary()
    arr = COSArray()
    arr.add(COSFloat(5.0))
    arr.add(COSFloat(6.0))
    arr.add(COSFloat(7.0))
    arr.add(COSFloat(8.0))

    vp.set_bbox(arr)

    assert vp.get_cos_object().get_dictionary_object(_BBOX) is arr
    rect = vp.get_bbox()
    assert rect is not None
    assert rect.get_lower_left_x() == 5.0
    assert rect.get_upper_right_x() == 7.0


def test_set_bbox_none_clears_entry() -> None:
    vp = PDViewportDictionary()
    vp.set_bbox(PDRectangle(1.0, 2.0, 3.0, 4.0))
    assert vp.get_cos_object().contains_key(_BBOX)
    vp.set_bbox(None)
    assert not vp.get_cos_object().contains_key(_BBOX)
    assert vp.get_bbox() is None


def test_set_b_box_also_accepts_cos_array() -> None:
    # Same edge-case but exercised through the original spelling so the
    # contract is symmetric for back-compat callers.
    vp = PDViewportDictionary()
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(100.0))
    arr.add(COSFloat(200.0))

    vp.set_b_box(arr)

    assert vp.get_cos_object().get_dictionary_object(_BBOX) is arr
