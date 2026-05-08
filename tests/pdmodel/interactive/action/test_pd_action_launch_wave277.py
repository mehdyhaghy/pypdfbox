from __future__ import annotations

import pytest

from pypdfbox.cos import COSBoolean, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)

_F = COSName.get_pdf_name("F")
_D = COSName.D  # type: ignore[attr-defined]
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")
_NEW_WINDOW = COSName.get_pdf_name("NewWindow")
_WIN = COSName.get_pdf_name("Win")


def test_file_accessors_share_simple_string_form_and_clear() -> None:
    action = PDActionLaunch()

    action.set_f("viewer.exe")
    assert action.get_f() == "viewer.exe"

    resolved = action.get_file()
    assert isinstance(resolved, PDSimpleFileSpecification)
    assert resolved.get_file() == "viewer.exe"

    fs = PDSimpleFileSpecification()
    fs.set_file("manual.pdf")
    action.set_file(fs)
    assert action.get_f() == "manual.pdf"
    assert action.get_cos_object().get_dictionary_object(_F) is fs.get_cos_object()

    action.set_f(None)
    assert action.get_f() is None
    assert action.get_file() is None
    assert _F not in action.get_cos_object()


def test_open_mode_bool_and_predicates_preserve_absent_explicit_false() -> None:
    action = PDActionLaunch()
    assert action.get_open_in_new_window() is False
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE
    assert action.is_open_in_user_preference() is True
    assert action.is_open_in_same_window() is False
    assert action.is_open_in_new_window() is False

    action.set_open_in_new_window(False)
    assert action.get_open_in_new_window() is False
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
    assert action.is_open_in_same_window() is True
    assert action.is_open_in_user_preference() is False

    action.set_open_in_new_window(True)
    assert action.get_open_in_new_window() is True
    assert action.should_open_in_new_window() is True
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
    assert action.is_open_in_new_window() is True

    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert _NEW_WINDOW not in action.get_cos_object()
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_windows_params_defaults_clear_and_backing_cos_identity() -> None:
    params = PDWindowsLaunchParams()
    assert params.get_filename() is None
    assert params.get_directory() is None
    assert params.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN
    assert params.has_operation() is False
    assert params.is_open_operation() is True
    assert params.get_execute_param() is None

    params.set_filename("notepad.exe")
    params.set_directory("C:\\Temp")
    params.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    params.set_execute_param("/p readme.txt")

    action = PDActionLaunch()
    action.set_win_launch_params(params)
    assert action.get_cos_object().get_dictionary_object(_WIN) is params.get_cos_object()

    resolved = action.get_win_launch_params()
    assert isinstance(resolved, PDWindowsLaunchParams)
    assert resolved.get_cos_object() is params.get_cos_object()
    assert resolved.get_filename() == "notepad.exe"
    assert resolved.get_directory() == "C:\\Temp"
    assert resolved.get_operation() == PDWindowsLaunchParams.OPERATION_PRINT
    assert resolved.is_print_operation() is True
    assert resolved.get_execute_param() == "/p readme.txt"

    resolved.set_operation(None)
    resolved.set_execute_param(None)
    assert _O not in params.get_cos_object()
    assert _P not in params.get_cos_object()
    assert params.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN

    action.set_win_launch_params(None)
    assert action.get_win_launch_params() is None
    assert _WIN not in action.get_cos_object()


def test_launch_action_cos_round_trip_wraps_existing_shape() -> None:
    raw_win = COSDictionary()
    raw_win.set_string(_F, "calc.exe")
    raw_win.set_string(_D, "C:\\Windows\\System32")
    raw_win.set_string(_O, PDWindowsLaunchParams.OPERATION_OPEN)
    raw_win.set_string(_P, "/A")

    raw_action = COSDictionary()
    raw_action.set_name("Type", "Action")
    raw_action.set_name("S", "Launch")
    raw_action.set_string(_F, "document.pdf")
    raw_action.set_string(_D, "/Applications/Preview.app")
    raw_action.set_string(_O, "print")
    raw_action.set_string(_P, "--silent")
    raw_action.set_boolean(_NEW_WINDOW, True)
    raw_action.set_item(_WIN, raw_win)

    action = PDActionLaunch(raw_action)
    assert action.get_cos_object() is raw_action
    assert action.get_f() == "document.pdf"
    assert action.get_d() == "/Applications/Preview.app"
    assert action.get_o() == "print"
    assert action.get_p() == "--silent"
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW

    file_spec = action.get_file()
    assert isinstance(file_spec, PDSimpleFileSpecification)
    assert file_spec.get_file() == "document.pdf"

    win = action.get_win_launch_params()
    assert isinstance(win, PDWindowsLaunchParams)
    assert win.get_cos_object() is raw_win
    assert win.get_filename() == "calc.exe"
    assert win.get_directory() == "C:\\Windows\\System32"
    assert win.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN
    assert win.get_execute_param() == "/A"

    win.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    assert raw_win.get_string(_O) == PDWindowsLaunchParams.OPERATION_PRINT


def test_malformed_cos_shapes_are_ignored_or_reported_narrowly() -> None:
    action = PDActionLaunch()
    action.get_cos_object().set_item(_NEW_WINDOW, COSString("true"))
    assert action.get_open_in_new_window() is False
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE
    assert action.is_open_in_user_preference() is True

    action.get_cos_object().set_item(_WIN, COSString("not-a-dict"))
    assert action.get_win_launch_params() is None

    action.get_cos_object().set_item(_F, COSBoolean.TRUE)
    with pytest.raises(OSError, match="Unknown file specification"):
        action.get_file()


def test_malformed_windows_param_fields_fall_back_per_typed_getters() -> None:
    raw = COSDictionary()
    raw.set_item(_F, COSBoolean.TRUE)
    raw.set_item(_D, COSBoolean.FALSE)
    raw.set_item(_O, COSBoolean.FALSE)
    raw.set_item(_P, COSBoolean.TRUE)

    params = PDWindowsLaunchParams(raw)
    assert params.get_filename() is None
    assert params.get_directory() is None
    assert params.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN
    assert params.has_operation() is True
    assert params.is_open_operation() is True
    assert params.is_print_operation() is False
    assert params.get_execute_param() is None
