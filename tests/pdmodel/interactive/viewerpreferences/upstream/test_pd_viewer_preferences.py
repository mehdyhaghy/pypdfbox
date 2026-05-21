"""Upstream-parity port for ``PDViewerPreferences``.

Mirrors ``PDViewerPreferences.java`` (PDFBox 3.0.x). Upstream ships no
JUnit test under ``pdfbox/src/test/java/.../viewerpreferences/`` (the
directory itself doesn't exist) — this module ports the source's
behavioural contract: the boolean-flag accessors with their spec
defaults, the name-valued accessors with their documented defaults
(``UseNone``, ``L2R``, ``CropBox``, ``AppDefault``), and the named
enum values from PDF 32000-1 §12.2 Table 150.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences

_HIDE_TOOLBAR = COSName.get_pdf_name("HideToolbar")
_HIDE_MENUBAR = COSName.get_pdf_name("HideMenubar")
_HIDE_WINDOW_UI = COSName.get_pdf_name("HideWindowUI")
_FIT_WINDOW = COSName.get_pdf_name("FitWindow")
_CENTER_WINDOW = COSName.get_pdf_name("CenterWindow")
_DISPLAY_DOC_TITLE = COSName.get_pdf_name("DisplayDocTitle")
_NON_FULL_SCREEN_PAGE_MODE = COSName.get_pdf_name("NonFullScreenPageMode")
_DIRECTION = COSName.get_pdf_name("Direction")
_VIEW_AREA = COSName.get_pdf_name("ViewArea")
_VIEW_CLIP = COSName.get_pdf_name("ViewClip")
_PRINT_AREA = COSName.get_pdf_name("PrintArea")
_PRINT_CLIP = COSName.get_pdf_name("PrintClip")
_DUPLEX = COSName.get_pdf_name("Duplex")
_PRINT_SCALING = COSName.get_pdf_name("PrintScaling")


def _make() -> PDViewerPreferences:
    return PDViewerPreferences(COSDictionary())


def test_get_cos_object_returns_wrapped_dict():
    # Upstream: ``getCOSObject()`` returns the wrapped dict instance.
    d = COSDictionary()
    prefs = PDViewerPreferences(d)
    assert prefs.get_cos_object() is d


def test_hide_toolbar_defaults_false_and_round_trips():
    prefs = _make()
    assert prefs.is_hide_toolbar() is False
    assert prefs.get_hide_toolbar() is False
    prefs.set_hide_toolbar(True)
    assert prefs.is_hide_toolbar() is True
    assert prefs.get_cos_object().get_boolean(_HIDE_TOOLBAR, False) is True


def test_hide_menubar_defaults_false_and_round_trips():
    prefs = _make()
    assert prefs.is_hide_menubar() is False
    prefs.set_hide_menubar(True)
    assert prefs.is_hide_menubar() is True
    assert prefs.get_cos_object().get_boolean(_HIDE_MENUBAR, False) is True


def test_hide_window_ui_defaults_false_and_round_trips():
    prefs = _make()
    assert prefs.is_hide_window_ui() is False
    prefs.set_hide_window_ui(True)
    assert prefs.is_hide_window_ui() is True


def test_fit_window_defaults_false_and_round_trips():
    prefs = _make()
    assert prefs.is_fit_window() is False
    prefs.set_fit_window(True)
    assert prefs.is_fit_window() is True


def test_center_window_defaults_false_and_round_trips():
    prefs = _make()
    assert prefs.is_center_window() is False
    prefs.set_center_window(True)
    assert prefs.is_center_window() is True


def test_display_doc_title_defaults_false_and_round_trips():
    prefs = _make()
    assert prefs.is_display_doc_title() is False
    prefs.set_display_doc_title(True)
    assert prefs.is_display_doc_title() is True


def test_non_full_screen_page_mode_default_use_none():
    # Upstream's `getNonFullScreenPageMode` returns NON_FULL_SCREEN_PAGE_MODE.UseNone
    # when /NonFullScreenPageMode is absent.
    prefs = _make()
    assert prefs.get_non_full_screen_page_mode() == "UseNone"


def test_non_full_screen_page_mode_round_trip_with_enum():
    prefs = _make()
    prefs.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    assert prefs.get_non_full_screen_page_mode() == "UseOutlines"
    prefs.set_non_full_screen_page_mode("UseThumbs")
    assert prefs.get_non_full_screen_page_mode() == "UseThumbs"
    prefs.set_non_full_screen_page_mode("UseOC")
    assert prefs.get_non_full_screen_page_mode() == "UseOC"


def test_reading_direction_default_l2r():
    prefs = _make()
    assert prefs.get_reading_direction() == "L2R"
    assert prefs.get_direction() == "L2R"


def test_reading_direction_round_trip():
    prefs = _make()
    prefs.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    assert prefs.get_reading_direction() == "R2L"
    prefs.set_direction("L2R")
    assert prefs.get_direction() == "L2R"


def test_view_area_default_crop_box():
    # Upstream returns BOUNDARY.CropBox by default.
    prefs = _make()
    assert prefs.get_view_area() == "CropBox"


def test_view_area_round_trip_each_boundary():
    prefs = _make()
    for name in ("MediaBox", "CropBox", "BleedBox", "TrimBox", "ArtBox"):
        prefs.set_view_area(name)
        assert prefs.get_view_area() == name


def test_view_clip_default_crop_box():
    prefs = _make()
    assert prefs.get_view_clip() == "CropBox"
    prefs.set_view_clip(PDViewerPreferences.BOUNDARY.TrimBox)
    assert prefs.get_view_clip() == "TrimBox"


def test_print_area_default_crop_box():
    prefs = _make()
    assert prefs.get_print_area() == "CropBox"
    prefs.set_print_area(PDViewerPreferences.BOUNDARY.MediaBox)
    assert prefs.get_print_area() == "MediaBox"


def test_print_clip_default_crop_box():
    prefs = _make()
    assert prefs.get_print_clip() == "CropBox"
    prefs.set_print_clip("BleedBox")
    assert prefs.get_print_clip() == "BleedBox"


def test_duplex_default_none():
    # Upstream returns null when /Duplex is absent (no spec default).
    prefs = _make()
    assert prefs.get_duplex() is None


def test_duplex_round_trip_each_value():
    prefs = _make()
    for name in (
        PDViewerPreferences.DUPLEX.Simplex,
        PDViewerPreferences.DUPLEX.DuplexFlipShortEdge,
        PDViewerPreferences.DUPLEX.DuplexFlipLongEdge,
    ):
        prefs.set_duplex(name)
        assert prefs.get_duplex() == str(name)


def test_print_scaling_default_app_default():
    prefs = _make()
    assert prefs.get_print_scaling() == "AppDefault"


def test_print_scaling_round_trip_none_value():
    # PDF 32000-1 print-scaling 'None' is reserved in Python — exposed
    # as the enum member ``None_``.
    prefs = _make()
    prefs.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    assert prefs.get_print_scaling() == "None"


def test_clear_individual_entries_removes_them():
    prefs = _make()
    prefs.set_hide_toolbar(True)
    prefs.set_view_area("MediaBox")
    assert prefs.get_cos_object().contains_key(_HIDE_TOOLBAR)
    assert prefs.get_cos_object().contains_key(_VIEW_AREA)
    prefs.clear_hide_toolbar()
    prefs.clear_view_area()
    assert not prefs.get_cos_object().contains_key(_HIDE_TOOLBAR)
    assert not prefs.get_cos_object().contains_key(_VIEW_AREA)


def test_set_to_none_removes_entry():
    # Upstream tolerates a null write — pypdfbox removes the entry.
    prefs = _make()
    prefs.set_non_full_screen_page_mode("UseOutlines")
    assert prefs.get_cos_object().contains_key(_NON_FULL_SCREEN_PAGE_MODE)
    prefs.set_non_full_screen_page_mode(None)
    assert not prefs.get_cos_object().contains_key(_NON_FULL_SCREEN_PAGE_MODE)


def test_class_level_string_constants_match_spec():
    # Per PDF 32000-1 §12.2 Table 150, the name tokens map to:
    assert PDViewerPreferences.NON_FS_USE_NONE == "UseNone"
    assert PDViewerPreferences.NON_FS_USE_OUTLINES == "UseOutlines"
    assert PDViewerPreferences.NON_FS_USE_THUMBS == "UseThumbs"
    assert PDViewerPreferences.NON_FS_USE_OC == "UseOC"
    assert PDViewerPreferences.DIRECTION_L2R == "L2R"
    assert PDViewerPreferences.DIRECTION_R2L == "R2L"
    assert PDViewerPreferences.PRINT_SCALING_NONE == "None"
    assert PDViewerPreferences.PRINT_SCALING_APPDEFAULT == "AppDefault"
    assert PDViewerPreferences.BOUNDARY_MEDIA_BOX == "MediaBox"
    assert PDViewerPreferences.BOUNDARY_CROP_BOX == "CropBox"
    assert PDViewerPreferences.BOUNDARY_BLEED_BOX == "BleedBox"
    assert PDViewerPreferences.BOUNDARY_TRIM_BOX == "TrimBox"
    assert PDViewerPreferences.BOUNDARY_ART_BOX == "ArtBox"
    assert PDViewerPreferences.DUPLEX_SIMPLEX == "Simplex"
    assert PDViewerPreferences.DUPLEX_DUPLEX_FLIP_SHORT_EDGE == "DuplexFlipShortEdge"
    assert PDViewerPreferences.DUPLEX_DUPLEX_FLIP_LONG_EDGE == "DuplexFlipLongEdge"
