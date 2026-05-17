"""Wave 1348 coverage-boost tests for ``pypdfbox.debugger.streampane.stream_pane``.

Targets the residual exception arms that the existing test corpus skips:

  * :meth:`StreamPane._content_stream_segments` broad-except path
    (lines 311-313) when ``PDFStreamParser.parse`` raises a non-OSError.
  * :meth:`_ContentStreamEmitter.write_token` exception arm
    (lines 391-392) when the operator-add helper raises.
  * :meth:`DocumentCreator.get_content_stream_document` broad-except path
    (lines 636-638) when the parser raises a non-OSError exception.
"""
from __future__ import annotations

from pypdfbox.cos import COSStream

# ---------- _content_stream_segments broad-except ----------


def test_content_stream_segments_swallows_non_oserror(
    tk_root, monkeypatch
) -> None:
    """A non-OSError raised by the parser is caught and reported as
    ``None`` (lines 311-313)."""
    from pypdfbox.debugger.streampane import stream_pane as sp_mod
    from pypdfbox.debugger.streampane.stream_pane import StreamPane

    cos = COSStream()
    cos.set_data(b"BT ET")
    pane = StreamPane(tk_root, cos, is_content_stream=True, is_thumb=False)

    def _explode(_data):
        raise RuntimeError("parser broke")

    # Patch the from_bytes constructor so .parse() never runs (the
    # exception fires earlier, but still on the broad-except arm).
    monkeypatch.setattr(sp_mod.PDFStreamParser, "from_bytes", _explode)
    assert pane._content_stream_segments(b"junk") is None  # noqa: SLF001


# ---------- _ContentStreamEmitter.write_token broad-except ----------


def test_emitter_write_token_swallows_attribute_error() -> None:
    """If ``_write_operand`` raises ``AttributeError`` (e.g. unknown
    operand shape), the emitter swallows it (lines 391-392)."""
    from pypdfbox.debugger.streampane.stream_pane import _ContentStreamEmitter

    emitter = _ContentStreamEmitter()

    class _UnknownOperand:
        """Not a recognised COS leaf — write_operand falls through to the
        ``else`` arm whose ``str(obj)`` call works fine, but we force the
        broad-catch by deleting the attribute it needs."""

    # Forcing the catch path: monkey-patch the operand writer to raise.
    def _boom(_obj):
        raise AttributeError("nope")

    emitter._write_operand = _boom  # type: ignore[assignment]
    # Must not raise — exception caught + logged inside the emitter.
    emitter.write_token(_UnknownOperand())


# ---------- DocumentCreator.get_content_stream_document broad-except ----


def test_document_creator_get_content_stream_document_swallows_non_oserror(
    monkeypatch,
) -> None:
    """Non-OSError raised by the parser is caught and ``None`` is
    returned (lines 636-638)."""
    from pypdfbox.debugger.streampane import stream_pane as sp_mod
    from pypdfbox.debugger.streampane.stream import Stream
    from pypdfbox.debugger.streampane.stream_pane import DocumentCreator

    class _CapturingView:
        def show_stream_text(self, *_args, **_kwargs) -> None:
            pass

    cos = COSStream()
    stream = Stream(cos, is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=True)

    def _explode(_data):
        raise RuntimeError("parser misbehaved")

    monkeypatch.setattr(sp_mod.PDFStreamParser, "from_bytes", _explode)
    assert creator.get_content_stream_document(b"anything") is None
