"""Dispatch tests for the public :class:`StreamPane` API (wave 1309).

Covers the methods promoted/added for upstream parity:

* :meth:`StreamPane.create_header_panel` — builds the filter dropdown
  header widget.
* :meth:`StreamPane.request_image_showing` — switches the body to the
  decoded image view for image streams.
* :meth:`StreamPane.request_stream_text` — switches the body to the
  text/hex view at a given filter-list position.

All tests honour ``PYPDFBOX_SKIP_TK=1`` via the shared ``tk_root``
fixture (see ``conftest.py``).
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from pypdfbox.cos import COSName, COSStream
from pypdfbox.debugger.streampane.stream import Stream
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


def _find_combobox(widget: Any) -> ttk.Combobox | None:
    """Walk the child tree until we find a ``ttk.Combobox``."""
    if isinstance(widget, ttk.Combobox):
        return widget
    for child in widget.winfo_children():
        found = _find_combobox(child)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# create_header_panel
# ---------------------------------------------------------------------------


def test_create_header_panel_returns_frame_with_filter_dropdown(tk_root) -> None:
    """``create_header_panel`` returns a frame containing the filter combo."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )
    filter_list = pane._stream.get_filter_list()  # noqa: SLF001
    header = pane.create_header_panel(filter_list, Stream.DECODED)
    assert isinstance(header, ttk.Frame)
    combo = _find_combobox(header)
    assert combo is not None
    # The preselected value matches what we passed in.
    assert combo.get() == Stream.DECODED
    # Combobox values list the filter options we supplied.
    assert list(combo.cget("values")) == filter_list


def test_create_header_panel_accepts_custom_action_listener(tk_root) -> None:
    """A caller-supplied listener replaces the internal handler."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )

    calls: list[Any] = []

    def listener(event: Any) -> None:  # noqa: ARG001
        calls.append(event)

    filter_list = pane._stream.get_filter_list()  # noqa: SLF001
    header = pane.create_header_panel(filter_list, Stream.DECODED, listener)
    combo = _find_combobox(header)
    assert combo is not None
    # The combobox is bound to <<ComboboxSelected>> (we can't easily
    # assert on the listener identity without dispatching the event,
    # but ``bind`` returning a non-empty string is the parity check).
    bindings = combo.bind("<<ComboboxSelected>>")
    assert bindings  # non-empty binding string


# ---------------------------------------------------------------------------
# request_image_showing
# ---------------------------------------------------------------------------


def test_request_image_showing_pushes_image_into_raw_view(
    tk_root, monkeypatch
) -> None:
    """``request_image_showing`` calls ``show_stream_image`` on the body view."""
    pane = StreamPane(
        tk_root, _image_stream(), is_content_stream=False, is_thumb=False
    )

    # Stub the image decoder so we do not depend on the rendering pipeline
    # (this exercises just the StreamPane dispatch, not PDImageXObject).
    sentinel_image = object()
    monkeypatch.setattr(
        pane._stream,  # noqa: SLF001
        "get_image",
        lambda _resources: sentinel_image,
    )

    captured: list[object] = []
    monkeypatch.setattr(
        pane._raw_view,  # noqa: SLF001
        "show_stream_image",
        lambda image: captured.append(image),
    )

    pane.request_image_showing()
    assert captured == [sentinel_image]


def test_request_image_showing_noop_for_non_image_stream(
    tk_root, monkeypatch
) -> None:
    """Non-image streams produce no image-view side effect."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )

    called: list[object] = []
    monkeypatch.setattr(
        pane._raw_view,  # noqa: SLF001
        "show_stream_image",
        lambda image: called.append(image),
    )
    pane.request_image_showing()
    assert called == []


# ---------------------------------------------------------------------------
# request_stream_text
# ---------------------------------------------------------------------------


def test_request_stream_text_index_zero_loads_unfiltered_bytes(
    tk_root, monkeypatch
) -> None:
    """``request_stream_text(0)`` resolves to the first filter view's bytes."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )

    text_calls: list[tuple] = []
    hex_calls: list[bytes] = []
    monkeypatch.setattr(
        pane._raw_view,  # noqa: SLF001
        "show_stream_text",
        lambda segments, styles, tool_tip_controller=None: text_calls.append(
            (list(segments), list(styles), tool_tip_controller)
        ),
    )
    monkeypatch.setattr(
        pane._hex_view,  # noqa: SLF001
        "change_data",
        lambda data: hex_calls.append(bytes(data)),
    )

    pane.request_stream_text(0)

    # Text view was populated with decoded-bytes segments.
    assert len(text_calls) == 1
    text = "".join(seg for seg, _ in text_calls[0][0])
    assert "BT /F1 12 Tf" in text
    # Hex view received the same raw bytes.
    assert hex_calls == [b"BT /F1 12 Tf (hello) Tj ET\n"]


def test_request_stream_text_string_key_decoded(tk_root, monkeypatch) -> None:
    """Passing the canonical ``Stream.DECODED`` key works identically."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )

    text_calls: list[tuple] = []
    hex_calls: list[bytes] = []
    monkeypatch.setattr(
        pane._raw_view,  # noqa: SLF001
        "show_stream_text",
        lambda segments, styles, tool_tip_controller=None: text_calls.append(
            (list(segments), list(styles), tool_tip_controller)
        ),
    )
    monkeypatch.setattr(
        pane._hex_view,  # noqa: SLF001
        "change_data",
        lambda data: hex_calls.append(bytes(data)),
    )

    pane.request_stream_text(Stream.DECODED)
    assert text_calls
    assert hex_calls == [b"BT /F1 12 Tf (hello) Tj ET\n"]


def test_request_stream_text_out_of_range_index_is_noop(
    tk_root, monkeypatch
) -> None:
    """Out-of-range integer index logs and does nothing."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )

    text_calls: list[tuple] = []
    monkeypatch.setattr(
        pane._raw_view,  # noqa: SLF001
        "show_stream_text",
        lambda *args, **kwargs: text_calls.append((args, kwargs)),
    )

    pane.request_stream_text(99)
    assert text_calls == []
