from __future__ import annotations

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

    def get_paths(self) -> list[PDPathInfo]:
        out: list[PDPathInfo] = []
        for i in range(self._array.size()):
            entry = self._array.get_object(i)
            if isinstance(entry, COSArray):
                out.append(PDPathInfo(entry))
        return out

    def add_path(self, path: PDPathInfo) -> None:
        self._array.add(path.get_cos_array())

    def remove_path(self, index: int) -> None:
        self._array.remove_at(index)

    def path_count(self) -> int:
        return self._array.size()


__all__ = ["PDInkList"]
