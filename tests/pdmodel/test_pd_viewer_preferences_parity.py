"""Parity tests for PDViewerPreferences upstream-named accessors and
class-level string constants.

These tests focus on the upstream-named ``is_*`` boolean accessors,
``get_direction`` / ``set_direction``, and the plain string constants
that mirror Apache PDFBox's public Java API surface.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDViewerPreferences

# ---------- ``is_*`` boolean accessors (defaults) ----------


def test_is_hide_toolbar_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_hide_toolbar() is False


def test_is_hide_menubar_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_hide_menubar() is False


def test_is_hide_window_ui_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_hide_window_ui() is False


def test_is_fit_window_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_fit_window() is False


def test_is_center_window_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_center_window() is False


def test_is_display_doc_title_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_display_doc_title() is False


def test_is_pick_tray_by_pdf_size_default_false() -> None:
    p = PDViewerPreferences()
    assert p.is_pick_tray_by_pdf_size() is False


# ---------- ``is_*`` boolean accessors (round-trip) ----------


def test_is_hide_toolbar_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    assert p.is_hide_toolbar() is True
    p.set_hide_toolbar(False)
    assert p.is_hide_toolbar() is False


def test_is_hide_menubar_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_hide_menubar(True)
    assert p.is_hide_menubar() is True
    p.set_hide_menubar(False)
    assert p.is_hide_menubar() is False


def test_is_hide_window_ui_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_hide_window_ui(True)
    assert p.is_hide_window_ui() is True
    p.set_hide_window_ui(False)
    assert p.is_hide_window_ui() is False


def test_is_fit_window_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_fit_window(True)
    assert p.is_fit_window() is True
    p.set_fit_window(False)
    assert p.is_fit_window() is False


def test_is_center_window_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_center_window(True)
    assert p.is_center_window() is True
    p.set_center_window(False)
    assert p.is_center_window() is False


def test_is_display_doc_title_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_display_doc_title(True)
    assert p.is_display_doc_title() is True
    p.set_display_doc_title(False)
    assert p.is_display_doc_title() is False


def test_is_pick_tray_by_pdf_size_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_pick_tray_by_pdf_size(True)
    assert p.is_pick_tray_by_pdf_size() is True
    p.set_pick_tray_by_pdf_size(False)
    assert p.is_pick_tray_by_pdf_size() is False


# ---------- ``is_*`` accessors agree with non-prefixed forms ----------


def test_is_accessors_track_legacy_accessors() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_hide_menubar(True)
    p.set_hide_window_ui(True)
    p.set_fit_window(True)
    p.set_center_window(True)
    p.set_display_doc_title(True)
    p.set_pick_tray_by_pdf_size(True)
    assert p.is_hide_toolbar() == p.hide_toolbar()
    assert p.is_hide_menubar() == p.hide_menubar()
    assert p.is_hide_window_ui() == p.hide_window_ui()
    assert p.is_fit_window() == p.fit_window()
    assert p.is_center_window() == p.center_window()
    assert p.is_display_doc_title() == p.display_doc_title()
    assert p.is_pick_tray_by_pdf_size() == p.pick_tray_by_pdf_size()


# ---------- get_direction / set_direction (upstream-named) ----------


def test_get_direction_default_l2r() -> None:
    p = PDViewerPreferences()
    assert p.get_direction() == "L2R"


def test_set_direction_round_trip_with_constants() -> None:
    p = PDViewerPreferences()
    p.set_direction(PDViewerPreferences.DIRECTION_R2L)
    assert p.get_direction() == "R2L"
    p.set_direction(PDViewerPreferences.DIRECTION_L2R)
    assert p.get_direction() == "L2R"


def test_set_direction_with_enum_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    assert p.get_direction() == "R2L"


def test_get_direction_tracks_get_reading_direction() -> None:
    p = PDViewerPreferences()
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    assert p.get_direction() == p.get_reading_direction()


# ---------- name-valued accessors with string constants (round-trip) ----------


def test_non_full_screen_page_mode_string_constants_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_non_full_screen_page_mode() == PDViewerPreferences.NON_FS_USE_NONE
    p.set_non_full_screen_page_mode(PDViewerPreferences.NON_FS_USE_OUTLINES)
    assert p.get_non_full_screen_page_mode() == "UseOutlines"
    p.set_non_full_screen_page_mode(PDViewerPreferences.NON_FS_USE_THUMBS)
    assert p.get_non_full_screen_page_mode() == "UseThumbs"
    p.set_non_full_screen_page_mode(PDViewerPreferences.NON_FS_USE_OC)
    assert p.get_non_full_screen_page_mode() == "UseOC"


def test_print_scaling_string_constants_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_print_scaling() == PDViewerPreferences.PRINT_SCALING_APPDEFAULT
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING_NONE)
    assert p.get_print_scaling() == "None"
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING_APPDEFAULT)
    assert p.get_print_scaling() == "AppDefault"


def test_duplex_string_constants_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_duplex() is None
    p.set_duplex(PDViewerPreferences.DUPLEX_SIMPLEX)
    assert p.get_duplex() == "Simplex"
    p.set_duplex(PDViewerPreferences.DUPLEX_DUPLEX_FLIP_SHORT_EDGE)
    assert p.get_duplex() == "DuplexFlipShortEdge"
    p.set_duplex(PDViewerPreferences.DUPLEX_DUPLEX_FLIP_LONG_EDGE)
    assert p.get_duplex() == "DuplexFlipLongEdge"


def test_view_area_default_and_string_constant_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_view_area() == "CropBox"
    p.set_view_area(PDViewerPreferences.BOUNDARY_MEDIA_BOX)
    assert p.get_view_area() == "MediaBox"


def test_view_clip_default_and_string_constant_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_view_clip() == "CropBox"
    p.set_view_clip(PDViewerPreferences.BOUNDARY_BLEED_BOX)
    assert p.get_view_clip() == "BleedBox"


def test_print_area_default_and_string_constant_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_print_area() == "CropBox"
    p.set_print_area(PDViewerPreferences.BOUNDARY_TRIM_BOX)
    assert p.get_print_area() == "TrimBox"


def test_print_clip_default_and_string_constant_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_print_clip() == "CropBox"
    p.set_print_clip(PDViewerPreferences.BOUNDARY_ART_BOX)
    assert p.get_print_clip() == "ArtBox"


# ---------- string constants resolve to the expected /Name token strings ----------


def test_non_full_screen_page_mode_constants_match_pdf_names() -> None:
    assert PDViewerPreferences.NON_FS_USE_NONE == "UseNone"
    assert PDViewerPreferences.NON_FS_USE_OUTLINES == "UseOutlines"
    assert PDViewerPreferences.NON_FS_USE_THUMBS == "UseThumbs"
    assert PDViewerPreferences.NON_FS_USE_OC == "UseOC"
    assert PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_OPTIONAL_CONTENT == "UseOC"
    assert (
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_OPTIONAL_CONTENT
        == PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE_USE_OC
    )


def test_direction_constants_match_pdf_names() -> None:
    assert PDViewerPreferences.DIRECTION_L2R == "L2R"
    assert PDViewerPreferences.DIRECTION_R2L == "R2L"


def test_print_scaling_constants_match_pdf_names() -> None:
    assert PDViewerPreferences.PRINT_SCALING_NONE == "None"
    assert PDViewerPreferences.PRINT_SCALING_APPDEFAULT == "AppDefault"


def test_duplex_constants_match_pdf_names() -> None:
    assert PDViewerPreferences.DUPLEX_SIMPLEX == "Simplex"
    assert PDViewerPreferences.DUPLEX_DUPLEX_FLIP_SHORT_EDGE == "DuplexFlipShortEdge"
    assert PDViewerPreferences.DUPLEX_DUPLEX_FLIP_LONG_EDGE == "DuplexFlipLongEdge"


def test_boundary_constants_match_pdf_names() -> None:
    assert PDViewerPreferences.BOUNDARY_MEDIA_BOX == "MediaBox"
    assert PDViewerPreferences.BOUNDARY_CROP_BOX == "CropBox"
    assert PDViewerPreferences.BOUNDARY_BLEED_BOX == "BleedBox"
    assert PDViewerPreferences.BOUNDARY_TRIM_BOX == "TrimBox"
    assert PDViewerPreferences.BOUNDARY_ART_BOX == "ArtBox"


def test_constants_round_trip_via_cos_dictionary() -> None:
    """Setting via string constants writes the expected COSName entry."""
    p = PDViewerPreferences()
    p.set_direction(PDViewerPreferences.DIRECTION_R2L)
    p.set_non_full_screen_page_mode(PDViewerPreferences.NON_FS_USE_THUMBS)
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING_NONE)
    p.set_duplex(PDViewerPreferences.DUPLEX_DUPLEX_FLIP_LONG_EDGE)
    p.set_view_area(PDViewerPreferences.BOUNDARY_MEDIA_BOX)

    cos = p.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("Direction")) == "R2L"
    assert cos.get_name(COSName.get_pdf_name("NonFullScreenPageMode")) == "UseThumbs"
    assert cos.get_name(COSName.get_pdf_name("PrintScaling")) == "None"
    assert cos.get_name(COSName.get_pdf_name("Duplex")) == "DuplexFlipLongEdge"
    assert cos.get_name(COSName.get_pdf_name("ViewArea")) == "MediaBox"


# ---------- name-valued setters accept None to clear the entry ----------


def test_set_view_area_none_removes_entry() -> None:
    """``set_view_area(None)`` removes ``/ViewArea`` (entry-clearing parity
    with ``PDPageLabelRange.set_style(None)``). The getter then falls
    back to the spec default ``CropBox``."""
    p = PDViewerPreferences()
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    assert p.get_cos_object().contains_key(COSName.get_pdf_name("ViewArea"))
    p.set_view_area(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("ViewArea"))
    assert p.get_view_area() == "CropBox"


def test_set_view_clip_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_view_clip(PDViewerPreferences.BOUNDARY.BleedBox)
    p.set_view_clip(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("ViewClip"))


def test_set_print_area_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_print_area(PDViewerPreferences.BOUNDARY.TrimBox)
    p.set_print_area(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("PrintArea"))


def test_set_print_clip_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_print_clip(PDViewerPreferences.BOUNDARY.ArtBox)
    p.set_print_clip(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("PrintClip"))


def test_set_duplex_none_removes_entry() -> None:
    """``set_duplex(None)`` removes ``/Duplex`` — and ``get_duplex()``
    correctly returns ``None`` since /Duplex has no spec default."""
    p = PDViewerPreferences()
    p.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    assert p.get_duplex() == "Simplex"
    p.set_duplex(None)
    assert p.get_duplex() is None


def test_set_print_scaling_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    p.set_print_scaling(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("PrintScaling"))
    # Getter falls back to spec default.
    assert p.get_print_scaling() == "AppDefault"


def test_set_non_full_screen_page_mode_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    p.set_non_full_screen_page_mode(None)
    assert not p.get_cos_object().contains_key(
        COSName.get_pdf_name("NonFullScreenPageMode")
    )
    assert p.get_non_full_screen_page_mode() == "UseNone"


def test_set_reading_direction_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    p.set_reading_direction(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("Direction"))
    assert p.get_reading_direction() == "L2R"


def test_set_direction_none_removes_entry() -> None:
    """The ``set_direction`` upstream-style alias also accepts ``None``."""
    p = PDViewerPreferences()
    p.set_direction(PDViewerPreferences.DIRECTION_R2L)
    p.set_direction(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("Direction"))


# ---------- /Enforce typed list helpers ----------


def test_get_enforce_names_default_empty() -> None:
    """Absent ``/Enforce`` decodes to an empty list."""
    p = PDViewerPreferences()
    assert p.get_enforce_names() == []


def test_set_enforce_names_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling", "Duplex"])
    assert p.get_enforce_names() == ["PrintScaling", "Duplex"]
    arr = p.get_enforce()
    assert arr is not None
    assert arr.size() == 2
    assert arr.get_name(0) == "PrintScaling"
    assert arr.get_name(1) == "Duplex"


def test_set_enforce_names_none_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling"])
    assert p.get_enforce() is not None
    p.set_enforce_names(None)
    assert p.get_enforce() is None
    assert p.get_enforce_names() == []


def test_set_enforce_names_empty_removes_entry() -> None:
    p = PDViewerPreferences()
    p.set_enforce_names(["PrintScaling"])
    p.set_enforce_names([])
    assert p.get_enforce() is None


def test_get_enforce_names_skips_non_name_entries() -> None:
    """Non-/Name entries inside ``/Enforce`` are silently skipped."""
    from pypdfbox.cos import COSArray, COSInteger
    p = PDViewerPreferences()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("PrintScaling"))
    arr.add(COSInteger.get(42))  # not a name — skipped
    arr.add(COSName.get_pdf_name("Duplex"))
    p.set_enforce(arr)
    assert p.get_enforce_names() == ["PrintScaling", "Duplex"]


# ---------- /NumCopies entry-clearing and raw accessor ----------


def test_set_num_copies_none_removes_entry() -> None:
    """``set_num_copies(None)`` clears ``/NumCopies`` (parity with the
    other viewer-preference setters' ``None``-clearing semantics)."""
    p = PDViewerPreferences()
    p.set_num_copies(7)
    assert p.get_cos_object().contains_key(COSName.get_pdf_name("NumCopies"))
    p.set_num_copies(None)
    assert not p.get_cos_object().contains_key(COSName.get_pdf_name("NumCopies"))
    # After clearing, getter falls back to spec default (1).
    assert p.get_num_copies() == 1


def test_get_num_copies_raw_default_none() -> None:
    """``get_num_copies_raw`` returns ``None`` when the entry is absent —
    distinct from ``get_num_copies`` which falls back to the spec default
    of 1."""
    p = PDViewerPreferences()
    assert p.get_num_copies_raw() is None
    assert p.get_num_copies() == 1


def test_get_num_copies_raw_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_num_copies(4)
    assert p.get_num_copies_raw() == 4
    assert p.get_num_copies() == 4


def test_get_num_copies_raw_does_not_clamp_below_one() -> None:
    """Unlike ``get_num_copies`` (which clamps <1 values up to 1), the raw
    accessor returns the exact stored value so callers can detect
    malformed producer output."""
    p = PDViewerPreferences()
    p.get_cos_object().set_int(COSName.get_pdf_name("NumCopies"), 0)
    assert p.get_num_copies_raw() == 0
    assert p.get_num_copies() == 1
    p.get_cos_object().set_int(COSName.get_pdf_name("NumCopies"), -3)
    assert p.get_num_copies_raw() == -3
    assert p.get_num_copies() == 1


# ---------- typed enum-returning accessors ----------


def test_get_non_full_screen_page_mode_enum_default() -> None:
    p = PDViewerPreferences()
    assert (
        p.get_non_full_screen_page_mode_enum()
        is PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseNone
    )


def test_get_non_full_screen_page_mode_enum_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    assert (
        p.get_non_full_screen_page_mode_enum()
        is PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOC
    )
    assert (
        p.get_non_full_screen_page_mode_enum()
        is PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOC
    )


def test_get_non_full_screen_page_mode_enum_unknown_token_returns_none() -> None:
    """Producer-written non-standard tokens decode to ``None`` (callers can
    fall back to ``get_non_full_screen_page_mode`` for the raw string)."""
    p = PDViewerPreferences()
    p.get_cos_object().set_name(
        COSName.get_pdf_name("NonFullScreenPageMode"), "Bogus"
    )
    assert p.get_non_full_screen_page_mode_enum() is None
    assert p.get_non_full_screen_page_mode() == "Bogus"


def test_get_reading_direction_enum_default_l2r() -> None:
    p = PDViewerPreferences()
    assert (
        p.get_reading_direction_enum()
        is PDViewerPreferences.READING_DIRECTION.L2R
    )


def test_get_reading_direction_enum_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    assert (
        p.get_reading_direction_enum()
        is PDViewerPreferences.READING_DIRECTION.R2L
    )


def test_get_reading_direction_enum_unknown_token_returns_none() -> None:
    p = PDViewerPreferences()
    p.get_cos_object().set_name(COSName.get_pdf_name("Direction"), "TopToBottom")
    assert p.get_reading_direction_enum() is None


def test_get_view_area_enum_default_crop_box() -> None:
    p = PDViewerPreferences()
    assert p.get_view_area_enum() is PDViewerPreferences.BOUNDARY.CropBox


def test_get_view_area_enum_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    assert p.get_view_area_enum() is PDViewerPreferences.BOUNDARY.MediaBox


def test_get_view_clip_enum_default_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_view_clip_enum() is PDViewerPreferences.BOUNDARY.CropBox
    p.set_view_clip(PDViewerPreferences.BOUNDARY.BleedBox)
    assert p.get_view_clip_enum() is PDViewerPreferences.BOUNDARY.BleedBox


def test_get_print_area_enum_default_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_print_area_enum() is PDViewerPreferences.BOUNDARY.CropBox
    p.set_print_area(PDViewerPreferences.BOUNDARY.TrimBox)
    assert p.get_print_area_enum() is PDViewerPreferences.BOUNDARY.TrimBox


def test_get_print_clip_enum_default_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_print_clip_enum() is PDViewerPreferences.BOUNDARY.CropBox
    p.set_print_clip(PDViewerPreferences.BOUNDARY.ArtBox)
    assert p.get_print_clip_enum() is PDViewerPreferences.BOUNDARY.ArtBox


def test_get_view_area_enum_unknown_token_returns_none() -> None:
    p = PDViewerPreferences()
    p.get_cos_object().set_name(COSName.get_pdf_name("ViewArea"), "WeirdBox")
    assert p.get_view_area_enum() is None


def test_get_duplex_enum_default_none() -> None:
    """Mirrors ``get_duplex``: absent ``/Duplex`` returns ``None``."""
    p = PDViewerPreferences()
    assert p.get_duplex_enum() is None


def test_get_duplex_enum_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_duplex(PDViewerPreferences.DUPLEX.DuplexFlipShortEdge)
    assert (
        p.get_duplex_enum() is PDViewerPreferences.DUPLEX.DuplexFlipShortEdge
    )
    p.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    assert p.get_duplex_enum() is PDViewerPreferences.DUPLEX.Simplex


def test_get_duplex_enum_unknown_token_returns_none() -> None:
    p = PDViewerPreferences()
    p.get_cos_object().set_name(COSName.get_pdf_name("Duplex"), "Triplex")
    assert p.get_duplex_enum() is None


def test_get_print_scaling_enum_default_app_default() -> None:
    p = PDViewerPreferences()
    assert (
        p.get_print_scaling_enum()
        is PDViewerPreferences.PRINT_SCALING.AppDefault
    )


def test_get_print_scaling_enum_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    assert (
        p.get_print_scaling_enum()
        is PDViewerPreferences.PRINT_SCALING.None_
    )


def test_get_print_scaling_enum_unknown_token_returns_none() -> None:
    p = PDViewerPreferences()
    p.get_cos_object().set_name(COSName.get_pdf_name("PrintScaling"), "Custom")
    assert p.get_print_scaling_enum() is None
