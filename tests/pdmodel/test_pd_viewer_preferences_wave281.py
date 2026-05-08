from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel import PDViewerPreferences


def test_boolean_has_predicates_track_explicit_false_wave281() -> None:
    prefs = PDViewerPreferences()

    assert prefs.hide_toolbar() is False
    assert prefs.has_hide_toolbar() is False

    prefs.set_hide_toolbar(False)

    assert prefs.hide_toolbar() is False
    assert prefs.has_hide_toolbar() is True

    prefs.clear_hide_toolbar()

    assert prefs.hide_toolbar() is False
    assert prefs.has_hide_toolbar() is False


def test_all_boolean_clear_helpers_remove_entries_wave281() -> None:
    prefs = PDViewerPreferences()
    prefs.set_hide_toolbar(True)
    prefs.set_hide_menubar(True)
    prefs.set_hide_window_ui(True)
    prefs.set_fit_window(True)
    prefs.set_center_window(True)
    prefs.set_display_doc_title(True)
    prefs.set_pick_tray_by_pdf_size(True)

    prefs.clear_hide_toolbar()
    prefs.clear_hide_menubar()
    prefs.clear_hide_window_ui()
    prefs.clear_fit_window()
    prefs.clear_center_window()
    prefs.clear_display_doc_title()
    prefs.clear_pick_tray_by_pdf_size()

    assert not prefs.has_hide_toolbar()
    assert not prefs.has_hide_menubar()
    assert not prefs.has_hide_window_ui()
    assert not prefs.has_fit_window()
    assert not prefs.has_center_window()
    assert not prefs.has_display_doc_title()
    assert not prefs.has_pick_tray_by_pdf_size()


@pytest.mark.parametrize(
    ("setter", "clearer", "haser", "default"),
    [
        (
            "set_non_full_screen_page_mode",
            "clear_non_full_screen_page_mode",
            "has_non_full_screen_page_mode",
            "UseNone",
        ),
        ("set_direction", "clear_direction", "has_direction", "L2R"),
        ("set_view_area", "clear_view_area", "has_view_area", "CropBox"),
        ("set_view_clip", "clear_view_clip", "has_view_clip", "CropBox"),
        ("set_print_area", "clear_print_area", "has_print_area", "CropBox"),
        ("set_print_clip", "clear_print_clip", "has_print_clip", "CropBox"),
        ("set_duplex", "clear_duplex", "has_duplex", None),
        ("set_print_scaling", "clear_print_scaling", "has_print_scaling", "AppDefault"),
    ],
)
def test_name_clear_helpers_remove_entries_wave281(
    setter: str, clearer: str, haser: str, default: str | None
) -> None:
    prefs = PDViewerPreferences()

    getattr(prefs, setter)("Custom")
    assert getattr(prefs, haser)() is True

    getattr(prefs, clearer)()

    assert getattr(prefs, haser)() is False
    if setter == "set_duplex":
        assert prefs.get_duplex() == default
    elif setter == "set_non_full_screen_page_mode":
        assert prefs.get_non_full_screen_page_mode() == default
    elif setter == "set_direction":
        assert prefs.get_direction() == default
    elif setter == "set_print_scaling":
        assert prefs.get_print_scaling() == default
    elif "view_area" in setter:
        assert prefs.get_view_area() == default
    elif "view_clip" in setter:
        assert prefs.get_view_clip() == default
    elif "print_area" in setter:
        assert prefs.get_print_area() == default
    else:
        assert prefs.get_print_clip() == default


def test_reading_direction_clear_alias_wave281() -> None:
    prefs = PDViewerPreferences()
    prefs.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)

    prefs.clear_reading_direction()

    assert prefs.has_direction() is False
    assert prefs.get_reading_direction() == "L2R"


def test_malformed_print_page_range_non_integer_is_ignored_wave281() -> None:
    prefs = PDViewerPreferences()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSName.get_pdf_name("NotAnInteger"))
    prefs.set_print_page_range(arr)

    assert prefs.get_print_page_range_pairs() == []
    assert prefs.get_print_page_range_pair_count() == 0
    assert prefs.is_valid_print_page_range() is False
