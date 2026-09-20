"""PDFBOX-6266 — ``show_type3_glyph`` must not recurse without bound.

A Type3 ``/CharProc`` is an ordinary content stream, so nothing stops it
from painting the very glyph it defines (directly, or through a cycle of
charprocs). Upstream 3.0.9 bumps the recursion level for the duration of
the charproc walk and bails out above depth 50, logging
``"recursion is too deep, skipping Type3 glyph"``.

The bump lives in ``show_type3_glyph`` **only** — ``process_stream``
deliberately leaves ``_level`` alone (wave 1472) so form-XObject ``Do``
recursion and Type3 recursion each count their own depth, exactly like
upstream.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine

_ENGINE_LOGGER = "pypdfbox.contentstream.pdf_stream_engine"


class _SelfReferencingFont:
    """Type3 font whose every code maps to the same charproc."""

    CHAR_PROC = object()

    def get_char_proc(self, code: int) -> object:
        del code
        return self.CHAR_PROC


class _RecursingEngine(PDFStreamEngine):
    """Engine whose Type3 charproc walk shows the same glyph again.

    Standing in for a charproc content stream whose ``d0``/``Tj`` pair
    paints the glyph it is defining — the shape PDFBOX-6266 reports.
    """

    def __init__(self) -> None:
        super().__init__()
        self.depths: list[int] = []
        self.font = _SelfReferencingFont()

    def process_type3_stream(
        self, charproc: Any, text_matrix: Any | None = None
    ) -> None:
        self.depths.append(self.get_level())
        self.show_type3_glyph(text_matrix, self.font, 65, None)


class _CountingEngine(PDFStreamEngine):
    """Non-recursing engine that records the level it was entered at."""

    def __init__(self) -> None:
        super().__init__()
        self.levels: list[int] = []

    def process_type3_stream(
        self, charproc: Any, text_matrix: Any | None = None
    ) -> None:
        del charproc, text_matrix
        self.levels.append(self.get_level())


def test_self_referencing_type3_glyph_stops_at_depth_50() -> None:
    engine = _RecursingEngine()
    engine.show_type3_glyph(None, engine.font, 65, None)

    # Levels 1..50 run the charproc; level 51 trips the cap and returns
    # before ``get_char_proc`` is consulted.
    assert engine.depths == list(range(1, 51))


def test_recursion_cap_logs_an_error(caplog: pytest.LogCaptureFixture) -> None:
    engine = _RecursingEngine()
    with caplog.at_level(logging.ERROR, logger=_ENGINE_LOGGER):
        engine.show_type3_glyph(None, engine.font, 65, None)
    assert "recursion is too deep, skipping Type3 glyph" in caplog.text


def test_level_is_restored_after_recursion_unwinds() -> None:
    engine = _RecursingEngine()
    engine.show_type3_glyph(None, engine.font, 65, None)
    assert engine.get_level() == 0


def test_non_recursive_glyph_is_processed_at_level_one() -> None:
    engine = _CountingEngine()
    engine.show_type3_glyph(None, _SelfReferencingFont(), 65, None)
    assert engine.levels == [1]
    assert engine.get_level() == 0


def test_level_restored_when_charproc_walk_raises() -> None:
    """The bump is in a ``try``/``finally`` — an exception escaping the
    charproc must not leave ``_level`` stuck above zero."""

    class _ExplodingEngine(PDFStreamEngine):
        def process_type3_stream(
            self, charproc: Any, text_matrix: Any | None = None
        ) -> None:
            del charproc, text_matrix
            raise RuntimeError("charproc blew up")

    engine = _ExplodingEngine()
    with pytest.raises(RuntimeError):
        engine.show_type3_glyph(None, _SelfReferencingFont(), 65, None)
    assert engine.get_level() == 0


def test_missing_font_still_balances_the_level() -> None:
    engine = _CountingEngine()
    engine.show_type3_glyph(None, None, 65, None)
    engine.show_type3_glyph(None, object(), 65, None)  # no get_char_proc
    assert engine.levels == []
    assert engine.get_level() == 0


def test_process_stream_does_not_bump_the_type3_level() -> None:
    """Wave 1472 removed the level bump from ``process_stream``; the
    PDFBOX-6266 guard must not reintroduce it there — otherwise nested
    charprocs would double-count and halve the effective cap."""

    class _LevelProbe(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[int] = []

        def process_type3_stream(
            self, charproc: Any, text_matrix: Any | None = None
        ) -> None:
            del text_matrix
            self.seen.append(self.get_level())
            self.process_stream(charproc)
            self.seen.append(self.get_level())

    class _EmptyContentStream:
        def get_resources(self) -> None:
            return None

        def get_contents_for_stream_parsing(self) -> Any:
            from pypdfbox.io import RandomAccessReadBuffer

            return RandomAccessReadBuffer(b"")

    class _Font:
        def get_char_proc(self, code: int) -> Any:
            del code
            return _EmptyContentStream()

    engine = _LevelProbe()
    engine.show_type3_glyph(None, _Font(), 65, None)
    assert engine.seen == [1, 1]
    assert engine.get_level() == 0
