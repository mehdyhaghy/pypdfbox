"""Verify wave-1389 debugger inner-class method completeness.

Wave 1388 agent E flagged ~50 missing methods across 19 debugger
classes — all anonymous Swing event handlers (``ActionListener`` /
``MouseListener`` / ``KeyListener`` / ``AncestorListener``) or
package-private helpers (``createPane`` / ``createView`` / ``initUI``
/ ``createMarkUp`` / ``paintComponent``). Wave 1389 closes them by
adding Tk-equivalent public methods on the corresponding Python
classes. This test asserts each method now exists on the expected
class and — where headless-safe — exercises the lightweight logic.

The matrix below mirrors the ``DEFERRED.md`` audit verbatim.
"""

from __future__ import annotations

import os
import sys

import pytest

DISPLAY_AVAILABLE = "DISPLAY" in os.environ or sys.platform == "darwin"


# ---------------------------------------------------------------------------
# Method-existence sweep (headless-safe — no Tk widgets created)
# ---------------------------------------------------------------------------

#: (import-target, attribute-name). Imports happen at test time so the
#: failure surface is per-row rather than a single collection error.
_METHOD_PARITY_MATRIX: list[tuple[str, str, str]] = [
    # (module_path, class_name, method_name)
    (
        "pypdfbox.debugger.colorpane.cs_array_based",
        "CSArrayBased",
        "init_ui",
    ),
    (
        "pypdfbox.debugger.colorpane.cs_separation",
        "CSSeparation",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.flagbitspane.flag_bits_pane",
        "FlagBitsPane",
        "create_pane",
    ),
    (
        "pypdfbox.debugger.flagbitspane.flag_bits_pane_view",
        "FlagBitsPaneView",
        "create_view",
    ),
    (
        "pypdfbox.debugger.streampane.tooltip.g_tool_tip",
        "GToolTip",
        "create_mark_up",
    ),
    (
        "pypdfbox.debugger.streampane.tooltip.rg_tool_tip",
        "RGToolTip",
        "create_mark_up",
    ),
    (
        "pypdfbox.debugger.streampane.tooltip.scn_tool_tip",
        "SCNToolTip",
        "create_mark_up",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_editor",
        "HexEditor",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_clicked",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_pressed",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_released",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_entered",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_exited",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_dragged",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "mouse_moved",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "key_pressed",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "key_released",
    ),
    (
        "pypdfbox.debugger.hexviewer.hex_pane",
        "HexPane",
        "key_typed",
    ),
    (
        "pypdfbox.debugger.hexviewer.status_pane",
        "StatusPane",
        "create_view",
    ),
    (
        "pypdfbox.debugger.hexviewer.upper_pane",
        "UpperPane",
        "paint_component",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "ancestor_added",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "ancestor_removed",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "ancestor_moved",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_clicked",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_pressed",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_released",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_entered",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_exited",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_dragged",
    ),
    (
        "pypdfbox.debugger.pagepane.page_pane",
        "PagePane",
        "mouse_moved",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "exit_menu_item_action_performed",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_annot",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_encrypt",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_flag_node",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_font",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_font_descriptor",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_other_color_space",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_page",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_signature",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_special_color_space",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_stream",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "is_string",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "j_tree1_value_changed",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "open_menu_item_action_performed",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "print_menu_item_action_performed",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "read_pd_furl",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "save_as_menu_item_action_performed",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_color_pane",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_flag_pane",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_font",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_page",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_signature_pane",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_stream",
    ),
    (
        "pypdfbox.debugger.pd_debugger",
        "PDFDebugger",
        "show_string",
    ),
    (
        "pypdfbox.debugger.streampane.stream_image_view",
        "StreamImageView",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.streampane.stream_image_view",
        "StreamImageView",
        "ancestor_added",
    ),
    (
        "pypdfbox.debugger.streampane.stream_image_view",
        "StreamImageView",
        "ancestor_removed",
    ),
    (
        "pypdfbox.debugger.streampane.stream_image_view",
        "StreamImageView",
        "ancestor_moved",
    ),
    (
        "pypdfbox.debugger.streampane.stream_pane",
        "StreamPane",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.streampane.stream_text_view",
        "StreamTextView",
        "mouse_dragged",
    ),
    (
        "pypdfbox.debugger.streampane.stream_text_view",
        "StreamTextView",
        "mouse_moved",
    ),
    (
        "pypdfbox.debugger.streampane.stream_text_view",
        "StreamTextView",
        "ancestor_added",
    ),
    (
        "pypdfbox.debugger.streampane.stream_text_view",
        "StreamTextView",
        "ancestor_removed",
    ),
    (
        "pypdfbox.debugger.streampane.stream_text_view",
        "StreamTextView",
        "ancestor_moved",
    ),
    (
        "pypdfbox.debugger.treestatus.tree_status_pane",
        "TreeStatusPane",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.ui.reader_bottom_panel",
        "ReaderBottomPanel",
        "mouse_clicked",
    ),
    (
        "pypdfbox.debugger.ui.textsearcher.search_panel",
        "SearchPanel",
        "action_performed",
    ),
    (
        "pypdfbox.debugger.ui.textsearcher.searcher",
        "Searcher",
        "action_performed",
    ),
]


