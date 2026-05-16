"""Tkinter port of ``org.apache.pdfbox.debugger.streampane.StreamPane``.

Top-level widget that displays a ``COSStream`` to the user as either
syntax-highlighted text (content streams, XML metadata) or a decoded
image (Image XObjects). A filter-chain :class:`ttk.Combobox` lets the
user pick which view of the stream to see.

The Swing original wires the heavy parsing onto a ``SwingWorker``; we
run it inline on the Tk main thread — content streams are small enough
that this is not a perceptible cost, and Tkinter has no equivalent
background-then-fold-back idiom.
"""

from __future__ import annotations

import contextlib
import logging
import re
import tkinter as tk
from collections.abc import Iterable
from tkinter import ttk
from typing import Any

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
    COSNull,
    COSNumber,
    COSStream,
    COSString,
)
from pypdfbox.debugger.hexviewer.hex_view import HexView
from pypdfbox.debugger.streampane.operator_marker import OperatorMarker
from pypdfbox.debugger.streampane.stream import Stream
from pypdfbox.debugger.streampane.stream_pane_view import StreamPaneView
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser

_LOG = logging.getLogger(__name__)

# Style tag names + the ``tag_configure`` keyword arguments to apply.
# Colors mirror upstream's ``StyleConstants.setForeground`` literals.
_OPERATOR_STYLE: tuple[str, dict[str, Any]] = (
    "operator",
    {"foreground": "#19379c"},
)
_NUMBER_STYLE: tuple[str, dict[str, Any]] = ("number", {"foreground": "#335612"})
_STRING_STYLE: tuple[str, dict[str, Any]] = ("string", {"foreground": "#802320"})
_ESCAPE_STYLE: tuple[str, dict[str, Any]] = ("escape", {"foreground": "#b33124"})
_NAME_STYLE: tuple[str, dict[str, Any]] = ("name", {"foreground": "#8c2691"})
_INLINE_IMAGE_STYLE: tuple[str, dict[str, Any]] = (
    "inline_image",
    {"foreground": "#747127"},
)

_LINE_BREAK_RE = re.compile(r"\r\n|\r|\n")


