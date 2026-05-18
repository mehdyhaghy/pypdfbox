"""Coverage-boost tests for ``pypdfbox.debugger.ui.tree`` (wave 1349).

Pre-wave: 96.3% line coverage (191 stmts, 7 missing). Missing lines map to:

* the ``_get_file_extension`` fall-through where ``node`` is neither a
  ``MapEntry`` nor an ``ArrayEntry`` (line 179);
* the ``_make_save_raw_stream`` save callback (lines 219-220);
* the ``_read_stream`` ``bytes(data)`` fall-back when the creator
  yielded a buffer without a ``read`` attribute (line 355);
* the ``_read_stream_partial`` ``TypeError`` fall-back when the creator
  signature does not accept a ``stop_filters`` argument (lines 376-377);
* the ``_read_stream_partial`` ``bytes(data)`` fall-back (line 380).

The new tests use minimal duck-typed fakes — no Pillow / no display.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.debugger.ui import Tree
from pypdfbox.debugger.ui.tree import (
    _read_stream,
    _read_stream_partial,
)

# ---- line 179: _get_file_extension fall-through for plain-object node -----


def test_get_file_extension_uses_str_of_node_for_other_types() -> None:
    """When ``node`` is neither ``MapEntry`` nor ``ArrayEntry``, the helper
    falls back to ``str(node)``. A plain string ``"FontFile"`` is its own
    ``str()``, so the FontFile branch fires."""
    stream = COSStream()
    assert Tree._get_file_extension(stream, "FontFile") == "pfb"  # noqa: SLF001
    assert Tree._get_file_extension(stream, "FontFile2") == "ttf"  # noqa: SLF001


def test_get_file_extension_str_node_unknown_returns_none() -> None:
    stream = COSStream()
    assert Tree._get_file_extension(stream, "RandomKey") is None  # noqa: SLF001


# ---- lines 219-220: _make_save_raw_stream invocation -----------------------


def test_save_raw_stream_callback_passes_raw_bytes_to_dialog(
    tk_root: Any,
) -> None:
    """The "Save Raw Stream ..." menu callback reads the *encoded* bytes
    (not run through filters) and forwards them to the supplied dialog
    with ``extension=None``."""
    stream = COSStream()
    with stream.create_output_stream(filters=COSName.FLATE_DECODE) as out:
        out.write(b"payload")
    # Stream now has /Filter /FlateDecode and a zlib-encoded body.

    from pypdfbox.debugger.ui.map_entry import MapEntry

    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Stream"))
    entry.set_value(stream)

    captured: list[tuple[bytes, str | None]] = []

    class _FakeDialog:
        def save_file(self, data: bytes, ext: str | None) -> bool:
            captured.append((data, ext))
            return True

    tree = Tree(tk_root)
    items = tree.build_menu_items(entry, (entry,), save_dialog=_FakeDialog())
    raw_cb = next(cb for label, cb in items if label.startswith("Save Raw Stream"))
    raw_cb()

    assert len(captured) == 1
    data, ext = captured[0]
    # Raw payload is the *compressed* form — not equal to b"payload".
    assert data != b"payload"
    assert ext is None


# ---- line 355: _read_stream fall-back when data lacks .read ----------------


class _BufferLike:
    """Context manager whose ``__enter__`` returns a plain ``bytes`` value.

    ``bytes`` does not have a ``read`` attribute, so ``_read_stream`` falls
    through to the ``return bytes(data)`` branch.
    """

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> bytes:
        return self._payload

    def __exit__(self, *exc: object) -> None:
        return None


class _StreamWithRawBufferOnly:
    """A duck-typed stand-in exposing only ``create_raw_input_stream``."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def create_raw_input_stream(self) -> _BufferLike:
        return _BufferLike(self._payload)


class _StreamWithDecodedBufferOnly:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def create_input_stream(self) -> _BufferLike:
        return _BufferLike(self._payload)


