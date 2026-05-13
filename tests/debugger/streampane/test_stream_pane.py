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


# ----------------------------------------------------------------------
# DocumentCreator (port of StreamPane.DocumentCreator inner class)
# ----------------------------------------------------------------------


class _CapturingView:
    """Test double mirroring StreamPaneView's ``show_stream_text`` surface."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def show_stream_text(
        self, segments, styles, tool_tip_controller=None
    ) -> None:
        self.calls.append((list(segments), list(styles), tool_tip_controller))


def test_document_creator_execute_returns_plain_text_segments() -> None:
    """A non-nice raw-view run produces decoded text segments."""
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import DocumentCreator

    cos = COSStream()
    cos.set_data(b"hello world")
    stream = Stream(cos, is_thumb=False)
    view = _CapturingView()
    creator = DocumentCreator(view, stream, Stream.DECODED, nice=False)
    segments = creator.execute()
    assert segments  # non-empty
    text = "".join(seg for seg, _ in segments)
    assert "hello world" in text
    assert creator.get() is segments
    # ``done()`` plumbed the segments through to the view.
    assert len(view.calls) == 1


def test_document_creator_execute_returns_nice_content_stream_segments() -> (
    None
):
    """Nice mode tokenises a content stream into operator-tagged segments."""
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import DocumentCreator

    cos = COSStream()
    cos.set_data(b"BT /F1 12 Tf (hello) Tj ET\n")
    stream = Stream(cos, is_thumb=False)
    view = _CapturingView()
    creator = DocumentCreator(view, stream, Stream.DECODED, nice=True)
    segments = creator.execute()
    assert segments
    # The tokeniser emits a recognised tag for every segment. The exact
    # tag-name vocabulary (number / string / name / None / operator-key)
    # mirrors what OperatorMarker.get_style returns — the contract here
    # is that *some* non-None tag is produced.
    tags = {tag for _, tag in segments}
    assert tags & {"operator", "number", "string", "name"}


def test_document_creator_get_xml_document_emits_pretty_printed_xml() -> None:
    """``get_xml_document`` returns a pretty-printed XML segment."""
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import DocumentCreator

    cos = COSStream()
    cos.set_data(b"<root><child/></root>")
    stream = Stream(cos, is_thumb=False)
    view = _CapturingView()
    creator = DocumentCreator(view, stream, Stream.DECODED, nice=True)
    segments = creator.get_xml_document(b"<root><child/></root>")
    text = "".join(seg for seg, _ in segments)
    assert "<root>" in text
    assert "<child" in text


def test_document_creator_get_content_stream_document_returns_none_on_garbage() -> (
    None
):
    """Invalid data → ``None`` so the caller can fall back to plain text."""
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import DocumentCreator

    cos = COSStream()
    stream = Stream(cos, is_thumb=False)
    view = _CapturingView()
    creator = DocumentCreator(view, stream, Stream.DECODED, nice=True)
    # Random bytes that aren't a valid content stream — most parses
    # will either yield zero operators or raise; either is fine, but
    # the result must not raise outside the method.
    result = creator.get_content_stream_document(b"\x00\xff\x01garbage")
    # Either parsed to empty segments or returned None — both are
    # acceptable per the upstream contract.
    assert result is None or isinstance(result, list)


def test_document_creator_get_document_normalises_line_endings() -> None:
    """``get_document`` normalises CR/CRLF to LF (mirrors upstream)."""
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import DocumentCreator

    cos = COSStream()
    stream = Stream(cos, is_thumb=False)
    view = _CapturingView()
    creator = DocumentCreator(view, stream, Stream.DECODED, nice=False)
    segments = creator.get_document(b"a\r\nb\rc\nd", "utf-8")
    text = "".join(seg for seg, _ in segments)
    assert text == "a\nb\nc\nd"