class StreamPane:
    """Dispatcher that builds the appropriate view for a ``COSStream``."""

    def __init__(
        self,
        master: tk.Misc | None,
        cos_stream: COSStream,
        is_content_stream: bool,
        is_thumb: bool,
        resources_dic: COSDictionary | None = None,
    ) -> None:
        """Build the pane.

        :param master: parent Tkinter widget.
        :param cos_stream: the underlying stream.
        :param is_content_stream: ``True`` when the stream is a page
            content stream (drives the "nice view" toggle).
        :param is_thumb: ``True`` when the stream is a ``/Thumb`` image.
        :param resources_dic: optional ``/Resources`` dictionary for the
            stream's drawing context — required for XObject lookups in
            inline image decoding.
        """
        self._stream = Stream(cos_stream, is_thumb)
        self._resources: object | None = None
        if resources_dic is not None:
            # Lazy import — pdmodel may not be on the import path during
            # purely-data unit tests of StreamPane construction.
            from pypdfbox.pdmodel.pd_resources import PDResources

            self._resources = PDResources(resources_dic)

        self._panel = ttk.Frame(master)
        with contextlib.suppress(tk.TclError):
            self._panel.configure(width=300, height=500)

        self._raw_view = StreamPaneView(self._panel)
        self._hex_view = HexView(self._panel, b"")
        if is_content_stream or self._stream.is_xml_metadata():
            self._nice_view: StreamPaneView | None = StreamPaneView(self._panel)
        else:
            self._nice_view = None

        self._notebook = ttk.Notebook(self._panel)
        self._filter_combo: ttk.Combobox | None = None

    # ---- public API --------------------------------------------------------

    def init(self) -> None:
        """Mirror upstream's ``init()`` — must be called after construction."""
        if self._stream.is_image():
            self._panel.pack_propagate(False)
            header = self.create_header_panel(
                self._stream.get_filter_list(), Stream.IMAGE
            )
            header.pack(fill="x")
            self.request_image_showing()
        else:
            header = self.create_header_panel(
                self._stream.get_filter_list(), Stream.DECODED
            )
            header.pack(fill="x")
            self.request_stream_text(Stream.DECODED)

        if self._stream.is_image():
            self._notebook.add(self._raw_view.get_stream_panel(), text="Image view")
        elif self._nice_view is not None:
            self._notebook.add(self._nice_view.get_stream_panel(), text="Nice view")
            self._notebook.add(self._raw_view.get_stream_panel(), text="Raw view")
            self._notebook.add(self._hex_view.get_pane(), text="Hex view")
        else:
            self._notebook.add(self._raw_view.get_stream_panel(), text="Text view")
            self._notebook.add(self._hex_view.get_pane(), text="Hex view")

        self._notebook.pack(fill="both", expand=True)

    def get_panel(self) -> ttk.Frame:
        """Return the top-level container."""
        return self._panel

    # ---- internals ---------------------------------------------------------

    def create_header_panel(
        self,
        available_filters: list[str],
        selected: str,
        action_listener: Any | None = None,
    ) -> ttk.Frame:
        """Build and return the top filter-selector header.

        Mirrors upstream's private ``createHeaderPanel(List<String>,
        String, ActionListener)``: assembles a combobox of filter view
        labels with ``selected`` preselected, and returns the
        :class:`ttk.Frame` container. Callers are responsible for
        ``pack``/``grid``ing the returned frame.

        The ``action_listener`` parameter is accepted for upstream API
        parity (upstream takes a Swing ``ActionListener``) — Tk has no
        direct equivalent. When ``None`` (default) the internal
        ``<<ComboboxSelected>>`` handler is wired up, which dispatches
        through :meth:`request_image_showing` / :meth:`request_stream_text`
        the same way upstream's ``actionPerformed`` does.
        """
        header = ttk.Frame(self._panel)
        combo = ttk.Combobox(
            header,
            values=available_filters,
            state="readonly",
        )
        if selected in available_filters:
            combo.set(selected)
        if action_listener is None:
            combo.bind("<<ComboboxSelected>>", self._on_filter_changed)
        else:
            combo.bind("<<ComboboxSelected>>", action_listener)
        combo.pack(side="left", padx=4, pady=4)
        self._filter_combo = combo
        return header

    # Back-compat private alias — existing call sites used ``_build_header``.
    def _build_header(self, available_filters: list[str], selected: str) -> None:
        header = self.create_header_panel(available_filters, selected)
        header.pack(fill="x")

    def _on_filter_changed(self, _event: tk.Event[Any] | None = None) -> None:
        if self._filter_combo is None:
            return
        current_filter = self._filter_combo.get()
        try:
            if current_filter == Stream.IMAGE:
                self.request_image_showing()
                self._rebuild_notebook([
                    (self._raw_view.get_stream_panel(), "Image view"),
                ])
                return
            if current_filter == Stream.DECODED and self._nice_view is not None:
                self._rebuild_notebook([
                    (self._nice_view.get_stream_panel(), "Nice view"),
                    (self._raw_view.get_stream_panel(), "Raw view"),
                    (self._hex_view.get_pane(), "Hex view"),
                ])
            else:
                self._rebuild_notebook([
                    (self._raw_view.get_stream_panel(), "Text view"),
                    (self._hex_view.get_pane(), "Hex view"),
                ])
            self.request_stream_text(current_filter)
        except OSError as exc:
            _LOG.error("%s", exc)

    def _rebuild_notebook(self, tabs: Iterable[tuple[Any, str]]) -> None:
        for tab_id in self._notebook.tabs():
            self._notebook.forget(tab_id)
        for widget, label in tabs:
            self._notebook.add(widget, text=label)

    def request_image_showing(self) -> None:
        """Decode the underlying stream as an image and display it.

        Mirrors upstream's private ``requestImageShowing()``. No-op when
        the stream is not an image. On decode failure, upstream pops a
        Swing ``JOptionPane``; we log and leave the image tab empty so
        the debugger main loop / headless tests are not blocked by a
        modal dialog (deviation noted in CHANGES.md).
        """
        if not self._stream.is_image():
            return
        image = self._stream.get_image(self._resources)
        if image is None:
            _LOG.warning("image not available (filter missing?)")
            return
        self._raw_view.show_stream_image(image)

    # Back-compat private alias.
    _request_image_showing = request_image_showing

    def request_stream_text(self, command: str | int) -> None:
        """Populate the text + hex views with the bytes at ``command``.

        Mirrors upstream's private ``requestStreamText(String)``. The
        ``command`` is a filter-list label (typically ``Stream.DECODED``
        or one of the partial-decode entries). As a pypdfbox convenience
        (and to match parity tooling), an integer is accepted as an
        index into :meth:`Stream.get_filter_list` — ``0`` selects the
        first filter view (``Stream.DECODED`` for non-image streams,
        ``Stream.IMAGE`` for image streams). On read failure, upstream
        pops a Swing ``JOptionPane``; we log and return (see CHANGES.md).
        """
        if isinstance(command, int):
            filter_list = self._stream.get_filter_list()
            if 0 <= command < len(filter_list):
                command = filter_list[command]
            else:
                _LOG.warning("filter index %d out of range", command)
                return

        # Populate raw view (always plain bytes).
        segments_raw = self._build_segments(command, nice=False)
        self._raw_view.show_stream_text(
            segments_raw, _default_styles(), tool_tip_controller=None
        )

        if self._nice_view is not None:
            segments_nice = self._build_segments(command, nice=True)
            self._nice_view.show_stream_text(
                segments_nice, _default_styles(), tool_tip_controller=None
            )

        # Update hex view with the raw bytes for this filter view.
        in_stream = self._stream.get_stream(command)
        if in_stream is None:
            _LOG.warning("%s text not available (filter missing?)", command)
            return
        with in_stream as src:
            data = src.read()
        self._hex_view.change_data(data)

    # Back-compat private alias.
    _request_stream_text = request_stream_text

    # ---- segment construction ---------------------------------------------

    def _build_segments(
        self, command: str, nice: bool
    ) -> list[tuple[str, str | None]]:
        """Return ``(text, tag_or_None)`` runs to feed into a StreamTextView."""
        encoding = "utf-8" if self._stream.is_xml_metadata() else "iso-8859-1"
        in_stream = self._stream.get_stream(command)
        if in_stream is None:
            return []
        with in_stream as src:
            raw = src.read()

        if nice and command == Stream.DECODED:
            if self._stream.is_xml_metadata():
                return _xml_segments(raw)
            content_segments = self._content_stream_segments(raw)
            if content_segments is not None:
                return content_segments
        return _plain_text_segments(raw, encoding)

    def _content_stream_segments(
        self, data: bytes
    ) -> list[tuple[str, str | None]] | None:
        try:
            parser = PDFStreamParser.from_bytes(data)
            tokens = parser.parse()
        except OSError:
            return None
        except Exception as exc:  # noqa: BLE001
            _LOG.error("content-stream parse failed: %s", exc)
            return None

        emitter = _ContentStreamEmitter()
        for token in tokens:
            emitter.write_token(token)
        return emitter.segments


