"""Wave 1497 — base-engine colour-operator gating
(``shouldProcessColorOperators``).

Upstream ``PDFStreamEngine.processStreamOperators`` (3.0.7 lines 538-578)
forces ``shouldProcessColorOperators = true`` for the duration of a stream's
operator loop, then flips it ``false`` for:

* an *uncoloured* tiling pattern (``PDTilingPattern`` with
  ``/PaintType 2``) — colour is supplied by the caller via the ``/Pattern``
  colour space, not the pattern's own content stream; and
* a Type 3 charproc whose *first* operator is ``d1`` — the glyph is an
  uncoloured mask and inherits the surrounding text-state colour.

The previous flag value is always restored in a ``finally``.

Before wave 1497 the 14 colour-operator classes read
``is_should_process_color_operators()`` but the base engine never wired the
setter into its dispatch loop — so ANY non-renderer subclass (the renderer
has its own parallel ``_type3_ignore_color`` gate) processed the suppressed
colour ops. These pins drive a minimal text-extraction-style engine subclass
(NOT the renderer) over crafted streams and assert the colour op after ``d1``
is suppressed, while a ``d0`` charproc / a coloured tiling pattern / a normal
page stream let it through, and the flag is restored afterwards.
"""

from __future__ import annotations

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator.color.set_non_stroking_rgb import (
    SetNonStrokingRGB,
)
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel.graphics.color import PDColor
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern


class _RecordingEngine(PDFStreamEngine):
    """A non-renderer engine (text-extraction shaped): it records every
    ``set_non_stroking_color`` hook the colour operators forward, and the
    value of the gating flag as each colour op fires."""

    def __init__(self) -> None:
        super().__init__()
        self.colors: list[PDColor] = []
        self.flag_at_color: list[bool] = []
        self.add_operator(SetNonStrokingRGB())

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.colors.append(color)
        self.flag_at_color.append(self.is_should_process_color_operators())


class _ContentStream:
    """Minimal duck-typed content stream over raw bytes — stands in for a
    page / form stream that carries no colour-suppression. Only the two
    methods the engine's dispatch path actually calls are implemented
    (``get_contents_for_stream_parsing`` + ``get_resources``)."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def get_contents_for_stream_parsing(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._body)

    def get_resources(self) -> None:
        return None


class PDType3CharProc(_ContentStream):
    """Type-name-only stand-in: the base engine identifies a Type 3 charproc
    by ``type(...).__name__ == "PDType3CharProc"`` so the leading-``d1``
    suppression can fire without importing the heavyweight font class (which
    does not implement ``get_contents_for_stream_parsing``)."""


class _TilingPattern(_ContentStream):
    """Duck-typed tiling pattern carrying the same ``is_uncolored`` /
    ``get_paint_type`` / ``get_pattern_type`` surface the base engine's
    ``_is_uncolored_tiling_pattern`` guard inspects. Avoids the real
    :class:`PDTilingPattern`'s ``BinaryIO`` (non-``RandomAccessRead``)
    stream-parsing return, which is an unrelated I/O quirk."""

    def __init__(self, body: bytes, paint_type: int) -> None:
        super().__init__(body)
        self._paint_type = paint_type

    def get_paint_type(self) -> int:
        return self._paint_type

    def get_pattern_type(self) -> int:
        return PDTilingPattern.TYPE_TILING_PATTERN

    def is_uncolored(self) -> bool:
        return self._paint_type == PDTilingPattern.PAINT_UNCOLORED


_RGB = b"0.1 0.2 0.3 rg\n0 0 10 10 re f\n"


def _make_tiling_pattern(paint_type: int, body: bytes) -> _TilingPattern:
    return _TilingPattern(body, paint_type)


def test_d1_charproc_suppresses_following_color_op() -> None:
    engine = _RecordingEngine()
    charproc = PDType3CharProc(b"640 0 10 -20 480 700 d1\n" + _RGB)
    engine.process_stream_operators(charproc)
    # The ``rg`` after a leading ``d1`` must be swallowed — no colour set.
    assert engine.colors == []


def test_d0_charproc_lets_color_op_through() -> None:
    engine = _RecordingEngine()
    charproc = PDType3CharProc(b"720 0 d0\n" + _RGB)
    engine.process_stream_operators(charproc)
    # ``d0`` glyphs keep their own colour ops.
    assert len(engine.colors) == 1
    assert engine.flag_at_color == [True]


def test_uncolored_tiling_pattern_suppresses_color_op() -> None:
    engine = _RecordingEngine()
    pattern = _make_tiling_pattern(PDTilingPattern.PAINT_UNCOLORED, _RGB)
    engine.process_stream_operators(pattern)
    assert engine.colors == []


def test_colored_tiling_pattern_lets_color_op_through() -> None:
    engine = _RecordingEngine()
    pattern = _make_tiling_pattern(PDTilingPattern.PAINT_COLORED, _RGB)
    engine.process_stream_operators(pattern)
    assert len(engine.colors) == 1
    assert engine.flag_at_color == [True]


def test_plain_content_stream_lets_color_op_through() -> None:
    engine = _RecordingEngine()
    engine.process_stream_operators(_ContentStream(_RGB))
    assert len(engine.colors) == 1


def test_flag_restored_after_d1_charproc() -> None:
    engine = _RecordingEngine()
    assert engine.is_should_process_color_operators() is True
    engine.process_stream_operators(
        PDType3CharProc(b"640 0 10 -20 480 700 d1\n" + _RGB)
    )
    # Restored to its pre-stream value in the ``finally`` (upstream 575-577).
    assert engine.is_should_process_color_operators() is True


def test_raw_bytes_path_leaves_flag_untouched() -> None:
    # The renderer's Type3 path feeds raw bytes (no content-stream object)
    # through ``_process_bytes`` -> ``_dispatch_tokens(parser)`` and carries
    # its own ``_type3_ignore_color`` gate; the base flag must NOT be touched
    # so the two mechanisms never double-apply.
    engine = _RecordingEngine()
    engine._set_should_process_color_operators(False)
    engine._process_bytes(_RGB)
    # Flag still False (left untouched), so the colour op stayed suppressed.
    assert engine.colors == []
    assert engine.is_should_process_color_operators() is False
