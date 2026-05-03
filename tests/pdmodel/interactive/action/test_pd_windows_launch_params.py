"""Tests for ``PDWindowsLaunchParams`` — PDF 32000-1 §12.6.4.5 Table 197
(Windows-specific launch parameters)."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)

_F = COSName.get_pdf_name("F")
_D = COSName.D  # type: ignore[attr-defined]
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")
_WIN = COSName.get_pdf_name("Win")


# ---------------------------------------------------------------- constructors
def test_default_constructor_creates_empty_dict() -> None:
    params = PDWindowsLaunchParams()
    assert isinstance(params.get_cos_object(), COSDictionary)
    assert len(params.get_cos_object()) == 0


def test_constructor_wraps_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_string(_F, "notepad.exe")
    params = PDWindowsLaunchParams(raw)
    assert params.get_cos_object() is raw
    assert params.get_filename() == "notepad.exe"


# ---------------------------------------------------------------- /F filename
def test_filename_round_trip() -> None:
    params = PDWindowsLaunchParams()
    assert params.get_filename() is None

    params.set_filename("C:\\Program Files\\App\\app.exe")
    assert params.get_filename() == "C:\\Program Files\\App\\app.exe"
    assert params.get_cos_object().get_string(_F) == "C:\\Program Files\\App\\app.exe"

    params.set_filename(None)
    assert params.get_filename() is None
    assert _F not in params.get_cos_object()


# ---------------------------------------------------------------- /D directory
def test_directory_round_trip() -> None:
    params = PDWindowsLaunchParams()
    assert params.get_directory() is None

    params.set_directory("C:\\Users\\Test")
    assert params.get_directory() == "C:\\Users\\Test"
    assert params.get_cos_object().get_string(_D) == "C:\\Users\\Test"

    params.set_directory(None)
    assert params.get_directory() is None
    assert _D not in params.get_cos_object()


# ---------------------------------------------------------------- /O operation
def test_operation_default_when_absent_is_open() -> None:
    """Upstream ``getOperation`` returns ``OPERATION_OPEN`` as default."""
    params = PDWindowsLaunchParams()
    assert _O not in params.get_cos_object()
    assert params.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN
    assert params.get_operation() == "open"


def test_operation_round_trip_open_print() -> None:
    params = PDWindowsLaunchParams()
    params.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    assert params.get_operation() == "print"
    assert params.get_cos_object().get_string(_O) == "print"

    params.set_operation(PDWindowsLaunchParams.OPERATION_OPEN)
    assert params.get_operation() == "open"


def test_operation_constants_match_pdf_spec() -> None:
    assert PDWindowsLaunchParams.OPERATION_OPEN == "open"
    assert PDWindowsLaunchParams.OPERATION_PRINT == "print"


def test_operation_set_none_falls_back_to_default() -> None:
    params = PDWindowsLaunchParams()
    params.set_operation("print")
    params.set_operation(None)
    # /O removed → default kicks in.
    assert _O not in params.get_cos_object()
    assert params.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN


# ------------------------------------------------------ /O typed predicates
def test_has_operation_default_false() -> None:
    """``has_operation`` distinguishes default-fallback from explicit set."""
    params = PDWindowsLaunchParams()
    assert params.has_operation() is False
    # Default getter still resolves to OPERATION_OPEN.
    assert params.get_operation() == PDWindowsLaunchParams.OPERATION_OPEN


def test_has_operation_true_after_explicit_set() -> None:
    params = PDWindowsLaunchParams()
    params.set_operation(PDWindowsLaunchParams.OPERATION_OPEN)
    assert params.has_operation() is True

    params.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    assert params.has_operation() is True

    params.set_operation(None)
    assert params.has_operation() is False


def test_is_open_operation_when_absent() -> None:
    """``is_open_operation`` honors the spec default — absent /O is open."""
    params = PDWindowsLaunchParams()
    assert params.is_open_operation() is True
    assert params.is_print_operation() is False


def test_is_open_operation_when_explicit_open() -> None:
    params = PDWindowsLaunchParams()
    params.set_operation(PDWindowsLaunchParams.OPERATION_OPEN)
    assert params.is_open_operation() is True
    assert params.is_print_operation() is False


def test_is_print_operation_when_explicit_print() -> None:
    params = PDWindowsLaunchParams()
    params.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    assert params.is_print_operation() is True
    assert params.is_open_operation() is False


def test_predicates_unrecognized_operation() -> None:
    """An unrecognized /O value (rare, malformed) is neither open nor print."""
    params = PDWindowsLaunchParams()
    params.set_operation("explore")
    assert params.is_open_operation() is False
    assert params.is_print_operation() is False
    assert params.has_operation() is True


def test_predicates_round_trip_after_clear() -> None:
    params = PDWindowsLaunchParams()
    params.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    assert params.is_print_operation() is True

    params.set_operation(None)
    # Cleared → falls back to default-open.
    assert params.is_open_operation() is True
    assert params.is_print_operation() is False
    assert params.has_operation() is False


# ---------------------------------------------------------------- /P parameter
def test_execute_param_round_trip() -> None:
    params = PDWindowsLaunchParams()
    assert params.get_execute_param() is None

    params.set_execute_param("--silent /A")
    assert params.get_execute_param() == "--silent /A"
    assert params.get_cos_object().get_string(_P) == "--silent /A"

    params.set_execute_param(None)
    assert params.get_execute_param() is None
    assert _P not in params.get_cos_object()


# ---------------------------------------------------------------- integration
def test_integration_with_pd_action_launch_typed_setter() -> None:
    action = PDActionLaunch()
    params = PDWindowsLaunchParams()
    params.set_filename("notepad.exe")
    params.set_directory("C:\\Users")
    params.set_operation(PDWindowsLaunchParams.OPERATION_OPEN)
    params.set_execute_param("/A")

    action.set_win_launch_params(params)

    resolved = action.get_win_launch_params()
    assert isinstance(resolved, PDWindowsLaunchParams)
    assert resolved.get_cos_object() is params.get_cos_object()
    assert resolved.get_filename() == "notepad.exe"
    assert resolved.get_directory() == "C:\\Users"
    assert resolved.get_operation() == "open"
    assert resolved.get_execute_param() == "/A"


def test_integration_get_returns_none_when_absent() -> None:
    action = PDActionLaunch()
    assert action.get_win_launch_params() is None


def test_integration_set_none_removes_win_entry() -> None:
    action = PDActionLaunch()
    params = PDWindowsLaunchParams()
    params.set_filename("foo.exe")
    action.set_win_launch_params(params)
    assert action.get_win_launch_params() is not None

    action.set_win_launch_params(None)
    assert action.get_win_launch_params() is None
    assert _WIN not in action.get_cos_object()


def test_integration_typed_wrapper_on_existing_action_dict() -> None:
    """An existing ``/Win`` raw dict is re-wrapped as ``PDWindowsLaunchParams``
    on read — typed access does not require constructing via the typed setter.
    """
    raw_action = COSDictionary()
    raw_action.set_name("Type", "Action")
    raw_action.set_name("S", "Launch")
    raw_win = COSDictionary()
    raw_win.set_item(_F, COSString("calc.exe"))
    raw_win.set_item(_O, COSString("print"))
    raw_action.set_item(_WIN, raw_win)

    action = PDActionLaunch(raw_action)
    resolved = action.get_win_launch_params()
    assert isinstance(resolved, PDWindowsLaunchParams)
    assert resolved.get_cos_object() is raw_win
    assert resolved.get_filename() == "calc.exe"
    assert resolved.get_operation() == "print"
