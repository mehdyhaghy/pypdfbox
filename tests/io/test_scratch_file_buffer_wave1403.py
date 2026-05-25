"""Wave 1403 branch round-out for ``ScratchFileBuffer.clear``.

Closes 262->265 — the ``if self._page_indices`` False arm: ``clear`` frees
the buffer's owned pages only when it holds any. Through the normal lifecycle
a buffer always owns at least one page (the constructor eagerly allocates the
first), so ``clear`` never sees an empty page list. We drain ``_page_indices``
directly to drive the empty-list fall-through (defensive parity with
upstream's ``if (pageIndexes != null && !pageIndexes.isEmpty())`` guard).
"""

from __future__ import annotations

from pypdfbox.io.scratch_file import ScratchFile


def test_clear_with_no_owned_pages_skips_free() -> None:
    """Closes 262->265: an empty ``_page_indices`` makes the free-pages arm
    False; ``clear`` still resets position/length and re-allocates a page."""
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        # Drain the owned-page list to force the empty-list path.
        buf._page_indices.clear()  # noqa: SLF001

        buf.clear()

        assert buf._position == 0  # noqa: SLF001
        assert buf._length == 0  # noqa: SLF001
        # clear() re-allocates the first page (upstream parity).
        assert len(buf._page_indices) == 1  # noqa: SLF001