def _default_styles() -> list[tuple[str, dict[str, Any]]]:
    """Return the canonical tag-configure pairs used by the content view."""
    styles: list[tuple[str, dict[str, Any]]] = [
        _OPERATOR_STYLE,
        _NUMBER_STYLE,
        _STRING_STYLE,
        _ESCAPE_STYLE,
        _NAME_STYLE,
        _INLINE_IMAGE_STYLE,
    ]
    # Operator-specific overrides from :class:`OperatorMarker` — these
    # tags are referenced by name when the emitter encounters a matching
    # operator. We register them under their operator-keyed names so
    # ``StreamTextView`` can resolve the tag at insert time.
    for op_name in (
        OperatorName.BEGIN_TEXT,
        OperatorName.END_TEXT,
        OperatorName.SAVE,
        OperatorName.RESTORE,
        OperatorName.CONCAT,
        OperatorName.BEGIN_INLINE_IMAGE,
        OperatorName.BEGIN_INLINE_IMAGE_DATA,
        OperatorName.END_INLINE_IMAGE,
    ):
        style = OperatorMarker.get_style(op_name)
        if style is not None:
            kwargs = {k: v for k, v in style.items() if k != "weight"}
            styles.append((f"op_{op_name}", kwargs))
    return styles


def _plain_text_segments(
    data: bytes, encoding: str
) -> list[tuple[str, str | None]]:
    """Decode ``data`` as text and normalise CR/CRLF → LF (matches upstream)."""
    text = data.decode(encoding, errors="replace")
    text = _LINE_BREAK_RE.sub("\n", text)
    return [(text, None)]


