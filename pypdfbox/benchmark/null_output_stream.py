"""Output stream that drops everything.

Ported from
``benchmark/src/main/java/org/apache/pdfbox/benchmark/NullOutputStream.java``
(lines 22-38). Identical to ``java.io.OutputStream`` with no-op
``write`` overloads; the Python port exposes the same file-like surface
(``write``, ``flush``, ``close``) so it can be passed to
:meth:`PDDocument.save` in place of a real file handle.
"""

from __future__ import annotations

from io import RawIOBase


class NullOutputStream(RawIOBase):
    """A write-only stream that swallows all input."""

    def writable(self) -> bool:  # pragma: no cover - trivial
        return True

    def write(self, b: bytes | bytearray | memoryview) -> int:  # type: ignore[override]
        # Mirrors the three overrides at lines 25 / 30 / 35 of upstream.
        if b is None:
            return 0
        return len(memoryview(b))

    def flush(self) -> None:  # pragma: no cover - trivial
        return None
