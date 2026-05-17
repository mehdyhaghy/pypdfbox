"""Wave 1345 coverage-boost tests for :class:`CSSeparation`.

Targets the residual branches:

* line 192 — ``state_changed(None)`` reads the current slider value
  via ``str(self._slider.get())``.
* lines 206-208 — ``OSError`` from ``update_color_bar`` (raised when
  :meth:`PDSeparation.to_rgb` blows up) is caught in ``state_changed``
  and the entry text is repainted with the exception's message.
* lines 239-240 — same ``OSError`` path inside ``_on_tint_entry``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.debugger.colorpane.cs_separation import CSSeparation


def _separation_array() -> COSArray:
    """Build a minimal `[/Separation /Black /DeviceGray <stream>]` array.

    The tint transform is a stub stream; ``to_rgb`` returns ``None`` for
    placeholder slots so the pane degrades to opaque black without
    raising. We patch ``to_rgb`` per-test when we want :class:`OSError`.
    """
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("Black"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    # Tint transform stream — empty / placeholder; PDFunction.create
    # returns ``None`` for shapes it doesn't recognise, which keeps
    # ``to_rgb`` from blowing up under happy-path construction.
    stream = COSStream()
    arr.add(stream)
    return arr


@pytest.fixture()
def pane(tk_root) -> CSSeparation:
    return CSSeparation(_separation_array(), master=tk_root)


def test_state_changed_with_none_reads_slider_value(pane: CSSeparation) -> None:
    """``state_changed(None)`` derives the value from the live slider.

    Sets the slider to a known integer first, then calls
    ``state_changed(None)`` and verifies the tint value is the slider's
    current position divided by 100.
    """
    assert pane._slider is not None
    # Bypass the syncing guard so the slider's set() doesn't trip it.
    pane._syncing = True
    pane._slider.set(60)
    pane._syncing = False
    pane.state_changed(None)
    # Slider 60 → tint 0.6 (matches get_float_representation(60)).
    assert pane.tint_value == 0.6


def test_state_changed_oserror_path_writes_message_to_entry(
    pane: CSSeparation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``update_color_bar`` raises :class:`OSError`, the entry is
    populated with the exception message (lines 206-208)."""
    sentinel = "tint transform missing in test"

    def _boom() -> None:
        raise OSError(sentinel)

    monkeypatch.setattr(pane, "update_color_bar", _boom)
    pane.state_changed("42")
    assert pane._tint_var is not None
    assert pane._tint_var.get() == sentinel


def test_on_tint_entry_oserror_path_writes_message_to_entry(
    pane: CSSeparation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same OSError catch inside ``_on_tint_entry`` (lines 239-240)."""
    sentinel = "tint transform missing on entry submit"

    assert pane._tint_var is not None
    pane._tint_var.set("0.42")
    monkeypatch.setattr(pane, "update_color_bar", lambda: (_ for _ in ()).throw(OSError(sentinel)))
    pane._on_tint_entry(None)
    assert pane._tint_var.get() == sentinel
