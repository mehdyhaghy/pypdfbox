from __future__ import annotations

from typing import TYPE_CHECKING

from .random_access_read_memory_mapped import RandomAccessReadMemoryMapped

if TYPE_CHECKING:
    import os


class RandomAccessReadMemoryMappedFile(RandomAccessReadMemoryMapped):
    """Random-access reader backed by a memory-mapped file.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessReadMemoryMappedFile`` exactly —
    the existing pypdfbox class lives under the shortened name
    ``RandomAccessReadMemoryMapped``; this alias keeps the upstream
    fully-qualified name available so 1:1 ports compile.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        super().__init__(path)

    def check_closed(self) -> None:
        """Raise ``OSError`` if this reader has been closed.

        Mirrors upstream ``RandomAccessReadMemoryMappedFile.checkClosed``
        (Java line 195, private). Implemented as a thin wrapper around
        the existing ``_check_open`` guard so it raises the same
        exception class as the parent's other public methods.
        """
        if self.is_closed():
            raise OSError(f"{type(self).__name__} already closed")
