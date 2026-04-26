from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDViewerPreferences


def test_default_construction_yields_empty_dict() -> None:
    p = PDViewerPreferences()
    assert p.get_cos_object().is_empty()


def test_boolean_defaults_are_false() -> None:
    p = PDViewerPreferences()
    assert p.hide_toolbar() is False
    assert p.hide_menubar() is False
    assert p.hide_window_ui() is False
    assert p.fit_window() is False
    assert p.center_window() is False
    assert p.display_doc_title() is False


def test_boolean_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_hide_menubar(True)
    p.set_hide_window_ui(True)
    p.set_fit_window(True)
    p.set_center_window(True)
    p.set_display_doc_title(True)
    assert p.hide_toolbar()
    assert p.hide_menubar()
    assert p.hide_window_ui()
    assert p.fit_window()
    assert p.center_window()
    assert p.display_doc_title()


def test_non_full_screen_page_mode_default_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_non_full_screen_page_mode() == "UseNone"
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    assert p.get_non_full_screen_page_mode() == "UseOutlines"
    p.set_non_full_screen_page_mode("UseThumbs")
    assert p.get_non_full_screen_page_mode() == "UseThumbs"


def test_reading_direction_default_l2r() -> None:
    p = PDViewerPreferences()
    assert p.get_reading_direction() == "L2R"
    p.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    assert p.get_reading_direction() == "R2L"


def test_boundary_defaults_crop_box() -> None:
    p = PDViewerPreferences()
    assert p.get_view_area() == "CropBox"
    assert p.get_view_clip() == "CropBox"
    assert p.get_print_area() == "CropBox"
    assert p.get_print_clip() == "CropBox"


def test_boundary_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    p.set_view_clip(PDViewerPreferences.BOUNDARY.BleedBox)
    p.set_print_area(PDViewerPreferences.BOUNDARY.TrimBox)
    p.set_print_clip(PDViewerPreferences.BOUNDARY.ArtBox)
    assert p.get_view_area() == "MediaBox"
    assert p.get_view_clip() == "BleedBox"
    assert p.get_print_area() == "TrimBox"
    assert p.get_print_clip() == "ArtBox"


def test_duplex_no_default() -> None:
    p = PDViewerPreferences()
    # Upstream returns null when /Duplex is absent (no spec default).
    assert p.get_duplex() is None
    p.set_duplex(PDViewerPreferences.DUPLEX.DuplexFlipShortEdge)
    assert p.get_duplex() == "DuplexFlipShortEdge"


def test_print_scaling_default_app_default() -> None:
    p = PDViewerPreferences()
    assert p.get_print_scaling() == "AppDefault"
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    assert p.get_print_scaling() == "None"


def test_underlying_dict_keys_match_pdf_names() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    cos = p.get_cos_object()
    assert cos.contains_key(COSName.get_pdf_name("HideToolbar"))
    assert cos.contains_key(COSName.get_pdf_name("ViewArea"))


def test_catalog_set_get_round_trip() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    p = PDViewerPreferences()
    p.set_fit_window(True)
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    cat.set_viewer_preferences(p)
    fetched = cat.get_viewer_preferences()
    assert fetched is not None
    assert fetched.fit_window()
    assert fetched.get_view_area() == "MediaBox"


def test_catalog_set_none_removes_entry() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    cat.set_viewer_preferences(PDViewerPreferences())
    cat.set_viewer_preferences(None)
    assert cat.get_viewer_preferences() is None


def test_construct_from_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_boolean(COSName.get_pdf_name("HideToolbar"), True)
    raw.set_name(COSName.get_pdf_name("ViewArea"), "BleedBox")
    p = PDViewerPreferences(raw)
    assert p.hide_toolbar()
    assert p.get_view_area() == "BleedBox"
