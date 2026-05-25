"""Wave 1402 — micro round-out for residual branch partials scattered
across the debugger subtree.

One small test per branch keeps blast-radius narrow and is the easiest
way to keep coverage of every individual ``if/elif/else`` arm visible
in the cov report. Each target file is grouped under its own
``# --- <file> ---`` header for navigation.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

# ----------------------------------------------------------------------
# Shared Tk fixture (debugger UI primitives need a Tk root).
# ----------------------------------------------------------------------


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk tests opted out")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()


# ----------------------------------------------------------------------
# pypdfbox/debugger/colorpane/cs_array_based.py  — 119->126
# ----------------------------------------------------------------------


def test_cs_array_based_zero_components_skips_component_count_label(
    tk_root: tk.Tk,
) -> None:
    """119->126 — ``_number_of_components`` is 0 ⇒ skip the count
    label and continue to the ICCBased branch."""
    from pypdfbox.debugger.colorpane.cs_array_based import CSArrayBased

    pane = CSArrayBased.__new__(CSArrayBased)
    cs = MagicMock()
    cs.get_name.return_value = "DeviceGray"
    pane._color_space = cs  # type: ignore[attr-defined]  # noqa: SLF001
    pane._number_of_components = 0  # type: ignore[attr-defined]  # noqa: SLF001
    pane._panel = None  # type: ignore[attr-defined]  # noqa: SLF001
    pane._errmsg = ""  # type: ignore[attr-defined]  # noqa: SLF001
    pane.init_ui(tk_root)
    assert pane._panel is not None  # noqa: SLF001


# ----------------------------------------------------------------------
# pypdfbox/debugger/hexviewer/ascii_pane.py  — 94->exit
# ----------------------------------------------------------------------


def test_ascii_pane_paint_in_selected_with_out_of_range_index(
    tk_root: tk.Tk,
) -> None:
    """94->exit — ``_selected_index_in_line`` is out of range ⇒ skip
    the per-char selected tag insertion."""
    from pypdfbox.debugger.hexviewer.ascii_pane import ASCIIPane
    from pypdfbox.debugger.hexviewer.hex_model import HexModel

    model = HexModel(b"ABCDEFGH")
    pane = ASCIIPane(tk_root, model)
    # Negative ⇒ the in-range check is False.
    pane._selected_index_in_line = -1  # noqa: SLF001
    pane.configure(state="normal")
    pane.paint_in_selected(1, "1.0")
    pane.configure(state="disabled")


# ----------------------------------------------------------------------
# pypdfbox/debugger/hexviewer/hex_pane.py  — 124->exit
# ----------------------------------------------------------------------


def test_hex_pane_set_selected_with_unchanged_index_is_noop(
    tk_root: tk.Tk,
) -> None:
    """124->exit — ``set_selected(idx)`` where ``idx == _selected_index``
    ⇒ skip ``put_in_selected``."""
    from pypdfbox.debugger.hexviewer.hex_model import HexModel
    from pypdfbox.debugger.hexviewer.hex_pane import HexPane

    model = HexModel(b"abcd")
    pane = HexPane(tk_root, model)
    pane.set_selected(0)
    # Calling again with the same value triggers the False arm of 124.
    pane.set_selected(0)


# ----------------------------------------------------------------------
# pypdfbox/debugger/streampane/tooltip/font_tool_tip.py  — 48->exit
# ----------------------------------------------------------------------


def test_font_tool_tip_skips_markup_when_font_has_no_name(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """48->exit — font.get_name() returns falsy ⇒ skip markup build."""
    from pypdfbox.cos import COSName
    from pypdfbox.debugger.streampane.tooltip.font_tool_tip import FontToolTip

    # Construct a fake resources object that returns a font with empty
    # name on lookup — drives the 48 branch.
    class _FontWithEmptyName:
        def get_name(self) -> str:
            return ""

    class _Resources:
        def get_font_names(self) -> list[COSName]:
            return [COSName.get_pdf_name("F1")]

        def get_font(self, _name: COSName) -> Any:
            return _FontWithEmptyName()

    # Construct manually — init_ui parses "/F1 12 Tf" out of the row text.
    tip = FontToolTip(_Resources(), "/F1 12 Tf")  # type: ignore[arg-type]
    # Empty font name ⇒ markup stays None.
    assert tip._markup is None  # noqa: SLF001


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/debug_log.py  — 80->exit (info gated by _INFO)
# ----------------------------------------------------------------------


def test_debug_log_info_when_info_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """80->exit — when the module-level ``_INFO`` flag is False, the
    method exits without emitting."""
    from pypdfbox.debugger.ui import debug_log as _dl

    monkeypatch.setattr(_dl, "_INFO", False)
    log = _dl.DebugLog("test-info-disabled")
    # No raise — early-exit branch taken.
    log.info("ignored")


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/file_open_save_dialog.py  — 109->111
# ----------------------------------------------------------------------


def test_file_open_save_dialog_save_skips_extension_append_when_present(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """109->111 — when the chosen path already ends with the extension
    ⇒ skip the ``+ "." + extension`` append step."""
    from pypdfbox.debugger.ui.file_open_save_dialog import FileOpenSaveDialog

    dialog = FileOpenSaveDialog(tk_root)
    # Force the picker to return a path WITH the extension already in
    # place ⇒ branch 109 evaluates False (no append).
    monkeypatch.setattr(
        dialog, "_ask_save_path", lambda: "/tmp/already.pdf"
    )
    fake_doc = MagicMock()
    result = dialog.save_document(fake_doc, extension="pdf")
    assert result is True
    fake_doc.save.assert_called_once_with("/tmp/already.pdf")


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/log_dialog.py  — 93->exit (set_visible False
# when toplevel is None) and 98->100 (show without rebuild)
# ----------------------------------------------------------------------


def test_log_dialog_set_visible_false_when_no_toplevel(
    tk_root: tk.Tk,
) -> None:
    """93->exit — ``set_visible(False)`` with no built toplevel ⇒ skip
    the withdraw call."""
    from pypdfbox.debugger.ui.log_dialog import LogDialog

    dialog = LogDialog.__new__(LogDialog)
    dialog._toplevel = None  # noqa: SLF001
    dialog.set_visible(False)


def test_log_dialog_show_reuses_existing_toplevel(tk_root: tk.Tk) -> None:
    """98->100 — second show() call doesn't trigger ``_build`` because
    ``_toplevel`` is already populated."""
    from pypdfbox.debugger.ui.log_dialog import LogDialog

    dialog = LogDialog(tk_root)
    first = dialog.show()
    # Second call hits the False arm of 98 and just deiconifies.
    second = dialog.show()
    assert first is second


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/menu_base.py  — 180->183, 184->exit
# ----------------------------------------------------------------------


def test_menu_base_add_radio_group_with_existing_variable_and_no_current(
    tk_root: tk.Tk,
) -> None:
    """180->183 — ``variable`` provided and ``current`` is None ⇒
    skip the variable.set step."""
    from pypdfbox.debugger.ui.menu_base import MenuBase

    base = MenuBase()
    parent = tk.Menu(tk_root)
    menu = tk.Menu(parent)
    base.set_menu(menu)
    pre = tk.StringVar(value="apple")
    base.add_radio_group(
        items=["apple", "pear"], current=None, on_change=None, variable=pre
    )
    # The variable's value should be unchanged.
    assert pre.get() == "apple"


def test_menu_base_radio_handler_with_no_on_change(tk_root: tk.Tk) -> None:
    """184->exit — ``on_change`` is None ⇒ skip the callback inside the
    handler closure."""
    from pypdfbox.debugger.ui.menu_base import MenuBase

    base = MenuBase()
    parent = tk.Menu(tk_root)
    menu = tk.Menu(parent)
    base.set_menu(menu)
    var = base.add_radio_group(
        items=["a", "b"], current="a", on_change=None
    )
    # Invoke the first radio entry — its command runs ``_handler``.
    menu.invoke(0)
    assert var.get() == "a"


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/osx_adapter.py  — 238->240 (quit_cb None branch)
# ----------------------------------------------------------------------


def test_osx_adapter_register_skips_when_quit_callback_missing(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """238->240 — ``callbacks.get('quit')`` is None ⇒ skip the
    ``set_quit_handler`` call but continue down the cascade."""
    import pypdfbox.debugger.ui.osx_adapter as _osx

    # Force the macOS guard True so the body runs on this dev box.
    monkeypatch.setattr(_osx, "_is_macos", lambda: True)
    adapter = _osx.OSXAdapter.register(tk_root, {"about": lambda: None})
    assert adapter is not None


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/text_dialog.py  — 78->exit
# ----------------------------------------------------------------------


def test_text_dialog_set_visible_false_when_no_toplevel(
    tk_root: tk.Tk,
) -> None:
    """78->exit — ``set_visible(False)`` with no toplevel ⇒ skip
    withdraw."""
    from pypdfbox.debugger.ui.text_dialog import TextDialog

    dialog = TextDialog.__new__(TextDialog)
    dialog._toplevel = None  # noqa: SLF001
    dialog.set_visible(False)


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/textsearcher/search_panel.py
#   128->exit, 132->exit, 165->168
# ----------------------------------------------------------------------


def _make_search_panel(tk_root: tk.Tk) -> Any:
    """Build a SearchPanel with no-op listeners for tests."""
    from pypdfbox.debugger.ui.textsearcher.search_panel import SearchPanel

    class _Listener:
        pass  # no methods

    return SearchPanel(
        document_listener=_Listener(),
        change_listener=_Listener(),
        component_listener=_Listener(),
        next_action=lambda: None,
        previous_action=lambda: None,
        parent=tk_root,
    )


def test_search_panel_document_listener_without_changed_update(
    tk_root: tk.Tk,
) -> None:
    """128->exit — document_listener has NO ``changed_update`` method
    ⇒ skip the dispatch."""
    panel = _make_search_panel(tk_root)
    panel._on_document_event()  # noqa: SLF001


def test_search_panel_change_listener_without_state_changed(
    tk_root: tk.Tk,
) -> None:
    """132->exit — change_listener has NO ``state_changed`` method."""
    panel = _make_search_panel(tk_root)
    panel._on_state_change()  # noqa: SLF001


def test_search_panel_reset_when_counter_not_visible(tk_root: tk.Tk) -> None:
    """165->168 — ``_counter_visible`` is False ⇒ skip the pack_forget."""
    panel = _make_search_panel(tk_root)
    panel._counter_visible = False  # noqa: SLF001
    panel.reset()


# ----------------------------------------------------------------------
# pypdfbox/debugger/ui/textsearcher/searcher.py
#   214->216, 218->220
# ----------------------------------------------------------------------


def test_searcher_update_navigation_current_above_range(tk_root: tk.Tk) -> None:
    """214->216 — ``_current_match`` is non-zero AND outside
    ``[1, _total_match-1]`` ⇒ both arms of 212/214 are False, jump
    straight to 216."""
    from pypdfbox.debugger.ui.textsearcher.searcher import Searcher

    searcher = Searcher.__new__(Searcher)
    searcher._current_match = 10  # noqa: SLF001
    searcher._total_match = 3  # noqa: SLF001 - current 10 > total-1 = 2
    searcher._previous_enabled = True  # noqa: SLF001
    searcher._next_enabled = True  # noqa: SLF001
    searcher._search_panel = None  # noqa: SLF001
    searcher.update_navigation_buttons()
    # previous_enabled stays True since neither arm fires.
    assert searcher._previous_enabled is True  # noqa: SLF001


def test_searcher_update_navigation_current_negative(tk_root: tk.Tk) -> None:
    """218->220 — ``_current_match`` is non-zero AND outside the
    ``< _total_match - 1`` window (also outside the equality at 216)
    so both arms are False. ``_current_match`` greater than
    ``_total_match - 1`` skips both."""
    from pypdfbox.debugger.ui.textsearcher.searcher import Searcher

    searcher = Searcher.__new__(Searcher)
    searcher._current_match = 10  # noqa: SLF001
    searcher._total_match = 3  # noqa: SLF001 - current > total - 1
    searcher._previous_enabled = False  # noqa: SLF001
    searcher._next_enabled = True  # noqa: SLF001
    searcher._search_panel = None  # noqa: SLF001
    searcher.update_navigation_buttons()
    # next_enabled stays True since neither 216-arm nor 218-arm fires.
    assert searcher._next_enabled is True  # noqa: SLF001


# ----------------------------------------------------------------------
# pypdfbox/debugger/streampane/stream_pane.py — 171->173 (selected
# not in available filters) and the lazy doc / inline-image branches.
# ----------------------------------------------------------------------


def test_stream_pane_header_combobox_with_selected_outside_filters(
    tk_root: tk.Tk,
) -> None:
    """171->173 — ``selected`` is not in ``available_filters`` ⇒ the
    combo.set call is skipped."""
    from pypdfbox.cos import COSStream
    from pypdfbox.debugger.streampane.stream_pane import StreamPane

    stream = COSStream()
    pane = StreamPane(
        tk_root, stream, is_content_stream=False, is_thumb=False
    )
    header = pane.create_header_panel(
        available_filters=["a", "b"],
        selected="not-in-list",
        action_listener=None,
    )
    assert header is not None


# ----------------------------------------------------------------------
# pypdfbox/debugger/streampane/stream_pane.py — 310->312, 571->573
# Both are the "content_segments is None" fall-through to the plain-
# text default.
# ----------------------------------------------------------------------


def test_stream_pane_build_segments_falls_back_when_parser_fails(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """310->312 — ``_content_stream_segments`` returns ``None`` (parse
    failure) ⇒ fall through to ``_plain_text_segments``."""
    from pypdfbox.cos import COSStream
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import StreamPane

    cos_stream = COSStream()
    cos_stream.set_data(b"BT /F0 12 Tf (hi) Tj ET")
    pane = StreamPane(
        tk_root, cos_stream, is_content_stream=True, is_thumb=False
    )
    # Force _content_stream_segments to return None.
    monkeypatch.setattr(
        pane, "_content_stream_segments", lambda _raw: None
    )
    pane._build_segments(Stream.DECODED, nice=True)  # noqa: SLF001


def test_stream_pane_document_creator_falls_back_when_content_returns_none(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """571->573 — fall-through inside ``DocumentCreator.do_in_background``
    when ``get_content_stream_document`` returns ``None``."""
    from pypdfbox.cos import COSStream
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import (
        DocumentCreator,
        StreamPane,
    )

    cos_stream = COSStream()
    cos_stream.set_data(b"raw")
    pane = StreamPane(
        tk_root, cos_stream, is_content_stream=True, is_thumb=False
    )
    creator = DocumentCreator(
        target_view=pane,
        stream=pane._stream,  # noqa: SLF001
        filter_key=Stream.DECODED,
        nice=True,
    )
    monkeypatch.setattr(
        creator, "get_content_stream_document", lambda _raw: None
    )
    # Fall-through ⇒ get_document is called instead.
    creator.do_in_background()


# ----------------------------------------------------------------------
# pypdfbox/debugger/fontencodingpane/font_encoding_pane_controller.py
#   85->exit, 87->exit
# ----------------------------------------------------------------------


def test_font_encoding_controller_with_unknown_font_type(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """85->exit — font is none of Type3 / SimpleFont / Type0Font ⇒
    no pane is constructed; the elif chain falls through."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.debugger.fontencodingpane import (
        font_encoding_pane_controller as _mod,
    )
    from pypdfbox.pdmodel import PDResources

    class _UnknownFont:
        def get_cos_object(self) -> Any:
            return COSDictionary()

    # Force PDResources.get_font to return our unknown-type font so the
    # elif chain at 81-88 falls all the way through.
    monkeypatch.setattr(
        PDResources, "get_font", lambda self, name: _UnknownFont()
    )
    ctrl = _mod.FontEncodingPaneController(
        COSName.get_pdf_name("F1"), COSDictionary(), master=tk_root
    )
    assert ctrl._font_pane is None  # noqa: SLF001


