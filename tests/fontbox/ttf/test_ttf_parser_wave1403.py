"""Wave 1403 — branch round-out for :class:`TTFParser`.

Closes the partial arc ``[507,514]`` — the ``len(raw) >= 4`` False
branch in :meth:`create_font_with_tables`: when the original SFNT byte
buffer is shorter than four bytes, the scaler/version decode is skipped
and control falls straight through to the reader-projection step.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.ttf import TTFParser


class _ShortStream:
    """TTFDataStream-shaped stub whose original data is < 4 bytes."""

    def get_original_data(self) -> bytes:
        return b"\x00\x01"


class _StubFont:
    """Minimal font with no fontTools reader handle."""

    _tt = None

    def __init__(self) -> None:
        self.version: float | None = None

    def set_version(self, value: float) -> None:  # pragma: no cover - guard
        # Should never be called: the < 4-byte buffer skips version decode.
        self.version = value


def test_create_font_with_tables_short_buffer_skips_version() -> None:
    """A < 4-byte original buffer takes the ``len(raw) >= 4`` False arc
    ([507,514]); ``set_version`` is never invoked and the font is
    returned once the (absent) reader short-circuits the entry walk."""
    set_calls: list[float] = []

    class _StubFontTracked(_StubFont):
        def set_version(self, value: float) -> None:
            set_calls.append(value)

    class _Parser(TTFParser):
        def new_font(self, data: Any) -> Any:  # noqa: ARG002
            return _StubFontTracked()

    parser = _Parser()
    font = parser.create_font_with_tables(_ShortStream())  # type: ignore[arg-type]
    assert font is not None
    # Version decode was skipped because the buffer is too short.
    assert set_calls == []