def _xml_segments(data: bytes) -> list[tuple[str, str | None]]:
    """Format an XML payload with rudimentary indentation."""
    # Upstream uses a TransformerFactory with INDENT=yes. We do a
    # minimal pretty-print via ElementTree to avoid an XML dep.
    import xml.dom.minidom as _minidom

    try:
        doc = _minidom.parseString(data)
        pretty = doc.toprettyxml(indent="  ")
        # Drop blank lines introduced by toprettyxml.
        pretty = "\n".join(line for line in pretty.splitlines() if line.strip())
        return [(pretty, None)]
    except Exception:  # noqa: BLE001 — fall back to raw text on parse failure
        return _plain_text_segments(data, "utf-8")


class _ContentStreamEmitter:
    """Convert parsed content-stream tokens into styled text segments."""

    def __init__(self) -> None:
        self.segments: list[tuple[str, str | None]] = []
        self._indent = 0
        self._need_indent = False

    def write_token(self, obj: object) -> None:
        try:
            if isinstance(obj, Operator):
                self._add_operator(obj)
            else:
                self._write_operand(obj)
        except (ValueError, AttributeError) as exc:
            _LOG.error("token emit failed: %s", exc)

    # ---- operands ----------------------------------------------------------

    def _write_operand(self, obj: object) -> None:
        self._write_indent()
        if isinstance(obj, COSName):
            self._emit("/" + obj.get_name() + " ", _NAME_STYLE[0])
        elif isinstance(obj, COSBoolean):
            self._emit(str(obj.get_value()).lower() + " ", None)
        elif isinstance(obj, COSArray):
            self._emit("[ ", None)
            for i in range(obj.size()):
                self._write_operand(obj.get(i))
            self._emit("] ", None)
        elif isinstance(obj, COSString):
            self._emit_cos_string(obj)
        elif isinstance(obj, COSNumber):
            text = (
                str(obj.float_value())
                if isinstance(obj, COSFloat)
                else str(obj.int_value())
            )
            self._emit(text + " ", _NUMBER_STYLE[0])
        elif isinstance(obj, COSDictionary):
            self._emit("<< ", None)
            for key, value in obj.entry_set():
                self._write_operand(key)
                self._write_operand(value)
            self._emit(">> ", None)
        elif isinstance(obj, COSNull):
            self._emit("null ", None)
        else:
            text = repr(obj)
            # Upstream trims the surrounding ``{...}`` from
            # ``Object.toString()`` — mirror by stripping the first
            # ``{`` ... last ``}`` if present.
            if "{" in text and text.endswith("}"):
                text = text[text.index("{") + 1 : -1]
            self._emit(text + " ", None)

    def _emit_cos_string(self, obj: COSString) -> None:
        self._emit("(", None)
        for byte_value in obj.get_bytes():
            chr_value = byte_value & 0xFF
            if chr_value in (0x28, 0x29, 0x5C):  # ( ) \
                self._emit("\\" + chr(chr_value), _ESCAPE_STYLE[0])
            elif chr_value < 0x20 or chr_value > 0x7E:
                self._emit(f"\\{chr_value:03o}", _ESCAPE_STYLE[0])
            else:
                self._emit(chr(chr_value), _STRING_STYLE[0])
        self._emit(") ", None)

    # ---- operators ---------------------------------------------------------

    def _add_operator(self, op: Operator) -> None:
        name = op.get_name()
        if name in (
            OperatorName.END_TEXT,
            OperatorName.RESTORE,
            OperatorName.END_MARKED_CONTENT,
        ):
            self._indent = max(0, self._indent - 1)
        self._write_indent()

        if name == OperatorName.BEGIN_INLINE_IMAGE:
            self._emit(OperatorName.BEGIN_INLINE_IMAGE + "\n", _OPERATOR_STYLE[0])
            params = op.get_image_parameters()
            if params is not None:
                for key in params.key_set() if hasattr(params, "key_set") else params:
                    value = params.get_dictionary_object(key)
                    self._emit("/" + key.get_name() + " ", None)
                    self.write_token(value)
                    self._emit("\n", None)
            image_data = op.get_image_data() or b""
            image_string = image_data.decode("iso-8859-1", errors="replace")
            self._emit(
                OperatorName.BEGIN_INLINE_IMAGE_DATA + "\n", _INLINE_IMAGE_STYLE[0]
            )
            self._emit(image_string + "\n", None)
            self._emit(OperatorName.END_INLINE_IMAGE + "\n", _OPERATOR_STYLE[0])
        else:
            self._emit(name + "\n", _OPERATOR_STYLE[0])
            if name in (
                OperatorName.BEGIN_TEXT,
                OperatorName.SAVE,
                OperatorName.BEGIN_MARKED_CONTENT,
                OperatorName.BEGIN_MARKED_CONTENT_SEQ,
            ):
                self._indent += 1
        self._need_indent = True

    # ---- low-level emit ----------------------------------------------------

    def _write_indent(self) -> None:
        if self._need_indent:
            if self._indent:
                self._emit("  " * self._indent, None)
            self._need_indent = False

    def _emit(self, text: str, tag: str | None) -> None:
        self.segments.append((text, tag))


