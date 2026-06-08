"""Wave 1345: residual coverage for ``PredictorOutputStream``.

Targets:
  - the negative-row-length guard (line 47 — ``OSError`` on bad params);
  - the ``writable()`` accessor (line 61);
  - the flush-flush-pad branch (line 131-134) when the final row is
    short and must be zero-padded before decode.
"""

from __future__ import annotations

import io

from pypdfbox.filter import PredictorOutputStream


def test_constructor_uses_java_truncation_for_negative_columns() -> None:
    """Java integer division truncates ``(-8 + 7) / 8`` to zero."""
    sink = io.BytesIO()
    stream = PredictorOutputStream(
        sink, predictor=2, colors=1, bits_per_component=8, columns=-1
    )
    try:
        assert stream._row_length == 0  # noqa: SLF001
    finally:
        stream.close()


def test_writable_returns_true() -> None:
    """``writable()`` always returns ``True`` (the stream is write-only)."""
    sink = io.BytesIO()
    pos = PredictorOutputStream(sink, predictor=2, colors=1, bits_per_component=8, columns=3)
    try:
        assert pos.writable() is True
    finally:
        pos.close()


def test_flush_pads_incomplete_final_row_with_zeros() -> None:
    """When the input ends mid-row, ``flush()`` zero-pads to row length
    and emits the partial row (mirrors upstream's eager-flush semantics).

    Row length = 3 bytes (columns=3, colors=1, 8 bpc).  We write 2 bytes
    of a TIFF-2 predicted row (5, 3) — the third byte is supplied by
    flush as 0.  TIFF-2 (Sub) decodes 5, 3, 0 to 5, 8, 8.
    """
    sink = io.BytesIO()
    pos = PredictorOutputStream(sink, predictor=2, colors=1, bits_per_component=8, columns=3)
    pos.write(b"\x05\x03")  # 2 of 3 bytes
    pos.flush()
    assert sink.getvalue() == b"\x05\x08\x08"
    pos.close()


def test_close_is_idempotent_and_propagates_flush_pad() -> None:
    """``close()`` invokes ``flush`` (which zero-pads the last row).

    We must read the sink value BEFORE close — close ultimately calls
    ``sink.close()`` on a BytesIO, which makes the buffer unreadable.
    """
    sink = io.BytesIO()
    pos = PredictorOutputStream(sink, predictor=2, colors=1, bits_per_component=8, columns=3)
    pos.write(b"\x07\x01")  # 2 bytes; missing trailing byte padded to 0
    pos.flush()
    # TIFF-2 sub: 7, 1, 0 -> 7, 8, 8
    assert sink.getvalue() == b"\x07\x08\x08"
    pos.close()
    # A second close must not raise.
    pos.close()


def test_close_swallows_sink_close_errors() -> None:
    """If the underlying sink raises on close, the predictor swallows it."""
    raised: list[bool] = []

    class _SinkExplodingOnClose(io.BytesIO):
        def close(self) -> None:
            raised.append(True)
            raise RuntimeError("boom")

    sink = _SinkExplodingOnClose()
    pos = PredictorOutputStream(sink, predictor=2, colors=1, bits_per_component=8, columns=3)
    # No data written; close should still succeed despite sink raising.
    pos.close()
    # The predictor must have attempted to close the sink.
    assert raised == [True]
