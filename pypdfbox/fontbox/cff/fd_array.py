from __future__ import annotations

from typing import Any


class FDArray:
    """CFF /FDArray — the per-FD Font DICT INDEX of a CIDKeyed font.

    Each entry is itself a Font DICT carrying its own /Private DICT
    (default/nominal width X, Subrs, ...). PDFBox exposes this as
    ``Map<String, Object>``-shaped accessors; we wrap the fontTools
    ``FDArrayIndex`` and surface the same API in snake_case.

    There is no separate ``FDArray`` class in upstream PDFBox — the
    array is just ``List<Map<String, Object>>`` returned from the parser.
    We give it a thin object wrapper here so the CIDFont accessors
    (``get_font_dict(i)`` / ``get_private_dict(i)``) have a clean home.
    """

    def __init__(self, fdarray: Any | None = None) -> None:
        # ``fdarray`` is a ``fontTools.cffLib.FDArrayIndex`` (sequence of
        # ``FontDict`` objects) or ``None`` for an empty placeholder.
        self._fdarray = fdarray

    @classmethod
    def from_fonttools(cls, fdarray: Any) -> "FDArray":
        return cls(fdarray)

    # ---------- length ----------

    def size(self) -> int:
        """PDFBox-style length accessor."""
        if self._fdarray is None:
            return 0
        try:
            return len(self._fdarray)
        except TypeError:
            return 0

    def __len__(self) -> int:
        return self.size()

    def is_empty(self) -> bool:
        return self.size() == 0

    # ---------- per-entry access ----------

    def get_font_dict(self, fd_index: int) -> dict[str, Any]:
        """The Font DICT entries for ``fd_index`` as a plain ``dict``
        snapshot (backed by fontTools' ``FontDict.rawDict``)."""
        font = self._raw_font_dict(fd_index)
        if font is None:
            return {}
        return dict(getattr(font, "rawDict", {}))

    def get_private_dict(self, fd_index: int) -> dict[str, Any]:
        """The Private DICT entries for ``fd_index``. Empty dict when the
        FontDict has no Private DICT (malformed CFF) or when the index
        is out of range."""
        font = self._raw_font_dict(fd_index)
        if font is None:
            return {}
        priv = getattr(font, "Private", None)
        if priv is None:
            return {}
        return dict(getattr(priv, "rawDict", {}))

    def get_default_width_x(self, fd_index: int) -> float:
        font = self._raw_font_dict(fd_index)
        if font is None:
            return 0.0
        priv = getattr(font, "Private", None)
        if priv is None:
            return 0.0
        return float(getattr(priv, "defaultWidthX", 0))

    def get_nominal_width_x(self, fd_index: int) -> float:
        font = self._raw_font_dict(fd_index)
        if font is None:
            return 0.0
        priv = getattr(font, "Private", None)
        if priv is None:
            return 0.0
        return float(getattr(priv, "nominalWidthX", 0))

    def get_local_subrs(self, fd_index: int) -> int:
        """Count of /Subrs in this FD's Private DICT, or 0."""
        font = self._raw_font_dict(fd_index)
        if font is None:
            return 0
        priv = getattr(font, "Private", None)
        if priv is None:
            return 0
        subrs = getattr(priv, "Subrs", None)
        return len(subrs) if subrs is not None else 0

    # ---------- raw underlying access (advanced callers) ----------

    def get_raw_font_dict(self, fd_index: int) -> Any | None:
        """Return the underlying fontTools ``FontDict`` (or ``None``)."""
        return self._raw_font_dict(fd_index)

    def _raw_font_dict(self, fd_index: int) -> Any | None:
        if self._fdarray is None or fd_index < 0:
            return None
        try:
            return self._fdarray[fd_index]
        except (IndexError, KeyError, TypeError):
            return None

    def __getitem__(self, fd_index: int) -> dict[str, Any]:
        return self.get_font_dict(fd_index)

    def __iter__(self):
        for i in range(self.size()):
            yield self.get_font_dict(i)

    def __repr__(self) -> str:
        return f"FDArray(size={self.size()})"

    # ---------- bulk views ----------

    def font_dicts(self) -> list[dict[str, Any]]:
        """All Font DICTs as a flat list. Convenience wrapper around
        iteration; mirrors ``CFFCIDFont.getFontDicts()``."""
        return list(iter(self))

    def private_dicts(self) -> list[dict[str, Any]]:
        """All Private DICTs as a flat list. Mirrors
        ``CFFCIDFont.getPrivDicts()``."""
        return [self.get_private_dict(i) for i in range(self.size())]


__all__ = ["FDArray"]
