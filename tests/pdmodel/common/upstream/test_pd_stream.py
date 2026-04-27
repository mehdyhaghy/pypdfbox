from __future__ import annotations

# Apache PDFBox 3.0.x ships no focused JUnit class for ``PDStream`` —
# upstream coverage is exercised indirectly through ``PDImageXObjectTest``
# and the parser/writer round-trip suites, both of which depend on image
# codecs / rendering subsystems outside the pdmodel cluster. This module
# is intentionally empty; PDStream is covered by the hand-written
# ``test_pd_stream.py`` and ``test_pd_stream_parity.py`` next door.


def test_no_upstream_pd_stream_test_exists_placeholder() -> None:
    """Placeholder so pytest discovers this module as a real test file
    (and so future re-syncs from upstream see a hook to plug into when /
    if a focused PDStreamTest is added upstream)."""
    assert True