class DocumentCreator:
    """Synchronous port of ``StreamPane.DocumentCreator`` (PDFBox 3.0).

    Upstream extends ``SwingWorker<StyledDocument, Integer>`` and runs
    the stream→styled-document conversion off the EDT. As with
    :class:`RenderWorker`, our Tk port runs synchronously — content-
    stream parsing is fast enough not to warrant a thread and the
    stdlib offers no equivalent worker idiom. Behavioural deviation
    is documented in CHANGES.md.

    Produces a list of ``(text, tag)`` segments compatible with
    :class:`StreamPaneView.show_stream_text` (the Tk analogue of
    Swing's ``StyledDocument``).
    """

    def __init__(
        self,
        target_view: Any,
        stream: Stream,
        filter_key: str,
        nice: bool,
    ) -> None:
        """Construct the creator.

        :param target_view: :class:`StreamPaneView`-like sink for
            :meth:`done` to call ``show_stream_text`` on.
        :param stream: :class:`Stream` wrapper around the underlying
            ``COSStream`` (provides ``get_stream`` /
            ``is_xml_metadata``).
        :param filter_key: filter selection (see :class:`Stream`
            constants — typically ``Stream.DECODED`` /
            ``Stream.IMAGE``).
        :param nice: if ``True``, prefer the operator-tokenised "nice"
            view for content streams / pretty-printed XML for metadata.
        """
        self._target_view = target_view
        self._stream = stream
        self._filter_key = filter_key
        self._nice = bool(nice)
        self._result: list[tuple[str, str | None]] | None = None

    # ------------------------------------------------------------------
    # Public lifecycle (mirrors SwingWorker)
    # ------------------------------------------------------------------

    def execute(self) -> list[tuple[str, str | None]]:
        """Run the creator end-to-end and return the segments produced."""
        segments = self.do_in_background()
        self._result = segments
        self.done()
        return segments

    def do_in_background(self) -> list[tuple[str, str | None]]:
        """Build the styled-document segments for the configured filter."""
        encoding = "utf-8" if self._stream.is_xml_metadata() else "iso-8859-1"
        in_stream = self._stream.get_stream(self._filter_key)
        if in_stream is None:
            return []
        with in_stream as src:
            raw = src.read()
        if self._nice and self._filter_key == Stream.DECODED:
            if self._stream.is_xml_metadata():
                return self.get_xml_document(raw)
            content_segments = self.get_content_stream_document(raw)
            if content_segments is not None:
                return content_segments
        return self.get_document(raw, encoding)

    def done(self) -> None:
        """Hand the produced segments off to the target view.

        Mirrors upstream's ``targetView.showStreamText(get(), tTController)``.
        """
        if self._result is None:
            return
        show = getattr(self._target_view, "show_stream_text", None)
        if show is None:
            return
        try:
            show(self._result, _default_styles(), tool_tip_controller=None)
        except (TypeError, AttributeError) as exc:  # pragma: no cover
            _LOG.error("show_stream_text failed: %s", exc)

    def get(self) -> list[tuple[str, str | None]] | None:
        """Mirror ``SwingWorker.get()`` — most recent result, ``None`` if unrun."""
        return self._result

    # ------------------------------------------------------------------
    # Document builders (port of the private helpers)
    # ------------------------------------------------------------------

    def get_string_of_stream(
        self, in_stream: Any, encoding: str
    ) -> str | None:
        """Read ``in_stream`` fully and decode under ``encoding``.

        Mirrors upstream's private ``getStringOfStream(InputStream, String)``.
        """
        try:
            with in_stream as src:
                raw = src.read()
            return raw.decode(encoding, errors="replace")
        except OSError as exc:
            _LOG.error("read stream failed: %s", exc)
            return None

    def get_document(
        self, data: bytes, encoding: str
    ) -> list[tuple[str, str | None]]:
        """Build a plain-text segment list.

        Mirrors upstream's private ``getDocument(InputStream, String)``;
        CR / CRLF are normalised to LF so the raw view matches what
        Swing's ``DefaultStyledDocument.insertString`` displays.
        """
        return _plain_text_segments(data, encoding)

    def get_xml_document(self, data: bytes) -> list[tuple[str, str | None]]:
        """Pretty-print ``data`` as XML.

        Mirrors upstream's private ``getXMLDocument(InputStream)`` —
        upstream uses a ``TransformerFactory``; we use
        :mod:`xml.dom.minidom` (stdlib, no XSLT dependency).
        """
        return _xml_segments(data)

    def get_content_stream_document(
        self, data: bytes
    ) -> list[tuple[str, str | None]] | None:
        """Build the operator-tokenised "nice" view for a content stream.

        Returns ``None`` when the data is not a valid content stream (so
        the caller can fall back to ``get_document``). Mirrors upstream's
        ``getContentStreamDocument(InputStream)``.
        """
        try:
            parser = PDFStreamParser.from_bytes(data)
            tokens = parser.parse()
        except OSError:
            return None
        except Exception as exc:  # noqa: BLE001
            _LOG.error("content-stream parse failed: %s", exc)
            return None
        emitter = _ContentStreamEmitter()
        for token in tokens:
            emitter.write_token(token)
        return emitter.segments

    # ------------------------------------------------------------------
    # Per-token writers (kept as instance methods for upstream parity)
    # ------------------------------------------------------------------

    def write_token(
        self,
        obj: object,
        emitter: _ContentStreamEmitter | None = None,
    ) -> None:
        """Dispatch ``obj`` through the per-token writers.

        Mirrors upstream's private ``writeToken(Object, StyledDocument)``;
        the ``emitter`` parameter takes the role of the Swing
        ``StyledDocument`` (a private :class:`_ContentStreamEmitter` is
        created on demand when not supplied).
        """
        target = emitter or _ContentStreamEmitter()
        target.write_token(obj)

    def write_operand(
        self,
        obj: object,
        emitter: _ContentStreamEmitter | None = None,
    ) -> None:
        """Mirror upstream's ``writeOperand(Object, StyledDocument)``."""
        target = emitter or _ContentStreamEmitter()
        target._write_operand(obj)  # noqa: SLF001 - same-module helper

    def add_operators(
        self,
        op: Operator,
        emitter: _ContentStreamEmitter | None = None,
    ) -> None:
        """Mirror upstream's ``addOperators(Object, StyledDocument)``."""
        target = emitter or _ContentStreamEmitter()
        target._add_operator(op)  # noqa: SLF001

    def write_indent(
        self,
        emitter: _ContentStreamEmitter | None = None,
    ) -> None:
        """Mirror upstream's ``writeIndent(StyledDocument)`` (no-op
        when ``need_indent`` is ``False``)."""
        target = emitter or _ContentStreamEmitter()
        target._write_indent()  # noqa: SLF001


