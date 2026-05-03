"""Wave 269 round-out tests for PDViewerPreferences.

Covers long-form upstream-style constant aliases, token-equivalence
predicates (``is_print_scaling_*``, ``is_simplex``,
``is_duplex_flip_*``, ``is_left_to_right`` / ``is_right_to_left``),
clear-entry helpers (``clear_enforce``, ``clear_print_page_range``,
``clear_num_copies``), count helpers (``enforce_count``,
``get_print_page_range_pair_count``), the ``is_valid_print_page_range``
structural validator, and the bulk ``add_enforce_names`` mutator.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel import PDViewerPreferences

# ---------- long-form constant aliases ----------


def test_non_full_screen_page_mode_long_form_aliases() -> None:
    assert (
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_NONE == "UseNone"
    )
    assert (
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_OUTLINES
        == "UseOutlines"
    )
    assert (
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_THUMBS
        == "UseThumbs"
    )
    assert PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_OC == "UseOC"


def test_reading_direction_long_form_aliases() -> None:
    assert PDViewerPreferences.READING_DIRECTION_L2R == "L2R"
    assert PDViewerPreferences.READING_DIRECTION_R2L == "R2L"
    # Long-form aliases match the short-form ones byte-for-byte.
    assert (
        PDViewerPreferences.READING_DIRECTION_L2R
        == PDViewerPreferences.DIRECTION_L2R
    )
    assert (
        PDViewerPreferences.READING_DIRECTION_R2L
        == PDViewerPreferences.DIRECTION_R2L
    )


def test_print_scaling_app_default_underscored_alias() -> None:
    # The underscored alias matches the un-underscored upstream form.
    assert PDViewerPreferences.PRINT_SCALING_APP_DEFAULT == "AppDefault"
    assert (
        PDViewerPreferences.PRINT_SCALING_APP_DEFAULT
        == PDViewerPreferences.PRINT_SCALING_APPDEFAULT
    )
    assert PDViewerPreferences.PRINT_SCALING_NONE == "None"


def test_duplex_short_form_aliases() -> None:
    assert (
        PDViewerPreferences.DUPLEX_FLIP_SHORT_EDGE == "DuplexFlipShortEdge"
    )
    assert (
        PDViewerPreferences.DUPLEX_FLIP_LONG_EDGE == "DuplexFlipLongEdge"
    )
    # Short-form matches the verbose form byte-for-byte.
    assert (
        PDViewerPreferences.DUPLEX_FLIP_SHORT_EDGE
        == PDViewerPreferences.DUPLEX_DUPLEX_FLIP_SHORT_EDGE
    )
    assert (
        PDViewerPreferences.DUPLEX_FLIP_LONG_EDGE
        == PDViewerPreferences.DUPLEX_DUPLEX_FLIP_LONG_EDGE
    )


# ---------- print-scaling predicates ----------


def test_is_print_scaling_app_default_when_absent() -> None:
    p = PDViewerPreferences()
    # /PrintScaling defaults to AppDefault per Table 150.
    assert p.is_print_scaling_app_default() is True
    assert p.is_print_scaling_none() is False


def test_is_print_scaling_none_when_explicit_none() -> None:
    p = PDViewerPreferences()
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    assert p.is_print_scaling_none() is True
    assert p.is_print_scaling_app_default() is False


def test_is_print_scaling_app_default_when_explicit_app_default() -> None:
    p = PDViewerPreferences()
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.AppDefault)
    assert p.is_print_scaling_app_default() is True
    assert p.is_print_scaling_none() is False


def test_is_print_scaling_neither_when_unknown_token() -> None:
    p = PDViewerPreferences()
    p.set_print_scaling("Something")  # producer-written nonstandard token
    assert p.is_print_scaling_none() is False
    assert p.is_print_scaling_app_default() is False


# ---------- duplex predicates ----------


def test_duplex_predicates_when_absent() -> None:
    p = PDViewerPreferences()
    # /Duplex has no spec default — all predicates False when absent.
    assert p.is_simplex() is False
    assert p.is_duplex_flip_short_edge() is False
    assert p.is_duplex_flip_long_edge() is False


def test_is_simplex_only_when_simplex() -> None:
    p = PDViewerPreferences()
    p.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    assert p.is_simplex() is True
    assert p.is_duplex_flip_short_edge() is False
    assert p.is_duplex_flip_long_edge() is False


def test_is_duplex_flip_short_edge() -> None:
    p = PDViewerPreferences()
    p.set_duplex(PDViewerPreferences.DUPLEX.DuplexFlipShortEdge)
    assert p.is_simplex() is False
    assert p.is_duplex_flip_short_edge() is True
    assert p.is_duplex_flip_long_edge() is False


def test_is_duplex_flip_long_edge() -> None:
    p = PDViewerPreferences()
    p.set_duplex(PDViewerPreferences.DUPLEX.DuplexFlipLongEdge)
    assert p.is_simplex() is False
    assert p.is_duplex_flip_short_edge() is False
    assert p.is_duplex_flip_long_edge() is True


# ---------- direction predicates ----------


def test_direction_predicates_default_l2r() -> None:
    p = PDViewerPreferences()
    # /Direction defaults to L2R per Table 150.
    assert p.is_left_to_right() is True
    assert p.is_right_to_left() is False


def test_direction_predicates_after_set_r2l() -> None:
    p = PDViewerPreferences()
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    assert p.is_left_to_right() is False
    assert p.is_right_to_left() is True


def test_direction_predicates_after_set_l2r() -> None:
    p = PDViewerPreferences()
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.L2R)
    assert p.is_left_to_right() is True
    assert p.is_right_to_left() is False


def test_direction_predicates_unknown_token_falls_through() -> None:
    p = PDViewerPreferences()
    p.set_reading_direction("XYZ")
    assert p.is_left_to_right() is False
    assert p.is_right_to_left() is False


# ---------- clear-entry helpers ----------


def test_clear_enforce_drops_entry() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling"])
    assert p.has_enforce() is True
    p.clear_enforce()
    assert p.has_enforce() is False
    # Re-clearing is a no-op.
    p.clear_enforce()
    assert p.has_enforce() is False


def test_clear_print_page_range_drops_entry() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(1, 5), (10, 20)])
    assert p.has_print_page_range() is True
    p.clear_print_page_range()
    assert p.has_print_page_range() is False
    # Re-clearing is a no-op.
    p.clear_print_page_range()
    assert p.has_print_page_range() is False


def test_clear_num_copies_drops_entry_and_falls_back_to_default() -> None:
    p = PDViewerPreferences()
    p.set_num_copies(7)
    assert p.has_num_copies() is True
    assert p.get_num_copies() == 7
    p.clear_num_copies()
    assert p.has_num_copies() is False
    # Getter falls back to the spec default of 1.
    assert p.get_num_copies() == 1
    # Re-clearing is a no-op.
    p.clear_num_copies()
    assert p.has_num_copies() is False


# ---------- enforce_count ----------


def test_enforce_count_when_absent() -> None:
    p = PDViewerPreferences()
    assert p.enforce_count() == 0


def test_enforce_count_after_population() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling", "Duplex", "NumCopies"])
    assert p.enforce_count() == 3


def test_enforce_count_skips_non_name_entries() -> None:
    # Producer-written /Enforce with mixed types: only name tokens count.
    p = PDViewerPreferences()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("PrintScaling"))
    arr.add(COSInteger.get(99))  # bogus non-name entry
    arr.add(COSName.get_pdf_name("Duplex"))
    p.set_enforce(arr)
    assert p.enforce_count() == 2


# ---------- add_enforce_names (bulk mutator) ----------


def test_add_enforce_names_creates_entry() -> None:
    p = PDViewerPreferences()
    assert p.has_enforce() is False
    p.add_enforce_names(["PrintScaling", "Duplex"])
    assert p.has_enforce() is True
    assert p.get_enforce_names() == ["PrintScaling", "Duplex"]


def test_add_enforce_names_skips_duplicates() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling"])
    p.add_enforce_names(["Duplex", "PrintScaling", "NumCopies"])
    # PrintScaling kept its position; Duplex/NumCopies appended in order.
    assert p.get_enforce_names() == ["PrintScaling", "Duplex", "NumCopies"]


def test_add_enforce_names_idempotent_on_all_duplicates() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling", "Duplex"])
    p.add_enforce_names(["PrintScaling", "Duplex"])
    assert p.get_enforce_names() == ["PrintScaling", "Duplex"]


def test_add_enforce_names_with_empty_iterable_is_noop() -> None:
    p = PDViewerPreferences()
    p.add_enforce_names([])
    # Should NOT have created a /Enforce entry from an empty iterable.
    assert p.has_enforce() is False


def test_add_enforce_names_with_generator() -> None:
    p = PDViewerPreferences()
    p.add_enforce_names(n for n in ["A", "B", "A", "C"])
    assert p.get_enforce_names() == ["A", "B", "C"]


# ---------- print-page-range count + structural validation ----------


def test_get_print_page_range_pair_count_when_absent() -> None:
    p = PDViewerPreferences()
    assert p.get_print_page_range_pair_count() == 0


def test_get_print_page_range_pair_count_after_population() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(1, 5), (10, 20), (30, 40)])
    assert p.get_print_page_range_pair_count() == 3


def test_get_print_page_range_pair_count_odd_length_returns_zero() -> None:
    # Odd-length /PrintPageRange is invalid per PDF 32000-2 §12.4.4 and
    # should produce a 0 pair count (matching get_print_page_range_pairs).
    p = PDViewerPreferences()
    p.set_print_page_range(COSArray.of_cos_integers([1, 5, 10]))
    assert p.get_print_page_range_pair_count() == 0


def test_is_valid_print_page_range_when_absent() -> None:
    p = PDViewerPreferences()
    # A missing /PrintPageRange is trivially valid.
    assert p.is_valid_print_page_range() is True


def test_is_valid_print_page_range_well_formed() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(1, 5), (10, 20)])
    assert p.is_valid_print_page_range() is True


def test_is_valid_print_page_range_single_page_pair() -> None:
    # (n, n) is a valid single-page range — start == end is allowed.
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(7, 7)])
    assert p.is_valid_print_page_range() is True


def test_is_valid_print_page_range_odd_length_invalid() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range(COSArray.of_cos_integers([1, 5, 10]))
    assert p.is_valid_print_page_range() is False


def test_is_valid_print_page_range_decreasing_pair_invalid() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(10, 5)])
    assert p.is_valid_print_page_range() is False


def test_is_valid_print_page_range_zero_or_negative_invalid() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(0, 5)])
    assert p.is_valid_print_page_range() is False
    p2 = PDViewerPreferences()
    p2.set_print_page_range_pairs([(-3, 5)])
    assert p2.is_valid_print_page_range() is False


def test_is_valid_print_page_range_empty_array_is_valid() -> None:
    # An empty /PrintPageRange is degenerate but not malformed.
    p = PDViewerPreferences()
    p.set_print_page_range(COSArray())
    assert p.is_valid_print_page_range() is True
    assert p.get_print_page_range_pair_count() == 0