# ----------------------------------------------------------------------
# pypdfbox/debugger/fontencodingpane/font_pane.py — 106->108, 110->114
# ----------------------------------------------------------------------


def test_font_pane_path_y_bounds_with_partial_rectangle_attrs() -> None:
    """106->108 — rect exposes ``min_y/max_y`` as ``None`` AND only
    ``y`` (no ``height``) ⇒ the ``lo, hi`` reassignment is skipped, and
    the next ``if lo is not None and hi is not None`` evaluates False
    ⇒ fall through (110->114)."""
    from pypdfbox.debugger.fontencodingpane.font_pane import _path_y_bounds

    class _Rect:
        # Both min_y / max_y missing → forces the fallback path.
        y = 1.0
        # height is intentionally absent ⇒ branch 106 stays False, no
        # lo/hi reassignment ⇒ branch 110 is False too.

    class _Path:
        def get_bounds(self) -> _Rect:
            return _Rect()

    # Path has the get_bounds attr; the inner rect has no usable bounds.
    assert _path_y_bounds(_Path()) is None


def test_font_pane_path_y_bounds_with_y_and_height_only() -> None:
    """106->108 inverse — both y AND height are present ⇒ the
    ``if y is not None and h is not None`` arm fires (covers the
    True path through 106-107)."""
    from pypdfbox.debugger.fontencodingpane.font_pane import _path_y_bounds

    class _Rect:
        y = 10.0
        height = 5.0
        # min_y / max_y missing ⇒ lo/hi None, fall to the y/h fallback.

    class _Path:
        def bounds(self) -> _Rect:
            return _Rect()

    result = _path_y_bounds(_Path())
    assert result == (10.0, 15.0)


def test_font_encoding_controller_with_type0_no_descendant(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """87->exit — Type0Font is given but ``get_descendant_font()``
    returns None ⇒ the wrapper is NOT constructed."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.debugger.fontencodingpane import (
        font_encoding_pane_controller as _mod,
    )
    from pypdfbox.pdmodel import PDResources
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    fake_font = PDType0Font.__new__(PDType0Font)
    fake_font.get_descendant_font = lambda: None  # type: ignore[method-assign]
    fake_font.get_cos_object = lambda: object()  # type: ignore[method-assign]
    monkeypatch.setattr(
        PDResources, "get_font", lambda self, name: fake_font
    )
    ctrl = _mod.FontEncodingPaneController(
        COSName.get_pdf_name("F1"), COSDictionary(), master=tk_root
    )
    assert ctrl._font_pane is None  # noqa: SLF001
