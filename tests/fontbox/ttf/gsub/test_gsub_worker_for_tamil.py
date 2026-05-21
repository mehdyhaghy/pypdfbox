"""Hand-written tests for :class:`GsubWorkerForTamil`.

Synthetic Tamil shaping fixtures — pypdfbox cannot redistribute
``Lohit-Tamil.ttf`` (SIL OFL 1.1, not Apache-2.0 interchangeable for
re-licensing) and upstream's own test is itself a placeholder
(``testDummy`` only asserts the factory returns a ``DefaultGsubWorker``
because no Tamil shaper was implemented when the test was written).
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_tamil import GsubWorkerForTamil


class _StubCmap:
    """Synthetic :class:`CmapLookup`: identity-maps Unicode codepoint to GID."""

    def get_glyph_id(self, codepoint: int) -> int:
        # Identity mapping: codepoint == GID for the synthetic tests
        # below. Keeps the reph / before-half / before-reph constants
        # readable (the GID arithmetic in apply_transforms uses the
        # codepoint values directly).
        return codepoint


def _make_gsub_data(features: dict | None = None) -> GsubData:
    return GsubData(
        active_script_name="taml",
        feature_list=features or {},
    )


def test_apply_transforms_no_features_pass_through() -> None:
    """Empty feature list + no reph/before-half glyphs — input unchanged."""
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data())
    glyphs = [0x0BA4, 0x0BAE, 0x0BB0]  # arbitrary Tamil consonants
    assert worker.apply_transforms(glyphs) == glyphs


def test_apply_transforms_empty_input() -> None:
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data())
    assert worker.apply_transforms([]) == []


def test_adjust_reph_position_swaps_ra_virama_past_consonant() -> None:
    """RA+VIRAMA+C → C+RA+VIRAMA (reph moves past the consonant)."""
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data())
    # 0x0BB0=RA, 0x0BCD=VIRAMA, 0x0BAE=MA.
    original = [0x0BB0, 0x0BCD, 0x0BAE]
    adjusted = worker.adjust_reph_position(original)
    assert adjusted == [0x0BAE, 0x0BB0, 0x0BCD]


def test_adjust_reph_position_no_reph_unchanged() -> None:
    """No RA+VIRAMA prefix — list is left alone."""
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data())
    glyphs = [0x0BAE, 0x0BB0, 0x0BCD]
    assert worker.adjust_reph_position(glyphs) == glyphs


def test_reposition_glyphs_before_half_moves_left() -> None:
    """Before-half glyph swaps one slot to the left."""
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data())
    # 0x0ABF is the BEFORE_HALF_CHAR per the upstream source comment.
    glyphs = [0x0BAE, 0x0ABF]
    out = worker.reposition_glyphs(glyphs)
    assert out == [0x0ABF, 0x0BAE]


def test_apply_transforms_with_feature_single_substitution() -> None:
    """A supported feature is applied during ``apply_transforms``."""
    # Define ``pres`` as a passthrough-like feature: maps 0x0BAE → 0x9999.
    features = {"pres": {(0x0BAE,): (0x9999,)}}
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data(features))
    out = worker.apply_transforms([0x0BAE])
    assert out == [0x9999]


def test_apply_transforms_unsupported_feature_continue_branch() -> None:
    """Feature tags that aren't in the FeatureList are skipped quietly."""
    # ``pres`` is unsupported (missing from ``feature_list``); ``locl``
    # is present but empty.
    features = {"locl": {}}
    worker = GsubWorkerForTamil(_StubCmap(), _make_gsub_data(features))
    glyphs = [0x0BAE, 0x0BAF]
    assert worker.apply_transforms(glyphs) == glyphs