def test_read_stream_returns_bytes_when_creator_yields_bytes_buffer() -> None:
    """Raw path — ``creator()`` returns a context manager whose target is a
    plain ``bytes`` value. ``hasattr(data, 'read')`` is False, so the
    helper executes the final ``bytes(data)`` branch."""
    stream = _StreamWithRawBufferOnly(b"raw-bytes-here")
    assert _read_stream(stream, raw=True) == b"raw-bytes-here"  # type: ignore[arg-type]


def test_read_stream_decoded_returns_bytes_when_creator_yields_bytes_buffer() -> None:
    stream = _StreamWithDecodedBufferOnly(b"decoded-bytes")
    assert _read_stream(stream, raw=False) == b"decoded-bytes"  # type: ignore[arg-type]


# ---- lines 376-377 + 380: _read_stream_partial fall-backs -----------------


class _StreamCreatorRejectsArgs:
    """``create_input_stream`` accepts no arguments — calling it with a
    ``stop_filters`` positional raises ``TypeError`` and forces the
    helper to retry with the zero-arg call."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def create_input_stream(self) -> bytes:
        return self._payload

    # Filter chain has at least two entries so the partial-decode path
    # tries to pass ``stop_filters``.
    def get_filters(self) -> COSArray:
        arr = COSArray()
        arr.add(COSName.get_pdf_name("ASCIIHexDecode"))
        arr.add(COSName.FLATE_DECODE)
        return arr


def test_read_stream_partial_falls_back_to_zero_arg_creator() -> None:
    """When the creator does not accept the ``stop_filters`` keyword/positional
    we fall through to the bare ``creator()`` call and still produce bytes."""
    stream = _StreamCreatorRejectsArgs(b"unfiltered-tail")
    # ``stop_index=1`` keeps the *Flate* filter — the helper attempts
    # ``creator(["FlateDecode"])`` first, hits TypeError, retries without args.
    out = _read_stream_partial(stream, 1)  # type: ignore[arg-type]
    assert out == b"unfiltered-tail"


class _StreamCreatorReturnsBytes:
    """Creator returns a plain ``bytes`` value (no ``.read`` attribute)."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def create_input_stream(self, *_args: object) -> bytes:
        return self._payload

    def get_filters(self) -> COSName:
        return COSName.FLATE_DECODE


def test_read_stream_partial_returns_bytes_when_data_lacks_read() -> None:
    """Even when the creator accepts ``stop_filters``, the returned buffer
    can still be a plain ``bytes`` value — the helper must take the
    ``return bytes(data)`` branch."""
    stream = _StreamCreatorReturnsBytes(b"partial-payload")
    out = _read_stream_partial(stream, 0)  # type: ignore[arg-type]
    assert out == b"partial-payload"


def test_read_stream_partial_single_filter_skips_stop_filters_path() -> None:
    """``stop_index`` outside the filter range leaves ``stop_filters`` empty,
    exercising the ``creator()`` zero-arg branch instead of the
    ``creator(stop_filters)`` one."""

    class _Single:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def create_input_stream(self) -> bytes:
            return self._payload

        def get_filters(self) -> COSName:
            return COSName.FLATE_DECODE

    out = _read_stream_partial(_Single(b"x"), 99)  # type: ignore[arg-type]
    assert out == b"x"


# ---- bonus: ensure the original tests still pass for non-bytes data --------


def test_read_stream_partial_handles_stream_without_get_filters() -> None:
    """``get_filters`` may be absent; the partial helper must still produce
    output (with an empty filter list) without raising."""

    class _NoFilters:
        def create_input_stream(self) -> bytes:
            return b"no-filters"

    out = _read_stream_partial(_NoFilters(), 0)  # type: ignore[arg-type]
    assert out == b"no-filters"


def test_read_stream_partial_creator_with_unwrapped_buffer_uses_read() -> None:
    """Sanity: when the buffer *does* have ``.read``, that branch fires —
    not the ``bytes(data)`` fall-through."""

    class _ReaderBuf:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

    class _Stream:
        def create_input_stream(self) -> _ReaderBuf:
            return _ReaderBuf(b"via-read")

    out = _read_stream_partial(_Stream(), 0)  # type: ignore[arg-type]
    assert out == b"via-read"


