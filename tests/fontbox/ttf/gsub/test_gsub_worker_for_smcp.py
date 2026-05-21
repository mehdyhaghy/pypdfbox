"""Hand-written tests for :class:`GsubWorkerForSMCP`.

Synthetic ``smcp`` (Small Caps) shaping fixtures — pypdfbox cannot
redistribute Calibri (Microsoft Office proprietary) and upstream's
test is itself platform-gated to ``c:/windows/fonts/calibri.ttf`` via
``Assumptions.assumeTrue``. These exercise the same code paths
through synthetic :class:`GsubData` inputs.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_smcp import GsubWorkerForSMCP


class _StubCmap:
    """Minimal :class:`CmapLookup` stub — SMCP worker accepts it but
    never consults it in :meth:`apply_transforms`."""

    def get_glyph_id(self, codepoint: int) -> int:  # noqa: ARG002
        return 0


def test_apply_transforms_no_smcp_feature() -> None:
    """Font has no ``smcp`` feature — input passes through unchanged."""
    gsub_data = GsubData(active_script_name="latn", feature_list={})
    worker = GsubWorkerForSMCP(_StubCmap(), gsub_data)
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_apply_transforms_empty_substitution_map() -> None:
    """``smcp`` supported but no substitutions — pass through."""
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"smcp": {}},
    )
    worker = GsubWorkerForSMCP(_StubCmap(), gsub_data)
    assert worker.apply_transforms([10, 20]) == [10, 20]


def test_apply_transforms_single_glyph_substitution() -> None:
    """A single-glyph ``smcp`` substitution rewrites the GID."""
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"smcp": {(65,): (300,)}},
    )
    worker = GsubWorkerForSMCP(_StubCmap(), gsub_data)
    assert worker.apply_transforms([65, 66, 65]) == [300, 66, 300]


def test_apply_transforms_empty_input() -> None:
    gsub_data = GsubData(
        active_script_name="latn",
        feature_list={"smcp": {(65,): (300,)}},
    )
    worker = GsubWorkerForSMCP(_StubCmap(), gsub_data)
    assert worker.apply_transforms([]) == []