@pytest.mark.parametrize(
    ("module_path", "class_name", "method_name"),
    _METHOD_PARITY_MATRIX,
    ids=[f"{c}.{m}" for _, c, m in _METHOD_PARITY_MATRIX],
)
def test_method_exists(module_path: str, class_name: str, method_name: str) -> None:
    """Every method flagged in the wave-1388 audit now exists on its class."""
    module = __import__(module_path, fromlist=[class_name])
    cls = getattr(module, class_name)
    assert hasattr(cls, method_name), (
        f"{class_name}.{method_name} missing (wave-1389 should have added it)"
    )
    attr = getattr(cls, method_name)
    assert callable(attr), f"{class_name}.{method_name} exists but is not callable"


# ---------------------------------------------------------------------------
# Logic-only tests (no Tk widgets created — safe headless)
# ---------------------------------------------------------------------------


def test_pdf_debugger_is_predicates_dispatch_to_private() -> None:
    """The public ``is_*`` predicates resolve to the same answers as the
    underscore-prefixed implementations.
    """
    from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
    from pypdfbox.debugger.pd_debugger import PDFDebugger

    # Page dict
    page_dict = COSDictionary()
    page_dict.set_item("Type", COSName.get_pdf_name("Page"))
    assert PDFDebugger.is_page(page_dict) is True
    assert PDFDebugger.is_page(page_dict) == PDFDebugger._is_page(page_dict)

    # Stream
    stream = COSStream(COSDictionary())
    assert PDFDebugger.is_stream(stream) is True
    assert PDFDebugger.is_stream(stream) == PDFDebugger._is_stream(stream)

    # String
    cos_string = COSString("hello")
    assert PDFDebugger.is_string(cos_string) is True
    assert PDFDebugger.is_string(cos_string) == PDFDebugger._is_string(cos_string)

    # Font (non-CID)
    font_dict = COSDictionary()
    font_dict.set_item("Type", COSName.get_pdf_name("Font"))
    assert PDFDebugger.is_font(font_dict) is True
    assert PDFDebugger.is_font(font_dict) == PDFDebugger._is_font(font_dict)

    # Non-font / non-page dict
    arbitrary = COSDictionary()
    assert PDFDebugger.is_page(arbitrary) is False
    assert PDFDebugger.is_font(arbitrary) is False


