"""Behavioural tests for JBIG2Page composition helpers.

The real ``.jb2`` corpus fixtures all decode through the single-region
"fits page" fast path with a zero default pixel value, an OR combination
operator override and no generic-refinement region, so several normal-page
composition branches are never exercised end-to-end. These tests drive those
branches directly with lightweight region stubs that supply a real
:class:`Bitmap` and :class:`RegionSegmentInformation`, mirroring upstream
``JBIG2Page`` page-79 step 3/5 semantics:

* default pixel value != 0 -> page buffer filled with 0xff before blitting;
* a :class:`GenericRefinementRegion` receives the page bitmap via
  ``set_page_bitmap`` before decoding;
* the combination-operator override decision;
* the get_segment / page-information / clear-page / get_height accessors.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.jbig2_page import JBIG2Page
from pypdfbox.jbig2.segments.generic_refinement_region import GenericRefinementRegion
from pypdfbox.jbig2.segments.region_segment_information import RegionSegmentInformation
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


class _StubPageInformation:
    def __init__(
        self,
        width=8,
        height=8,
        default_pixel=0,
        striped=False,
        override=False,
        operator=CombinationOperator.OR,
    ):
        self._w = width
        self._h = height
        self._defpix = default_pixel
        self._striped = striped
        self._override = override
        self._op = operator

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def get_default_pixel_value(self):
        return self._defpix

    def is_striped(self):
        return self._striped

    def is_combination_operator_override_allowed(self):
        return self._override

    def get_combination_operator(self):
        return self._op

    def get_resolution_x(self):
        return 0

    def get_resolution_y(self):
        return 0


class _StubSegmentHeader:
    def __init__(self, seg_type, data):
        self._type = seg_type
        self._data = data
        self.cleaned = False

    def get_segment_type(self):
        return self._type

    def get_segment_nr(self):
        return 1

    def get_segment_data(self):
        return self._data

    def clean_segment_data(self):
        self.cleaned = True


class _StubRegion:
    """Minimal Region returning a real Bitmap (does not equal page dims)."""

    def __init__(self, bitmap, region_info):
        self._bitmap = bitmap
        self._info = region_info

    def get_region_bitmap(self):
        return self._bitmap

    def get_region_info(self):
        return self._info


def _region_info(width, height, x, y, operator=CombinationOperator.OR):
    info = RegionSegmentInformation()
    info.bitmap_width = width
    info.bitmap_height = height
    info.x_location = x
    info.y_location = y
    info.combination_operator = operator
    return info


def test_get_segment_returns_none_without_document():
    page = JBIG2Page(None, 1)
    assert page.get_segment(42) is None


def test_get_page_information_segment_none_when_absent():
    page = JBIG2Page(None, 1)
    assert page.get_page_information_segment() is None


def test_combination_operator_override_returns_new_operator():
    page = JBIG2Page(None, 1)
    pi = _StubPageInformation(override=True, operator=CombinationOperator.AND)
    assert (
        page._get_combination_operator(pi, CombinationOperator.XOR)
        == CombinationOperator.XOR
    )


def test_combination_operator_without_override_uses_page_operator():
    page = JBIG2Page(None, 1)
    pi = _StubPageInformation(override=False, operator=CombinationOperator.AND)
    assert (
        page._get_combination_operator(pi, CombinationOperator.XOR)
        == CombinationOperator.AND
    )


def test_clear_page_data_resets_bitmap():
    page = JBIG2Page(None, 1)
    page.page_bitmap = Bitmap(4, 4)
    page.clear_page_data()
    assert page.page_bitmap is None


def test_normal_page_fills_for_nonzero_default_pixel():
    # default pixel != 0 -> page buffer pre-filled with 0xff (page-79 step 3).
    page = JBIG2Page(None, 1)
    pi = _StubPageInformation(width=8, height=8, default_pixel=1)
    # A small region (4x4) that does NOT fit the page, so it is blitted in.
    region_bitmap = Bitmap(4, 4)
    region = _StubRegion(region_bitmap, _region_info(4, 4, 0, 0))
    page.segments[1] = _StubSegmentHeader(38, region)  # immediate generic region
    page._create_normal_page(pi)
    # The 0xff fill means the top-left byte carries set bits outside the blit.
    assert any(b != 0 for b in page.page_bitmap.get_byte_array())


def test_normal_page_sets_page_bitmap_on_refinement_region():
    page = JBIG2Page(None, 1)
    pi = _StubPageInformation(width=8, height=8, default_pixel=0)
    region_bitmap = Bitmap(4, 4)

    class _RefRegion(GenericRefinementRegion):
        def __init__(self, bitmap, info):
            self._bitmap = bitmap
            self._info = info
            self.received_page_bitmap = None

        def set_page_bitmap(self, page_bitmap):  # type: ignore[override]
            self.received_page_bitmap = page_bitmap

        def get_region_bitmap(self):  # type: ignore[override]
            return self._bitmap

        def get_region_info(self):  # type: ignore[override]
            return self._info

    region = _RefRegion(region_bitmap, _region_info(4, 4, 0, 0))
    page.segments[1] = _StubSegmentHeader(42, region)  # refinement region type
    page._create_normal_page(pi)
    assert region.received_page_bitmap is not None


def test_get_height_decodes_when_page_height_unknown():
    # get_height with an unknown page height (0xffffffff) forces a get_bitmap()
    # decode; here we stub the page-information to report the sentinel height
    # and pre-seed the composed bitmap so the decode is a no-op.
    page = JBIG2Page(None, 1)
    pi = _StubPageInformation(width=8, height=0xFFFFFFFF)
    page.segments[48] = _StubSegmentHeader(48, pi)
    page.page_bitmap = Bitmap(8, 1)  # already composed -> get_bitmap returns it
    # final_height stays 0 because the sentinel height triggers the decode path.
    assert page.get_height() == 0
