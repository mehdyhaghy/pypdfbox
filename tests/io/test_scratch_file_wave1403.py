"""Wave 1403 branch round-out for ``ScratchFile._reset_page``.

Closes 461->455 (the ``elif idx in self._file_pages`` False arm → method
exit): ``_reset_page`` is a defensive page-zeroing helper. Through the normal
allocator a page is *always* either a live in-memory ``bytearray`` (first
arm) or recorded in ``_file_pages`` (elif arm), because file-backed
allocation registers the page in ``_file_pages`` at the same time it nulls
the in-memory slot. The "neither store" state is reachable only when a page
index has a ``None`` in-memory slot AND is absent from ``_file_pages`` — an
invariant the allocator prevents. We construct that state directly to drive
the no-op fall-through.
"""

from __future__ import annotations

from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
from pypdfbox.io.scratch_file import ScratchFile


def test_reset_page_no_op_when_page_absent_from_both_stores() -> None:
    """Closes 461->455: an index whose in-memory slot is None and which is
    not in ``_file_pages`` makes both arms False — ``_reset_page`` returns
    without touching any store."""
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as sf:
        idx = sf.get_new_page()
        # Force the "neither store" defensive state: null the in-memory slot
        # and ensure it is not registered as file-backed.
        sf._mem_pages[idx] = None  # noqa: SLF001
        sf._file_pages.pop(idx, None)  # noqa: SLF001

        # Should be a silent no-op (no IndexError, no file write).
        sf._reset_page(idx)  # noqa: SLF001

        assert sf._mem_pages[idx] is None  # noqa: SLF001
        assert idx not in sf._file_pages  # noqa: SLF001
