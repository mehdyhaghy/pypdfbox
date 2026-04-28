from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSName
from pypdfbox.pdmodel.interactive.action import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)


_NEW_WINDOW = COSName.get_pdf_name("NewWindow")


# ---------- OpenMode enum identity ----------


def test_open_mode_has_three_states() -> None:
    """OpenMode mirrors upstream's three discrete states."""
    assert {m.name for m in OpenMode} == {
        "USER_PREFERENCE",
        "SAME_WINDOW",
        "NEW_WINDOW",
    }


# ---------- PDActionLaunch tri-state ----------


def test_launch_open_in_new_window_mode_absent_is_user_preference() -> None:
    """An action without /NewWindow defaults to USER_PREFERENCE in the
    upstream tri-state surface."""
    action = PDActionLaunch()
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE
    # Bool surface keeps the historical False default for back-compat.
    assert action.get_open_in_new_window() is False


def test_launch_open_in_new_window_mode_round_trip() -> None:
    action = PDActionLaunch()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
    assert action.get_open_in_new_window() is True
    assert action.is_new_window() is True

    action.set_open_in_new_window(OpenMode.SAME_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
    assert action.get_open_in_new_window() is False
    assert action.is_new_window() is False


def test_launch_open_in_new_window_user_preference_removes_entry() -> None:
    action = PDActionLaunch()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert action.get_cos_object().get_dictionary_object(_NEW_WINDOW) is None
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_launch_set_open_in_new_window_bool_back_compat() -> None:
    action = PDActionLaunch()
    action.set_open_in_new_window(True)
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
    action.set_open_in_new_window(False)
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW


def test_launch_open_in_new_window_mode_with_explicit_cos_boolean() -> None:
    """A pre-populated COSDictionary with /NewWindow false maps to
    SAME_WINDOW (not USER_PREFERENCE)."""
    action = PDActionLaunch()
    action.get_cos_object().set_item(_NEW_WINDOW, COSBoolean.FALSE)
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW


# ---------- PDActionLaunch /F string accessor ----------


def test_launch_get_set_f_string() -> None:
    """Upstream getF/setF works directly with the string form of /F."""
    action = PDActionLaunch()
    action.set_f("foo.exe")
    assert action.get_f() == "foo.exe"


# ---------- PDActionEmbeddedGoTo tri-state ----------


def test_embedded_go_to_mode_absent_is_user_preference() -> None:
    action = PDActionEmbeddedGoTo()
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE
    assert action.get_open_in_new_window() is False


def test_embedded_go_to_mode_round_trip() -> None:
    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
    action.set_open_in_new_window(OpenMode.SAME_WINDOW)
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE
    assert action.get_cos_object().get_dictionary_object(_NEW_WINDOW) is None


# ---------- PDActionRemoteGoTo tri-state ----------


def test_remote_go_to_get_open_in_new_window_returns_open_mode() -> None:
    """RemoteGoTo's spec accessor returns OpenMode (matches upstream
    return type)."""
    action = PDActionRemoteGoTo()
    assert action.get_open_in_new_window() is OpenMode.USER_PREFERENCE

    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.get_open_in_new_window() is OpenMode.NEW_WINDOW
    # Legacy bool accessor still works.
    assert action.get_new_window() is True

    action.set_open_in_new_window(OpenMode.SAME_WINDOW)
    assert action.get_open_in_new_window() is OpenMode.SAME_WINDOW
    assert action.get_new_window() is False

    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert action.get_open_in_new_window() is OpenMode.USER_PREFERENCE
    assert action.get_cos_object().get_dictionary_object(_NEW_WINDOW) is None


def test_remote_go_to_set_open_in_new_window_bool_back_compat() -> None:
    action = PDActionRemoteGoTo()
    action.set_open_in_new_window(True)
    assert action.get_open_in_new_window() is OpenMode.NEW_WINDOW
    action.set_open_in_new_window(False)
    assert action.get_open_in_new_window() is OpenMode.SAME_WINDOW
