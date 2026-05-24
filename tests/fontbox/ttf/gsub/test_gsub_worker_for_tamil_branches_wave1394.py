"""Wave 1394 — uncovered branches in ``GsubWorkerForTamil``.

Covers:

* Line 86 — ``script_feature is None`` continue branch in
  ``apply_transforms`` (feature key present in the feature-list with a
  ``None`` value).
* Lines 152-156 — ``reposition_glyphs`` reph + before-half drag path
  (the elif branch where the loop lands on the virama-reph glyph and
  the slot after it carries a before-half glyph).
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_tamil import GsubWorkerForTamil


class _IdentityCmap:
    """Identity cmap — codepoint == GID, like the existing tests."""

    def get_glyph_id(self, codepoint: int) -> int:
        return codepoint


def test_apply_transforms_skips_feature_when_adapter_returns_none() -> None:
    """A feature whose value is ``None`` triggers the ``continue`` branch
    on line 86 (feature_tag listed but ``_adapt_feature`` returns ``None``)."""
    # Feature key present but value is None — `is_feature_supported` returns
    # True; `_adapt_feature` returns None; the worker continues.
    features = {"pres": None}
    worker = GsubWorkerForTamil(_IdentityCmap(), GsubData(
        active_script_name="taml", feature_list=features,
    ))
    glyphs = [0x0BAE, 0x0BAF, 0x0BB0]
    out = worker.apply_transforms(glyphs)
    # No substitution feature applied — output equals input (modulo the
    # repositioning pre-passes, which are identity-no-op here).
    assert out == glyphs


def test_reposition_glyphs_drags_before_half_past_reph_virama() -> None:
    """Reach the elif branch (lines 152-156).

    Glyph 0x0BCD is the virama (``_reph_glyph_ids[1]``) and 0x0BBF is the
    before-half. With input ``[X, V, X, B]`` the loop:

    1. found_index=3 (B): pop+insert moves B one slot left →
       ``[X, V, B, X]``. next_index=1, found_index=1.
    2. found_index=1 (V), prev_index=2 carries B (before-half) — the
       elif fires: pop(prev), insert(next_index, prev) →
       ``[B, X, V, X]``.
    """
    worker = GsubWorkerForTamil(_IdentityCmap(), GsubData(
        active_script_name="taml", feature_list={},
    ))
    x = 0x0BAE  # any Tamil consonant; not special
    v = 0x0BCD
    b = 0x0ABF  # _BEFORE_HALF_CHAR — actually Gujarati U+0ABF (upstream literal)
    out = worker.reposition_glyphs([x, v, x, b])
    assert out == [b, x, v, x]


def test_reposition_glyphs_elif_branch_no_op_when_prev_not_before_half() -> None:
    """Companion: the elif's outer condition matches (V at found_index +
    prev_index in range) but the inner condition fails because prev is
    not a before-half — no mutation. Lines 152 still executed (the assign),
    but 153-156 are skipped."""
    worker = GsubWorkerForTamil(_IdentityCmap(), GsubData(
        active_script_name="taml", feature_list={},
    ))
    x = 0x0BAE
    v = 0x0BCD
    # [X, V, X] — when loop reaches found_index=1 (V), prev_index=2 (X)
    # is in range but X is not a before-half.
    out = worker.reposition_glyphs([x, v, x])
    assert out == [x, v, x]