def test_pdf_debugger_is_annot_and_font_descriptor() -> None:
    """``is_annot`` / ``is_font_descriptor`` recognise the right ``/Type``s."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.debugger.pd_debugger import PDFDebugger

    annot_dict = COSDictionary()
    annot_dict.set_item("Type", COSName.get_pdf_name("Annot"))
    assert PDFDebugger.is_annot(annot_dict) is True

    fd_dict = COSDictionary()
    fd_dict.set_item("Type", COSName.get_pdf_name("FontDescriptor"))
    assert PDFDebugger.is_font_descriptor(fd_dict) is True

    # Unrelated dict
    other = COSDictionary()
    other.set_item("Type", COSName.get_pdf_name("XObject"))
    assert PDFDebugger.is_annot(other) is False
    assert PDFDebugger.is_font_descriptor(other) is False


def test_pdf_debugger_is_special_and_other_colorspace() -> None:
    """The special / other colour-space predicates dispatch on the first array name."""
    from pypdfbox.cos import COSArray, COSName
    from pypdfbox.debugger.pd_debugger import PDFDebugger

    # Per pd_debugger._SPECIAL_COLORSPACES: {Indexed, Separation, DeviceN}
    indexed_array = COSArray()
    indexed_array.add(COSName.get_pdf_name("Indexed"))
    assert PDFDebugger.is_special_color_space(indexed_array) is True
    assert PDFDebugger.is_other_color_space(indexed_array) is False

    # Per _OTHER_COLORSPACES: {ICCBased, Pattern, CalGray, CalRGB, Lab}
    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    assert PDFDebugger.is_other_color_space(icc_array) is True
    assert PDFDebugger.is_special_color_space(icc_array) is False

    pattern_array = COSArray()
    pattern_array.add(COSName.get_pdf_name("Pattern"))
    assert PDFDebugger.is_other_color_space(pattern_array) is True
    assert PDFDebugger.is_special_color_space(pattern_array) is False


def test_pdf_debugger_public_predicates_match_classmethod_shape() -> None:
    """The public predicates are class-level callable (``classmethod``)."""
    from pypdfbox.debugger.pd_debugger import PDFDebugger

    # Each predicate should be callable both via the class and via an
    # instance — same surface as upstream Java statics.
    for attr in (
        "is_page",
        "is_stream",
        "is_string",
        "is_font",
        "is_font_descriptor",
        "is_annot",
        "is_encrypt",
        "is_signature",
        "is_special_color_space",
        "is_other_color_space",
        "is_flag_node",
    ):
        assert callable(getattr(PDFDebugger, attr)), attr


def test_g_tool_tip_create_mark_up_is_public_and_back_compat() -> None:
    """``create_mark_up`` is public; the underscore alias still works."""
    from pypdfbox.debugger.streampane.tooltip.g_tool_tip import GToolTip

    # Method exists on the class and is callable.
    assert hasattr(GToolTip, "create_mark_up")
    assert hasattr(GToolTip, "_create_markup")
    assert GToolTip._create_markup is GToolTip.create_mark_up


def test_rg_tool_tip_create_mark_up_is_public_and_back_compat() -> None:
    from pypdfbox.debugger.streampane.tooltip.rg_tool_tip import RGToolTip

    assert hasattr(RGToolTip, "create_mark_up")
    assert hasattr(RGToolTip, "_create_markup")
    assert RGToolTip._create_markup is RGToolTip.create_mark_up


def test_scn_tool_tip_create_mark_up_is_public_and_back_compat() -> None:
    from pypdfbox.debugger.streampane.tooltip.scn_tool_tip import SCNToolTip

    assert hasattr(SCNToolTip, "create_mark_up")
    assert hasattr(SCNToolTip, "_create_markup")
    assert SCNToolTip._create_markup is SCNToolTip.create_mark_up


def test_g_tool_tip_create_mark_up_round_trip() -> None:
    """Building a GToolTip exercises the new public ``create_mark_up`` path."""
    from pypdfbox.debugger.streampane.tooltip.g_tool_tip import GToolTip

    tip = GToolTip("0.5 g")
    text = tip.get_tool_tip_text()
    # Whichever shape the markup wraps the swatch hex in, the row text
    # must have produced *some* tooltip text (the gray 0.5 -> #7F or #80
    # depending on rounding — both end in a hex digit).
    assert text is not None
    assert text.plain or text.segments


# ---------------------------------------------------------------------------
# Light-touch UI smoke tests (require a Tk display)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not DISPLAY_AVAILABLE,
    reason="no Tk display available (set DISPLAY or run on macOS)",
)
def test_upper_pane_paint_component_idempotent(tk_root) -> None:  # type: ignore[no-untyped-def]
    """``UpperPane.paint_component`` builds the banner and can be re-invoked."""
    from pypdfbox.debugger.hexviewer.upper_pane import UpperPane

    pane = UpperPane(tk_root)
    pane.update_idletasks()
    first_count = len(pane.winfo_children())
    assert first_count == 3  # Offset label + cols label + Text label

    # Re-invoking paint_component should rebuild rather than stack.
    pane.paint_component()
    pane.update_idletasks()
    assert len(pane.winfo_children()) == 3


@pytest.mark.skipif(
    not DISPLAY_AVAILABLE,
    reason="no Tk display available (set DISPLAY or run on macOS)",
)
def test_status_pane_create_view_builds_labels(tk_root) -> None:  # type: ignore[no-untyped-def]
    """``StatusPane.create_view`` populates the Line / Column / Index labels."""
    from pypdfbox.debugger.hexviewer.status_pane import StatusPane

    pane = StatusPane(tk_root)
    pane.update_idletasks()
    # 6 labels total: Line:/value/Column:/value/Index:/value.
    assert len(pane.winfo_children()) == 6


@pytest.mark.skipif(
    not DISPLAY_AVAILABLE,
    reason="no Tk display available (set DISPLAY or run on macOS)",
)
def test_reader_bottom_panel_mouse_clicked_safe_with_no_dialog(tk_root) -> None:  # type: ignore[no-untyped-def]
    """``ReaderBottomPanel.mouse_clicked(None)`` is a no-crash no-op when no
    LogDialog instance exists.
    """
    from pypdfbox.debugger.ui.log_dialog import LogDialog
    from pypdfbox.debugger.ui.reader_bottom_panel import ReaderBottomPanel

    # Clear any singleton state from sibling tests.
    LogDialog._instance = None  # noqa: SLF001 — explicit test-only reset
    panel = ReaderBottomPanel(tk_root)
    panel.init()
    # Without a LogDialog the click handler should bail safely.
    panel.mouse_clicked(None)
