"""Hand-written tests for the JBIG2 Profiles segment (empty upstream stub)."""

from __future__ import annotations

from pypdfbox.jbig2.segment_data import SegmentData
from pypdfbox.jbig2.segments.profiles import Profiles


def test_profiles_is_segment_data():
    assert issubclass(Profiles, SegmentData)


def test_init_is_noop():
    # Upstream Profiles.init() is empty; it must not raise even with no stream.
    profiles = Profiles()
    profiles.init(None, None)
