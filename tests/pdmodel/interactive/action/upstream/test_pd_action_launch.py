"""Upstream-parity port for ``PDActionLaunch``.

Mirrors ``PDActionLaunch.java`` (PDFBox 3.0.x). Upstream ships no JUnit
test for the launch action wrapper — this module ports the source's
behavioural contract: SUB_TYPE stamp, /F /D /O /P windows-launch
parameter pairs, /Win sub-dict, and the tri-state /NewWindow flag
mapping to OpenMode.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)

_S = COSName.get_pdf_name("S")
_NEW_WINDOW = COSName.get_pdf_name("NewWindow")
_F = COSName.get_pdf_name("F")
_WIN = COSName.get_pdf_name("Win")


def test_default_constructor_stamps_subtype():
    action = PDActionLaunch()
    assert action.get_sub_type() == "Launch"
    assert action.get_cos_object().get_name(_S) == "Launch"


def test_f_d_o_p_string_accessors_round_trip():
    action = PDActionLaunch()
    assert action.get_f() is None
    assert action.get_d() is None
    assert action.get_o() is None
    assert action.get_p() is None
    action.set_f("notepad.exe")
    action.set_d("C:\\")
    action.set_o("open")
    action.set_p("/A")
    assert action.get_f() == "notepad.exe"
    assert action.get_d() == "C:\\"
    assert action.get_o() == "open"
    assert action.get_p() == "/A"


def test_win_launch_params_get_set_round_trip():
    action = PDActionLaunch()
    assert action.get_win_launch_params() is None
    win = PDWindowsLaunchParams()
    win.set_filename("notepad.exe")
    action.set_win_launch_params(win)
    fetched = action.get_win_launch_params()
    assert isinstance(fetched, PDWindowsLaunchParams)
    assert fetched.get_filename() == "notepad.exe"


def test_set_win_launch_params_none_removes_entry():
    action = PDActionLaunch()
    win = PDWindowsLaunchParams()
    action.set_win_launch_params(win)
    assert action.get_cos_object().contains_key(_WIN)
    action.set_win_launch_params(None)
    assert not action.get_cos_object().contains_key(_WIN)


def test_open_in_new_window_default_user_preference():
    # Upstream: absent /NewWindow → OpenMode.USER_PREFERENCE.
    action = PDActionLaunch()
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_open_in_new_window_true_round_trip_to_new_window():
    action = PDActionLaunch()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
    assert action.get_cos_object().get_boolean(_NEW_WINDOW, False) is True


def test_open_in_new_window_false_round_trip_to_same_window():
    action = PDActionLaunch()
    action.set_open_in_new_window(OpenMode.SAME_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
    assert action.get_cos_object().get_boolean(_NEW_WINDOW, True) is False


def test_open_in_new_window_user_preference_removes_entry():
    action = PDActionLaunch()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.get_cos_object().contains_key(_NEW_WINDOW)
    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert not action.get_cos_object().contains_key(_NEW_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_open_in_new_window_none_removes_entry():
    # Upstream's setOpenInNewWindow(null) also removes the entry.
    action = PDActionLaunch()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    action.set_open_in_new_window(None)
    assert not action.get_cos_object().contains_key(_NEW_WINDOW)


def test_sub_type_constant_equals_launch():
    assert PDActionLaunch.SUB_TYPE == "Launch"
