from pypdfbox.jbig2.jbig2_globals import JBIG2Globals


def test_empty_globals_returns_none():
    globals_ = JBIG2Globals()
    assert globals_.get_segment(0) is None
    assert globals_.get_segment(42) is None


def test_add_and_get_segment():
    globals_ = JBIG2Globals()
    # SegmentHeader is ported later; any object stands in as the value
    sentinel = object()
    globals_.add_segment(7, sentinel)
    assert globals_.get_segment(7) is sentinel


def test_add_segment_overwrites_existing():
    globals_ = JBIG2Globals()
    first = object()
    second = object()
    globals_.add_segment(3, first)
    globals_.add_segment(3, second)
    assert globals_.get_segment(3) is second


def test_multiple_segments_keyed_by_number():
    globals_ = JBIG2Globals()
    seg_a = object()
    seg_b = object()
    globals_.add_segment(1, seg_a)
    globals_.add_segment(2, seg_b)
    assert globals_.get_segment(1) is seg_a
    assert globals_.get_segment(2) is seg_b
    assert globals_.get_segment(3) is None
