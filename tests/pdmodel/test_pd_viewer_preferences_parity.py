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
