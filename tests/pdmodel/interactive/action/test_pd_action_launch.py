"""Tests for ``PDActionLaunch`` — PDF 32000-1 §12.6.4.5 Table 196 +
WinLaunchParameters Table 197."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch


def test_defaults_on_fresh_action() -> None:
    action = PDActionLaunch()
    assert action.get_sub_type() == "Launch"
    assert action.get_file() is None
    assert action.get_d() is None
    assert action.get_o() is None
    assert action.get_p() is None
    assert action.get_open_in_new_window() is False
    assert action.get_win_launch_params() is None


def test_round_trip_simple_file_spec() -> None:
    action = PDActionLaunch()
    fs = PDSimpleFileSpecification()
    fs.set_file("notepad.exe")
    action.set_file(fs)

    resolved = action.get_file()
    assert isinstance(resolved, PDSimpleFileSpecification)
    assert resolved.get_file() == "notepad.exe"


def test_round_trip_complex_file_spec() -> None:
    action = PDActionLaunch()
    fs = PDComplexFileSpecification()
    fs.set_file("readme.txt")
    action.set_file(fs)

    resolved = action.get_file()
    assert isinstance(resolved, PDComplexFileSpecification)
    assert resolved.get_file() == "readme.txt"


def test_set_file_none_removes_entry() -> None:
    action = PDActionLaunch()
    fs = PDSimpleFileSpecification()
    fs.set_file("foo.exe")
    action.set_file(fs)
    assert action.get_file() is not None

    action.set_file(None)
    assert action.get_file() is None
    assert COSName.get_pdf_name("F") not in action.get_cos_object()


def test_round_trip_d_o_p_text_strings() -> None:
    action = PDActionLaunch()
    action.set_d("/Applications/Preview.app")
    action.set_o("print")
    action.set_p("--silent --copies=2")

    assert action.get_d() == "/Applications/Preview.app"
    assert action.get_o() == "print"
    assert action.get_p() == "--silent --copies=2"

    action.set_d(None)
    action.set_o(None)
    action.set_p(None)
    assert action.get_d() is None
    assert action.get_o() is None
    assert action.get_p() is None


def test_open_in_new_window_toggle_round_trip() -> None:
    action = PDActionLaunch()
    assert action.get_open_in_new_window() is False

    action.set_open_in_new_window(True)
    assert action.get_open_in_new_window() is True

    action.set_open_in_new_window(False)
    assert action.get_open_in_new_window() is False


def test_win_launch_params_round_trip_raw_dict() -> None:
    action = PDActionLaunch()
    win = COSDictionary()
    win.set_item(COSName.get_pdf_name("F"), COSString("notepad.exe"))
    win.set_item(COSName.get_pdf_name("D"), COSString("C:\\\\Users"))
    win.set_item(COSName.get_pdf_name("O"), COSString("open"))
    win.set_item(COSName.get_pdf_name("P"), COSString("/A"))
    action.set_win_launch_params(win)

    resolved = action.get_win_launch_params()
    assert isinstance(resolved, COSDictionary)
    assert resolved is win
    assert resolved.get_string("F") == "notepad.exe"
    assert resolved.get_string("O") == "open"

    action.set_win_launch_params(None)
    assert action.get_win_launch_params() is None
    assert COSName.get_pdf_name("Win") not in action.get_cos_object()


def test_existing_dict_wraps_without_resetting_subtype() -> None:
    raw = COSDictionary()
    raw.set_name("Type", "Action")
    raw.set_name("S", "Launch")
    raw.set_string("D", "preview")
    raw.set_boolean("NewWindow", True)

    action = PDActionLaunch(raw)
    assert action.get_sub_type() == "Launch"
    assert action.get_d() == "preview"
    assert action.get_open_in_new_window() is True
    assert action.get_cos_object() is raw
