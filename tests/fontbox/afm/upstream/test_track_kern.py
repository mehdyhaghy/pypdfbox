"""Port of upstream ``TrackKernTest`` from
``fontbox/src/test/java/org/apache/fontbox/afm/TrackKernTest.java``.
"""

from __future__ import annotations

from pypdfbox.fontbox.afm import TrackKern


# Translated from testTrackKern -- constructor + accessor parity.
def test_track_kern() -> None:
    track_kern = TrackKern(0, 1.0, 1.0, 10.0, 10.0)
    assert track_kern.get_degree() == 0
    assert track_kern.get_min_point_size() == 1.0
    assert track_kern.get_min_kern() == 1.0
    assert track_kern.get_max_point_size() == 10.0
    assert track_kern.get_max_kern() == 10.0
