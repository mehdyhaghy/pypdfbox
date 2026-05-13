"""Tests for :class:`StreamPane`."""

from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.debugger.streampane.stream_pane import StreamPane


def _content_stream() -> COSStream:
    stream = COSStream()
    stream.set_data(b"BT /F1 12 Tf (hello) Tj ET\n")
    return stream


def _image_stream() -> COSStream:
    stream = COSStream()
    stream.set_item("Type", COSName.get_pdf_name("XObject"))
    stream.set_item("Subtype", COSName.get_pdf_name("Image"))
    stream.set_data(b"\x00" * 16)
    return stream


def test_content_stream_pane_builds_nice_and_raw_views(tk_root) -> None:
    pane = StreamPane(tk_root, _content_stream(), is_content_stream=True, is_thumb=False)
    pane.init()
    # Three tabs: Nice / Raw / Hex.
    tabs = pane._notebook.tabs()  # noqa: SLF001 — internal accessor
    assert len(tabs) == 3


def test_non_content_stream_pane_builds_text_and_hex(tk_root) -> None:
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )
    pane.init()
    tabs = pane._notebook.tabs()  # noqa: SLF001
    assert len(tabs) == 2


def test_image_stream_pane_only_has_image_tab(tk_root) -> None:
    pane = StreamPane(
        tk_root, _image_stream(), is_content_stream=False, is_thumb=False
    )
    pane.init()
    tabs = pane._notebook.tabs()  # noqa: SLF001
    assert len(tabs) == 1


def test_get_panel_returns_frame(tk_root) -> None:
    pane = StreamPane(tk_root, _content_stream(), is_content_stream=True, is_thumb=False)
    pane.init()
    assert pane.get_panel() is not None
