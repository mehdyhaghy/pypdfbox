from __future__ import annotations

from collections.abc import Iterator

from pypdfbox.cos import COSArray

from .pd_path_info import PDPathInfo


class PDInkList:
    """Typed wrapper around the ``/InkList`` array of arrays — each inner
    ``COSArray`` is one stroked path (PDF 32000-1:2008 §12.5.6.13).
    """

    def __init__(self, array: COSArray | None = None) -> None:
        self._array: COSArray = array if array is not None else COSArray()

    def get_cos_array(self) -> COSArray:
        return self._array

    def get_cos_object(self) -> COSArray:
        """Alias for :meth:`get_cos_array` matching the COSObjectable
        convention used by sibling annotation helpers."""
        return self._array

    def get_paths(self) -> list[PDPathInfo]:
        out: list[PDPathInfo] = []
        for i in range(self._array.size()):
            entry = self._array.get_object(i)
            if isinstance(entry, COSArray):
                out.append(PDPathInfo(entry))
        return out

    def get_path(self, index: int) -> PDPathInfo:
        """Return the :class:`PDPathInfo` wrapping the inner ``COSArray`` at
        ``index``. Raises :class:`IndexError` if ``index`` is out of range
        or :class:`TypeError` if the entry is not a ``COSArray``."""
        if index < 0 or index >= self._array.size():
            raise IndexError(
                f"PDInkList index {index} out of range "
                f"(path_count={self._array.size()})"
            )
        entry = self._array.get_object(index)
        if not isinstance(entry, COSArray):
            raise TypeError(
                f"PDInkList entry at {index} is {type(entry).__name__}, "
                "expected COSArray"
            )
        return PDPathInfo(entry)

    def add_path(self, path: PDPathInfo) -> None:
        self._array.add(path.get_cos_array())

    def remove_path(self, index: int) -> None:
        self._array.remove_at(index)

    def clear(self) -> None:
        """Remove every stroked path from the wrapped ``/InkList`` array.

        The underlying ``COSArray`` is mutated in place so external
        references stay valid."""
        self._array.clear()

    def path_count(self) -> int:
        return self._array.size()

    def is_empty(self) -> bool:
        """True when the ``/InkList`` array contains no stroked paths."""
        return self._array.size() == 0

    # ---------- python protocols ----------

    def __len__(self) -> int:
        return self._array.size()

    def __iter__(self) -> Iterator[PDPathInfo]:
        return iter(self.get_paths())


__all__ = ["PDInkList"]
