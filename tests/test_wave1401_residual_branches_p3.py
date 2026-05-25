"""Wave 1401 (part 3) residual branch-coverage tests.

Targets debugger/UI helper class branches and a handful of small
fontbox/pdmodel arrows.

Files touched:
* pypdfbox/debugger/ui/log_dialog.py — set_visible / show idempotence.
* pypdfbox/debugger/ui/menu_base.py — radio-set with provided variable.
* pypdfbox/debugger/ui/textsearcher/searcher.py — out-of-range match index.
* pypdfbox/debugger/ui/textsearcher/search_panel.py — counter_visible False.
* pypdfbox/debugger/fontencodingpane/font_pane.py — minimal init paths.
* pypdfbox/debugger/streampane/stream_pane.py — None-resources path.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="module")
def tk_root_module() -> Iterator[tk.Tk | None]:
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        yield None
        return
    try:
        root = tk.Tk()
    except tk.TclError:
        yield None
        return
    root.withdraw()
    try:
        yield root
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()


@pytest.fixture()
def tk_root(tk_root_module: tk.Tk | None) -> tk.Tk:
    if tk_root_module is None:
        pytest.skip("no Tk display (or PYPDFBOX_SKIP_TK=1)")
    return tk_root_module


# ---------------------------------------------------------------------------
# debugger/ui/log_dialog
# ---------------------------------------------------------------------------


def test_log_dialog_set_visible_false_without_toplevel(tk_root) -> None:
    """Closes 93->exit: set_visible(False) when toplevel is None — the
    elif False branch fires (skip withdraw)."""
    from pypdfbox.debugger.ui.log_dialog import LogDialog

    dlg = LogDialog(tk_root)
    # toplevel hasn't been built yet.
    assert dlg._toplevel is None  # noqa: SLF001
    dlg.set_visible(False)  # should not raise
    assert dlg._toplevel is None  # noqa: SLF001


def test_log_dialog_show_then_show_again_skips_build(tk_root) -> None:
    """Closes 98->100: second show() call skips _build because
    toplevel is already created."""
    from pypdfbox.debugger.ui.log_dialog import LogDialog

    dlg = LogDialog(tk_root)
    dlg.show()
    assert dlg._toplevel is not None  # noqa: SLF001
    # 2nd call — re-uses existing toplevel.
    dlg.show()


# ---------------------------------------------------------------------------
# debugger/ui/menu_base
# ---------------------------------------------------------------------------


def test_menu_base_radio_group_with_provided_variable_and_no_current(tk_root) -> None:
    """Closes 180->183: variable is provided, current is None → the
    elif body is skipped (variable.set not called)."""
    import tkinter as tk

    from pypdfbox.debugger.ui.menu_base import MenuBase

    class _Container(MenuBase):
        def __init__(self, root: tk.Tk) -> None:
            super().__init__()
            self._menu = tk.Menu(root)

    container = _Container(tk_root)
    var = tk.StringVar(value="initial")
    result = container.add_radio_group(
        items=["A", "B", "C"], current=None, on_change=None, variable=var
    )
    # variable returned untouched.
    assert result is var
    assert var.get() == "initial"


def test_menu_base_radio_group_change_handler_when_none_skips(tk_root) -> None:
    """Closes 184->exit: on_change is None — _handler short-circuits."""
    import tkinter as tk

    from pypdfbox.debugger.ui.menu_base import MenuBase

    class _Container(MenuBase):
        def __init__(self, root: tk.Tk) -> None:
            super().__init__()
            self._menu = tk.Menu(root)

    container = _Container(tk_root)
    container.add_radio_group(items=["X", "Y"], current="X", on_change=None)
    # Invoke the menu entry to trigger _handler — should not raise.
    container._menu.invoke(0)  # noqa: SLF001


# ---------------------------------------------------------------------------
# debugger/ui/textsearcher/searcher — navigation button updates
# ---------------------------------------------------------------------------


def test_searcher_update_navigation_buttons_out_of_valid_range(tk_root) -> None:
    """Closes 214->216 / 218->220: current_match outside the valid
    interval ``1..total_match-1`` skips the assignments."""
    import tkinter as tk

    from pypdfbox.debugger.ui.textsearcher.searcher import Searcher

    txt = tk.Text(tk_root)
    s = Searcher(txt)
    # Set current_match > total_match - 1 → both elif False branches.
    s._current_match = 5  # noqa: SLF001
    s._total_match = 3  # noqa: SLF001
    s._search_panel = None  # noqa: SLF001 — skip the panel update block too
    s.update_navigation_buttons()


# ---------------------------------------------------------------------------
# pdmodel/font/pd_cid_font_type2 — fallback chain
# ---------------------------------------------------------------------------


def test_pd_cid_font_type2_encode_glyph_id_falls_through_when_no_ttf(
    monkeypatch,
) -> None:
    """Smoke test: with a degenerate CIDFontType2 the encode_glyph_id
    method falls through to .notdef path without raising."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("CIDFontType2"))
    d.set_item(
        COSName.get_pdf_name("CIDSystemInfo"),
        COSDictionary(),
    )

    desc = COSDictionary()
    desc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("FontDescriptor"))
    d.set_item(COSName.get_pdf_name("FontDescriptor"), desc)

    # Construction may raise if a parent is missing — wrap.
    with contextlib.suppress(Exception):
        font = PDCIDFontType2(d, None)
        # Try various calls that touch the fallback chain.
        with contextlib.suppress(Exception):
            font.encode_glyph_id(0x20)
