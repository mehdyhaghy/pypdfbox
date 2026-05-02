"""Wave 181 round-out tests for PDViewerPreferences.

Covers the ``has_*`` presence predicates, ``/Enforce`` element-level
helpers (``is_enforced`` / ``add_enforce_name`` / ``remove_enforce_name``),
and the ``add_print_page_range_pair`` mutator added to close small
remaining gaps against upstream Apache PDFBox + PDF 32000-2 §12.4.4.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel import PDViewerPreferences

# ---------- has_* presence predicates ----------


def test_has_non_full_screen_page_mode_default_false() -> None:
    p = PDViewerPreferences()
    assert p.has_non_full_screen_page_mode() is False


def test_has_non_full_screen_page_mode_true_after_set() -> None:
    p = PDViewerPreferences()
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseNone
    )
    # Even when set to the spec default, the predicate is True.
    assert p.has_non_full_screen_page_mode() is True
    p.set_non_full_screen_page_mode(None)
    assert p.has_non_full_screen_page_mode() is False


def test_has_direction_default_false() -> None:
    p = PDViewerPreferences()
    assert p.has_direction() is False
    # Even when the stored value matches the spec default, the predicate
    # tracks presence — distinguishes "stated L2R" from "defaulted L2R".
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.L2R)
    assert p.has_direction() is True


def test_has_view_area_clip_print_area_print_clip() -> None:
    p = PDViewerPreferences()
    assert p.has_view_area() is False
    assert p.has_view_clip() is False
    assert p.has_print_area() is False
    assert p.has_print_clip() is False
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    p.set_view_clip(PDViewerPreferences.BOUNDARY.BleedBox)
    p.set_print_area(PDViewerPreferences.BOUNDARY.TrimBox)
    p.set_print_clip(PDViewerPreferences.BOUNDARY.ArtBox)
    assert p.has_view_area()
    assert p.has_view_clip()
    assert p.has_print_area()
    assert p.has_print_clip()
    p.set_view_area(None)
    p.set_view_clip(None)
    p.set_print_area(None)
    p.set_print_clip(None)
    assert p.has_view_area() is False
    assert p.has_view_clip() is False
    assert p.has_print_area() is False
    assert p.has_print_clip() is False


def test_has_duplex_default_false_no_spec_default() -> None:
    """``/Duplex`` has no spec default — the predicate distinguishes
    'absent (caller decides)' from 'explicitly Simplex'."""
    p = PDViewerPreferences()
    assert p.has_duplex() is False
    p.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    assert p.has_duplex() is True
    p.set_duplex(None)
    assert p.has_duplex() is False


def test_has_print_scaling_default_false() -> None:
    p = PDViewerPreferences()
    assert p.has_print_scaling() is False
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.AppDefault)
    assert p.has_print_scaling() is True


def test_has_num_copies_default_false() -> None:
    p = PDViewerPreferences()
    assert p.has_num_copies() is False
    # get_num_copies returns 1 even when absent, so the predicate is the
    # only way to detect 'no /NumCopies entry'.
    assert p.get_num_copies() == 1
    p.set_num_copies(1)
    assert p.has_num_copies() is True
    p.set_num_copies(None)
    assert p.has_num_copies() is False


def test_has_print_page_range_and_enforce_default_false() -> None:
    p = PDViewerPreferences()
    assert p.has_print_page_range() is False
    assert p.has_enforce() is False
    p.set_print_page_range_pairs([(1, 2)])
    p.set_enforce_names(["PrintScaling"])
    assert p.has_print_page_range() is True
    assert p.has_enforce() is True


# ---------- /Enforce element-level helpers ----------


def test_is_enforced_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_enforced("PrintScaling") is False


def test_is_enforced_after_set_enforce_names() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling", "Duplex"])
    assert p.is_enforced("PrintScaling") is True
    assert p.is_enforced("Duplex") is True
    assert p.is_enforced("ViewArea") is False


def test_add_enforce_name_creates_entry_when_absent() -> None:
    p = PDViewerPreferences()
    assert not p.has_enforce()
    p.add_enforce_name("PrintScaling")
    assert p.has_enforce()
    assert p.get_enforce_names() == ["PrintScaling"]


def test_add_enforce_name_appends() -> None:
    p = PDViewerPreferences()
    p.add_enforce_name("PrintScaling")
    p.add_enforce_name("Duplex")
    assert p.get_enforce_names() == ["PrintScaling", "Duplex"]


def test_add_enforce_name_idempotent() -> None:
    p = PDViewerPreferences()
    p.add_enforce_name("PrintScaling")
    p.add_enforce_name("PrintScaling")
    p.add_enforce_name("PrintScaling")
    assert p.get_enforce_names() == ["PrintScaling"]


def test_remove_enforce_name_returns_true_when_present() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling", "Duplex", "ViewArea"])
    assert p.remove_enforce_name("Duplex") is True
    assert p.get_enforce_names() == ["PrintScaling", "ViewArea"]


def test_remove_enforce_name_returns_false_when_absent() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling"])
    assert p.remove_enforce_name("Duplex") is False
    assert p.get_enforce_names() == ["PrintScaling"]


def test_remove_enforce_name_when_no_entry() -> None:
    p = PDViewerPreferences()
    assert p.remove_enforce_name("PrintScaling") is False
    assert p.has_enforce() is False


def test_remove_last_enforce_name_drops_entry() -> None:
    """Removing the only element should clear ``/Enforce`` itself rather
    than leaving an empty array in the dictionary."""
    p = PDViewerPreferences()
    p.add_enforce_name("PrintScaling")
    assert p.has_enforce() is True
    assert p.remove_enforce_name("PrintScaling") is True
    assert p.has_enforce() is False
    assert p.get_enforce() is None
    assert p.get_enforce_names() == []


def test_is_enforced_after_round_trip() -> None:
    p = PDViewerPreferences()
    p.add_enforce_name("PrintScaling")
    p.add_enforce_name("Duplex")
    p.remove_enforce_name("PrintScaling")
    assert p.is_enforced("PrintScaling") is False
    assert p.is_enforced("Duplex") is True


# ---------- add_print_page_range_pair ----------


def test_add_print_page_range_pair_creates_entry_when_absent() -> None:
    p = PDViewerPreferences()
    assert p.has_print_page_range() is False
    p.add_print_page_range_pair(1, 5)
    assert p.has_print_page_range() is True
    assert p.get_print_page_range_pairs() == [(1, 5)]


def test_add_print_page_range_pair_appends() -> None:
    p = PDViewerPreferences()
    p.add_print_page_range_pair(1, 3)
    p.add_print_page_range_pair(7, 9)
    p.add_print_page_range_pair(12, 12)
    assert p.get_print_page_range_pairs() == [(1, 3), (7, 9), (12, 12)]


def test_add_print_page_range_pair_writes_flat_integers() -> None:
    """Each pair adds two consecutive ``COSInteger`` entries."""
    p = PDViewerPreferences()
    p.add_print_page_range_pair(2, 4)
    p.add_print_page_range_pair(8, 10)
    arr = p.get_print_page_range()
    assert arr is not None
    assert arr.size() == 4
    assert arr.get_int(0) == 2
    assert arr.get_int(1) == 4
    assert arr.get_int(2) == 8
    assert arr.get_int(3) == 10


def test_add_print_page_range_pair_after_raw_array() -> None:
    """Appending a pair after a raw array round-trips through pairs
    decoding (works only when the pre-existing array is well-formed)."""
    p = PDViewerPreferences()
    p.set_print_page_range(COSArray.of_cos_integers([1, 2, 3, 4]))
    p.add_print_page_range_pair(5, 6)
    assert p.get_print_page_range_pairs() == [(1, 2), (3, 4), (5, 6)]


# ---------- predicate consistency with COS dictionary ----------


def test_has_predicates_track_underlying_dict() -> None:
    """Predicates should agree exactly with ``contains_key`` on the wrapped
    dictionary — they are thin presence checks, not value checks."""
    p = PDViewerPreferences()
    cos = p.get_cos_object()
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    p.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    p.set_num_copies(2)
    p.set_print_page_range_pairs([(1, 1)])
    p.set_enforce_names(["PrintScaling"])
    assert p.has_view_area() == cos.contains_key(COSName.get_pdf_name("ViewArea"))
    assert p.has_duplex() == cos.contains_key(COSName.get_pdf_name("Duplex"))
    assert p.has_num_copies() == cos.contains_key(COSName.get_pdf_name("NumCopies"))
    assert p.has_print_page_range() == cos.contains_key(
        COSName.get_pdf_name("PrintPageRange")
    )
    assert p.has_enforce() == cos.contains_key(COSName.get_pdf_name("Enforce"))
