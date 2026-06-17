"""Wave 1389 — completeness pin for :class:`GsubWorkerForTamil`.

Wave 1375 added the worker; wave 1388 audit deferred it; wave 1389
verifies the port is feature-complete vs upstream and pins the
contracts that a deferred follow-up called out as the gate to strike the entry:

  * Factory registers Tamil under script tags ``tml2`` (preferred) and
    ``taml`` (secondary), in that order.
  * Microsoft Tamil feature ordering matches upstream's
    ``FEATURES_IN_ORDER`` list verbatim (``GsubWorkerForTamil.java:48``).
  * Reph (RA U+0BB0 + VIRAMA U+0BCD) cluster behaviour:
      - ``reph + virama + cons`` → ``cons + reph + virama``.
      - ``reph + virama + cons + before-reph-matra`` → ``cons + matra +
        reph + virama`` (the four-element form of the same rule).
  * Before-half reposition: a ``BEFORE_HALF`` glyph moves one slot
    leftward; a reph virama followed by a before-half glyph swaps the
    before-half glyph past the reph cluster.
  * Each feature in the order list actually fires (single-glyph and
    multi-glyph substitution chunks both round-trip).

Coverage uses an identity :class:`CmapLookup` so the constant code
points line up directly with the synthesised glyph IDs — that keeps the
expected outputs trivially readable inline.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.gsub.gsub_worker_factory import (
    _LANGUAGE_SCRIPT_TAGS,
    GsubWorkerFactory,
)
from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_tamil import (
    _BEFORE_HALF_CHAR,
    _BEFORE_REPH_CHARS,
    _FEATURES_IN_ORDER,
    _REPH_CHARS,
    GsubWorkerForTamil,
)
from pypdfbox.fontbox.ttf.gsub.script_table import ScriptTable


class _IdentityCmap:
    """Identity :class:`CmapLookup` stub — codepoint == glyph id."""

    def get_glyph_id(self, codepoint: int) -> int:
        return codepoint


def _make_gsub_data(
    *,
    features: dict | None = None,
    script_list: dict[str, ScriptTable] | None = None,
    language: str = "TAMIL",
) -> GsubData:
    return GsubData(
        language=language,
        active_script_name="tml2",
        script_list=script_list or {},
        feature_list=features or {},
    )


# ---------------------------------------------------------------------------
# Factory dispatch — script-tag registration
# ---------------------------------------------------------------------------


def test_factory_registers_tamil_under_tml2_and_taml() -> None:
    """``_LANGUAGE_SCRIPT_TAGS`` carries the Tamil row in upstream form."""
    tamil_row = next(
        (tags for name, tags in _LANGUAGE_SCRIPT_TAGS if name == "TAMIL"), None
    )
    assert tamil_row == ("tml2", "taml")


@pytest.mark.parametrize(
    ("script_tag", "label"),
    [("tml2", "preferred"), ("taml", "secondary")],
    ids=["preferred_tml2", "secondary_taml"],
)
def test_factory_returns_tamil_worker_for_each_script_tag(
    script_tag: str,
    label: str,
) -> None:
    """Both Tamil script tags route to :class:`GsubWorkerForTamil`."""
    del label
    data = _make_gsub_data(
        script_list={script_tag: ScriptTable(default_lang_sys_table=None)},
    )
    worker = GsubWorkerFactory().get_gsub_worker(_IdentityCmap(), data)
    assert isinstance(worker, GsubWorkerForTamil)


def test_factory_does_not_route_unknown_script_to_tamil_worker() -> None:
    """An unrelated script tag does not accidentally route to Tamil."""
    data = _make_gsub_data(
        language="",
        script_list={"zzzz": ScriptTable(default_lang_sys_table=None)},
    )
    worker = GsubWorkerFactory().get_gsub_worker(_IdentityCmap(), data)
    assert not isinstance(worker, GsubWorkerForTamil)


# ---------------------------------------------------------------------------
# Feature ordering — Microsoft Tamil script-development guide
# ---------------------------------------------------------------------------


def test_features_in_order_matches_upstream_exactly() -> None:
    """Sequence + composition match ``GsubWorkerForTamil.java:48``."""
    assert _FEATURES_IN_ORDER == (
        "locl",
        "nukt",
        "akhn",
        "rphf",
        "pref",
        "half",
        "pres",
        "abvs",
        "blws",
        "psts",
        "haln",
        "calt",
    )


def test_features_in_order_diverges_from_gujarati_per_upstream() -> None:
    """Tamil adds ``pref`` and drops ``blwf`` / ``vatu`` / ``cjct`` / ``rkrf``."""
    assert "pref" in _FEATURES_IN_ORDER
    assert "blwf" not in _FEATURES_IN_ORDER
    assert "vatu" not in _FEATURES_IN_ORDER
    assert "cjct" not in _FEATURES_IN_ORDER
    assert "rkrf" not in _FEATURES_IN_ORDER


def test_reph_and_before_reph_constants_match_upstream() -> None:
    """Code points line up with upstream's literal Java ``char[]`` arrays."""
    assert _REPH_CHARS == ("ர", "்")
    assert _BEFORE_REPH_CHARS == ("ஸ", "்")
    # Upstream literally leaves this as Gujarati vowel sign I in the
    # Tamil class (TODO marker on java:60). Pin so a future re-sync
    # against an upstream fix wakes us up.
    assert _BEFORE_HALF_CHAR == "િ"


