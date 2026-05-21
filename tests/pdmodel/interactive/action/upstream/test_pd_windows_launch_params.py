"""Upstream-parity port for ``PDWindowsLaunchParams``.

Mirrors ``PDWindowsLaunchParams.java`` (PDFBox 3.0.x). Upstream ships no
JUnit test for this typed wrapper around the ``/Win`` sub-dict of a
launch action. This module ports the source's behavioural contract:
OPERATION_* constants, getCOSObject parity, the /F /D /O /P accessor
pairs, and the OPERATION_OPEN default for /O.

Note: upstream ``setOperation`` (PDFBox 3.0.x) writes to ``COSName.D``
instead of ``COSName.O`` — a documented PDFBox bug. pypdfbox writes to
``/O`` (the spec-correct key); this test asserts the corrected behaviour.
A `CHANGES.md` entry for the divergence already exists.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)

_F = COSName.get_pdf_name("F")
_D = COSName.get_pdf_name("D")
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")


def test_operation_constants_match_spec():
    assert PDWindowsLaunchParams.OPERATION_OPEN == "open"
    assert PDWindowsLaunchParams.OPERATION_PRINT == "print"


def test_default_constructor_wraps_fresh_dict():
    win = PDWindowsLaunchParams()
    cos = win.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_cos_dictionary_ctor_wraps_existing_dict():
    d = COSDictionary()
    d.set_string(_F, "notepad.exe")
    win = PDWindowsLaunchParams(d)
    assert win.get_cos_object() is d
    assert win.get_filename() == "notepad.exe"


def test_filename_get_set_round_trip():
    win = PDWindowsLaunchParams()
    assert win.get_filename() is None
    win.set_filename("calc.exe")
    assert win.get_filename() == "calc.exe"


def test_directory_get_set_round_trip():
    win = PDWindowsLaunchParams()
    assert win.get_directory() is None
    win.set_directory("C:\\Windows\\System32")
    assert win.get_directory() == "C:\\Windows\\System32"
    # The directory write should target /D — distinct from /F and /O.
    assert win.get_cos_object().get_string(_D) == "C:\\Windows\\System32"


def test_operation_default_is_open():
    # Upstream's getOperation defaults to OPERATION_OPEN when /O is
    # absent. Matches ``params.getString(COSName.O, OPERATION_OPEN)``.
    win = PDWindowsLaunchParams()
    assert win.get_operation() == "open"


def test_operation_set_writes_to_o_key():
    # NB: upstream `setOperation` writes to /D (PDFBox bug). pypdfbox
    # writes to /O (spec-correct).
    win = PDWindowsLaunchParams()
    win.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
    assert win.get_operation() == "print"
    assert win.get_cos_object().get_string(_O) == "print"
    # /D should not have been polluted.
    assert win.get_cos_object().get_string(_D) is None


def test_execute_param_get_set_round_trip():
    win = PDWindowsLaunchParams()
    assert win.get_execute_param() is None
    win.set_execute_param("/A")
    assert win.get_execute_param() == "/A"
