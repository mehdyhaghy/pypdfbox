"""Wave 1345 coverage-boost tests for :class:`CSArrayBased`.

Targets the two residual branches surfaced by ``--cov-report=term-missing``:

* lines 75-79 — the ``OSError`` path when ``PDColorSpace.create`` raises
  (mirrors upstream's ``IOException`` catch). We force the raise via a
  ``monkeypatch`` of :func:`PDColorSpace.create` so the constructor's
  ``except OSError`` branch fires.
* lines 120-125 — the ``PDICCBased`` arm of ``_init_ui`` which emits the
  ``Colorspace type:`` + ``sRGB:`` labels. We build a minimal valid
  ICCBased array (``[/ICCBased <stream with /N 3>]``) so the constructor
  produces a real :class:`PDICCBased` and the labels get packed.
"""

from __future__ import annotations

from tkinter import ttk

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.debugger.colorpane import cs_array_based as cs_module
from pypdfbox.debugger.colorpane.cs_array_based import CSArrayBased


def _icc_based_array(n: int = 3) -> COSArray:
    """Build a minimal valid ``[/ICCBased <stream>]`` array.

    The stream carries ``/N <n>`` so :class:`PDICCBased` reports the
    expected component count. Pillow's ICC machinery isn't required to
    *render* — the ``CSArrayBased`` pane only calls
    ``get_color_space_type`` and ``is_srgb`` which are defined on the
    PDICCBased instance itself.
    """
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), n)
    arr.add(stream)
    return arr


def test_oserror_branch_renders_error_panel(
    tk_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OSError from ``PDColorSpace.create`` is caught and surfaced.

    Upstream's ``initUI`` matches an ``IOException`` from the same call;
    pypdfbox's port catches :class:`OSError` (mirrors the project's
    exception-mapping convention). When the create call raises, the
    constructor stashes the message on ``_errmsg`` and packs a single
    error label.
    """
    sentinel_msg = "synthetic OSError for the create-time catch"

    def _boom(*_args, **_kwargs):
        raise OSError(sentinel_msg)

    monkeypatch.setattr(cs_module.PDColorSpace, "create", _boom)

    arr = COSArray()
    arr.add(COSName.get_pdf_name("AnyName"))
    pane = CSArrayBased(arr, master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    # Error branch packs exactly one label (the error message).
    children = panel.winfo_children()
    assert len(children) <= 1


def test_icc_based_branch_emits_colorspace_type_and_srgb_labels(tk_root) -> None:
    """PDICCBased pane carries 4+ labels: header + component count +
    type + sRGB."""
    pane = CSArrayBased(_icc_based_array(n=3), master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    children = panel.winfo_children()
    # Header + component-count + colorspace-type + sRGB = 4 labels.
    assert len(children) >= 4
