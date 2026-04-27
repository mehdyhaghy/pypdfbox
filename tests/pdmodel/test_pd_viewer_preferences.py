from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
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
    assert p.pick_tray_by_pdf_size() is False


def test_boolean_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_hide_menubar(True)
    p.set_hide_window_ui(True)
    p.set_fit_window(True)
    p.set_center_window(True)
    p.set_display_doc_title(True)
    p.set_pick_tray_by_pdf_size(True)
    assert p.hide_toolbar()
    assert p.hide_menubar()
    assert p.hide_window_ui()
    assert p.fit_window()
    assert p.center_window()
    assert p.display_doc_title()
    assert p.pick_tray_by_pdf_size()


def test_non_full_screen_page_mode_default_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_non_full_screen_page_mode() == "UseNone"
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    assert p.get_non_full_screen_page_mode() == "UseOutlines"
    p.set_non_full_screen_page_mode("UseThumbs")
    assert p.get_non_full_screen_page_mode() == "UseThumbs"
    p.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOC
    )
    assert p.get_non_full_screen_page_mode() == "UseOC"


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
    p.set_duplex(PDViewerPreferences.DUPLEX.DuplexFlipLongEdge)
    assert p.get_duplex() == "DuplexFlipLongEdge"
    p.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    assert p.get_duplex() == "Simplex"


def test_print_scaling_default_app_default() -> None:
    p = PDViewerPreferences()
    assert p.get_print_scaling() == "AppDefault"
    p.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    assert p.get_print_scaling() == "None"


def test_num_copies_default_one_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_num_copies() == 1
    p.set_num_copies(5)
    assert p.get_num_copies() == 5
    cos = p.get_cos_object()
    assert cos.contains_key(COSName.get_pdf_name("NumCopies"))


def test_print_page_range_default_none_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_print_page_range() is None
    arr = COSArray.of_cos_integers([1, 3, 5, 7])
    p.set_print_page_range(arr)
    fetched = p.get_print_page_range()
    assert fetched is not None
    assert fetched.size() == 4
    assert fetched.get_int(0) == 1
    assert fetched.get_int(1) == 3
    assert fetched.get_int(2) == 5
    assert fetched.get_int(3) == 7
    p.set_print_page_range(None)
    assert p.get_print_page_range() is None


def test_enforce_default_none_and_round_trip() -> None:
    p = PDViewerPreferences()
    assert p.get_enforce() is None
    arr = COSArray.of_cos_names(["PrintScaling"])
    p.set_enforce(arr)
    fetched = p.get_enforce()
    assert fetched is not None
    assert fetched.size() == 1
    assert fetched.get_name(0) == "PrintScaling"
    p.set_enforce(None)
    assert p.get_enforce() is None


def test_underlying_dict_keys_match_pdf_names() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    p.set_pick_tray_by_pdf_size(True)
    p.set_num_copies(2)
    cos = p.get_cos_object()
    assert cos.contains_key(COSName.get_pdf_name("HideToolbar"))
    assert cos.contains_key(COSName.get_pdf_name("ViewArea"))
    assert cos.contains_key(COSName.get_pdf_name("PickTrayByPDFSize"))
    assert cos.contains_key(COSName.get_pdf_name("NumCopies"))


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


def test_get_boolean_accessors_default_false() -> None:
    p = PDViewerPreferences()
    assert p.get_hide_toolbar() is False
    assert p.get_hide_menubar() is False
    assert p.get_hide_window_ui() is False
    assert p.get_fit_window() is False
    assert p.get_center_window() is False
    assert p.get_display_doc_title() is False
    assert p.get_pick_tray_by_pdf_size() is False


def test_get_boolean_accessors_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_hide_menubar(True)
    p.set_hide_window_ui(True)
    p.set_fit_window(True)
    p.set_center_window(True)
    p.set_display_doc_title(True)
    p.set_pick_tray_by_pdf_size(True)
    assert p.get_hide_toolbar() is True
    assert p.get_hide_menubar() is True
    assert p.get_hide_window_ui() is True
    assert p.get_fit_window() is True
    assert p.get_center_window() is True
    assert p.get_display_doc_title() is True
    assert p.get_pick_tray_by_pdf_size() is True


def test_get_boolean_accessors_track_legacy_forms() -> None:
    p = PDViewerPreferences()
    p.set_hide_toolbar(True)
    p.set_fit_window(True)
    assert p.get_hide_toolbar() == p.hide_toolbar() == p.is_hide_toolbar()
    assert p.get_fit_window() == p.fit_window() == p.is_fit_window()


def test_print_page_range_pairs_empty_default() -> None:
    p = PDViewerPreferences()
    assert p.get_print_page_range_pairs() == []


def test_print_page_range_pairs_round_trip() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(1, 3), (5, 7), (10, 10)])
    assert p.get_print_page_range_pairs() == [(1, 3), (5, 7), (10, 10)]
    arr = p.get_print_page_range()
    assert arr is not None
    assert arr.size() == 6
    assert arr.get_int(0) == 1
    assert arr.get_int(1) == 3
    assert arr.get_int(4) == 10


def test_print_page_range_pairs_set_none_removes() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(1, 5)])
    assert p.get_print_page_range() is not None
    p.set_print_page_range_pairs(None)
    assert p.get_print_page_range() is None
    assert p.get_print_page_range_pairs() == []


def test_print_page_range_pairs_set_empty_removes() -> None:
    p = PDViewerPreferences()
    p.set_print_page_range_pairs([(2, 4)])
    p.set_print_page_range_pairs([])
    assert p.get_print_page_range() is None


def test_print_page_range_pairs_odd_length_returns_empty() -> None:
    """Odd-length /PrintPageRange arrays are invalid per PDF 32000-2 §12.4.4."""
    p = PDViewerPreferences()
    arr = COSArray.of_cos_integers([1, 3, 5])
    p.set_print_page_range(arr)
    assert p.get_print_page_range_pairs() == []


def test_set_view_area_with_string() -> None:
    """Verify set_view_area(name) accepts a plain string."""
    p = PDViewerPreferences()
    p.set_view_area("BleedBox")
    assert p.get_view_area() == "BleedBox"


def test_num_copies_clamps_below_one() -> None:
    """Per PDF 32000-1 Table 150, /NumCopies < 1 must be treated as 1."""
    p = PDViewerPreferences()
    p.get_cos_object().set_int(COSName.get_pdf_name("NumCopies"), 0)
    assert p.get_num_copies() == 1
    p.get_cos_object().set_int(COSName.get_pdf_name("NumCopies"), -3)
    assert p.get_num_copies() == 1


def test_construct_from_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_boolean(COSName.get_pdf_name("HideToolbar"), True)
    raw.set_name(COSName.get_pdf_name("ViewArea"), "BleedBox")
    raw.set_int(COSName.get_pdf_name("NumCopies"), 4)
    range_arr = COSArray()
    range_arr.add(COSInteger.get(2))
    range_arr.add(COSInteger.get(6))
    raw.set_item(COSName.get_pdf_name("PrintPageRange"), range_arr)
    p = PDViewerPreferences(raw)
    assert p.hide_toolbar()
    assert p.get_view_area() == "BleedBox"
    assert p.get_num_copies() == 4
    fetched = p.get_print_page_range()
    assert fetched is not None
    assert fetched.size() == 2
    assert fetched.get_int(0) == 2
    assert fetched.get_int(1) == 6