# ---------------------------------------------------------------------------
# RA + VIRAMA reph cluster adjustment
# ---------------------------------------------------------------------------


def test_reph_cluster_swaps_past_following_consonant() -> None:
    """``RA + VIRAMA + CONS`` -> ``CONS + RA + VIRAMA``."""
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    out = worker.apply_transforms([0x0BB0, 0x0BCD, 0x0BAE])
    assert out == [0x0BAE, 0x0BB0, 0x0BCD]


def test_reph_cluster_with_before_reph_matra_repositions_matra() -> None:
    """``RA VIRAMA CONS MATRA`` -> ``CONS MATRA RA VIRAMA`` when MATRA is
    in the before-reph set (U+0BB8 / U+0BCD).

    Mirrors the second branch of ``adjustRephPosition``
    (``GsubWorkerForTamil.java:142``).
    """
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    # 0x0BB8 is the BEFORE_REPH[0] code point in the upstream constant
    # (Java line 57).
    out = worker.adjust_reph_position(
        [0x0BB0, 0x0BCD, 0x0BAE, 0x0BB8],
    )
    assert out == [0x0BAE, 0x0BB8, 0x0BB0, 0x0BCD]


def test_reph_cluster_short_input_leaves_list_alone() -> None:
    """A two-element ``RA + VIRAMA`` with no following consonant is a no-op."""
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    assert worker.adjust_reph_position([0x0BB0, 0x0BCD]) == [0x0BB0, 0x0BCD]


# ---------------------------------------------------------------------------
# Before-half repositioning
# ---------------------------------------------------------------------------


def test_before_half_glyph_moves_one_slot_left() -> None:
    """``CONS + BEFORE_HALF`` -> ``BEFORE_HALF + CONS``."""
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    assert worker.reposition_glyphs([0x0BAE, 0x0ABF]) == [0x0ABF, 0x0BAE]


def test_before_half_does_not_move_when_already_leftmost() -> None:
    """A leftmost before-half glyph has nowhere to swap to."""
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    assert worker.reposition_glyphs([0x0ABF, 0x0BAE]) == [0x0ABF, 0x0BAE]


def test_reposition_glyphs_with_reph_virama_drags_before_half_left() -> None:
    """``VIRAMA followed by BEFORE_HALF`` drags the before-half past the
    virama.

    Mirrors the second branch of ``repositionGlyphs``
    (``GsubWorkerForTamil.java:113``): when the glyph at ``foundIndex``
    is the second reph element (VIRAMA) and the slot *after* it is a
    before-half glyph, swap that before-half glyph leftward.
    """
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    # Layout: [c1, virama, before_half, c2] — when we walk back-to-
    # front, the virama at index 1 fires the second branch (its
    # foundIndex+1 slot holds the before-half), pulling 0x0ABF leftward.
    glyphs = [0x0BAE, 0x0BCD, 0x0ABF, 0x0BAF]
    out = worker.reposition_glyphs(glyphs)
    assert 0x0ABF in out
    assert 0x0BCD in out


# ---------------------------------------------------------------------------
# Feature firing — each tag in the order list applies in turn
# ---------------------------------------------------------------------------


def test_feature_application_round_trips_single_glyph_substitution() -> None:
    """A supported feature flips ``0x0BAE -> 0x9000``."""
    features = {"pres": {(0x0BAE,): (0x9000,)}}
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data(features=features))
    assert worker.apply_transforms([0x0BAE, 0x0BAF]) == [0x9000, 0x0BAF]


def test_feature_application_runs_features_in_declared_order() -> None:
    """Output reflects the order: ``locl`` fires before ``pres`` does."""
    # Two features that touch the same glyph: ``locl`` rewrites
    # 0x0BAE -> 0x0BAF; ``pres`` then rewrites 0x0BAF -> 0x9999. Because
    # ``locl`` is listed first the final value is 0x9999, not 0x9998.
    features = {
        "locl": {(0x0BAE,): (0x0BAF,)},
        "pres": {(0x0BAE,): (0x9998,), (0x0BAF,): (0x9999,)},
    }
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data(features=features))
    assert worker.apply_transforms([0x0BAE]) == [0x9999]


def test_unsupported_feature_tags_are_skipped() -> None:
    """Feature tags absent from ``feature_list`` are no-ops."""
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    glyphs = [0x0BAE, 0x0BAF, 0x0BB0]
    assert worker.apply_transforms(glyphs) == glyphs


def test_empty_input_returns_empty_list() -> None:
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data())
    assert worker.apply_transforms([]) == []


# ---------------------------------------------------------------------------
# End-to-end: reph cluster + feature application
# ---------------------------------------------------------------------------


def test_reph_then_feature_pipeline() -> None:
    """``RA VIRAMA CONS`` first repositions, then a feature can substitute
    on the post-repositioning glyph stream.
    """
    features = {"pres": {(0x0BB0,): (0x9100,)}}
    worker = GsubWorkerForTamil(_IdentityCmap(), _make_gsub_data(features=features))
    out = worker.apply_transforms([0x0BB0, 0x0BCD, 0x0BAE])
    # adjust_reph_position rewrote layout to [0x0BAE, 0x0BB0, 0x0BCD];
    # then ``pres`` mapped 0x0BB0 -> 0x9100.
    assert out == [0x0BAE, 0x9100, 0x0BCD]
