"""Wave 271 — pdmodel/interactive/annotation/PDAnnotationCaret parity gaps.

Round-out cold gaps last touched in Wave 216:

* explicit ``clear_rectangle_differences`` / ``clear_symbol`` companions to
  the existing ``set_*(None)`` clears
* per-side ``get_left_difference`` / ``get_top_difference`` /
  ``get_right_difference`` / ``get_bottom_difference`` accessors backed by
  the ``[lx ly rx ry]`` Table 180 ordering
* aggregate ``is_caret_default`` predicate — ``True`` when the
  caret-specific entries (``/RD``, ``/Sy``) are entirely spec-default
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)

# ---------- clear_rectangle_differences ----------


def test_clear_rectangle_differences_removes_entry_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(2.0)
    assert ann.has_rectangle_differences() is True

    ann.clear_rectangle_differences()

    assert ann.has_rectangle_differences() is False
    assert ann.get_rectangle_differences() is None
    # Underlying COSDictionary actually drops /RD.
    assert (
        ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("RD"))
        is None
    )


def test_clear_rectangle_differences_idempotent_wave271() -> None:
    """Clearing twice is a no-op — same shape as ``set_*(None)``."""
    ann = PDAnnotationCaret()
    ann.clear_rectangle_differences()
    ann.clear_rectangle_differences()
    assert ann.has_rectangle_differences() is False


def test_clear_rectangle_differences_preserves_symbol_wave271() -> None:
    """Clearing /RD must not touch /Sy."""
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_PARAGRAPH)
    ann.set_rect_differences_uniform(1.0)

    ann.clear_rectangle_differences()

    assert ann.has_rectangle_differences() is False
    assert ann.get_symbol() == "P"


# ---------- clear_symbol ----------


def test_clear_symbol_removes_entry_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_PARAGRAPH)
    assert ann.has_symbol() is True

    ann.clear_symbol()

    assert ann.has_symbol() is False
    # /Sy absent → spec default surfaces via getter.
    assert ann.get_symbol() == PDAnnotationCaret.SY_NONE
    assert (
        ann.get_cos_object().get_name(COSName.get_pdf_name("Sy")) is None
    )


def test_clear_symbol_idempotent_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.clear_symbol()
    ann.clear_symbol()
    assert ann.has_symbol() is False


def test_clear_symbol_after_explicit_none_wave271() -> None:
    """Clearing must drop even an explicit ``/Sy /None``."""
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_NONE)
    assert ann.has_symbol() is True

    ann.clear_symbol()

    assert ann.has_symbol() is False


def test_clear_symbol_preserves_rectangle_differences_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_lrtb(1.0, 2.0, 3.0, 4.0)
    ann.set_symbol("P")

    ann.clear_symbol()

    assert ann.has_symbol() is False
    assert ann.get_rect_differences() == [1.0, 2.0, 3.0, 4.0]


# ---------- per-side /RD accessors ----------


def test_per_side_difference_returns_none_when_unset_wave271() -> None:
    ann = PDAnnotationCaret()
    assert ann.get_left_difference() is None
    assert ann.get_top_difference() is None
    assert ann.get_right_difference() is None
    assert ann.get_bottom_difference() is None


def test_per_side_difference_reports_lrtb_ordering_wave271() -> None:
    """Spec /RD ordering is ``[left top right bottom]`` (Table 180)."""
    ann = PDAnnotationCaret()
    ann.set_rect_differences_lrtb(1.0, 2.0, 3.0, 4.0)

    assert ann.get_left_difference() == 1.0
    assert ann.get_top_difference() == 2.0
    assert ann.get_right_difference() == 3.0
    assert ann.get_bottom_difference() == 4.0


def test_per_side_difference_uniform_returns_same_for_all_sides_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(2.5)

    assert ann.get_left_difference() == 2.5
    assert ann.get_top_difference() == 2.5
    assert ann.get_right_difference() == 2.5
    assert ann.get_bottom_difference() == 2.5


def test_per_side_difference_zero_distinguished_from_unset_wave271() -> None:
    """Explicit zero must surface as ``0.0``, not ``None``."""
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(0.0)

    assert ann.get_left_difference() == 0.0
    assert ann.get_top_difference() == 0.0
    assert ann.get_right_difference() == 0.0
    assert ann.get_bottom_difference() == 0.0


def test_per_side_difference_after_clear_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_lrtb(1.0, 2.0, 3.0, 4.0)
    ann.clear_rectangle_differences()

    assert ann.get_left_difference() is None
    assert ann.get_top_difference() is None
    assert ann.get_right_difference() is None
    assert ann.get_bottom_difference() is None


# ---------- is_caret_default ----------


def test_is_caret_default_on_fresh_annotation_wave271() -> None:
    """A bare ``PDAnnotationCaret()`` (just /Type + /Subtype) is in spec-default
    territory for the caret-specific entries."""
    ann = PDAnnotationCaret()
    assert ann.is_caret_default() is True


def test_is_caret_default_false_when_rd_set_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(1.0)
    assert ann.is_caret_default() is False


def test_is_caret_default_false_when_symbol_set_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_PARAGRAPH)
    assert ann.is_caret_default() is False


def test_is_caret_default_false_for_explicit_sy_none_wave271() -> None:
    """An explicit ``/Sy /None`` is "set" — predicate must not collapse to
    the absent-entry state."""
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_NONE)
    assert ann.is_caret_default() is False


def test_is_caret_default_recovers_after_clearing_both_wave271() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(1.0)
    ann.set_symbol("P")
    assert ann.is_caret_default() is False

    ann.clear_rectangle_differences()
    ann.clear_symbol()

    assert ann.is_caret_default() is True


def test_is_caret_default_ignores_markup_metadata_wave271() -> None:
    """``/Subj``, ``/IRT`` etc. live on PDAnnotationMarkup — the caret-level
    "default" predicate must not consider them."""
    ann = PDAnnotationCaret()
    ann.set_subject("review note")
    assert ann.is_caret_default() is True
