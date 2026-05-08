from __future__ import annotations

from collections.abc import Iterator
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
    def from_fonttools(cls, fdarray: Any) -> FDArray:
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

    def get_local_subr_index(self, fd_index: int) -> list[bytes]:
        """Per-FD local subroutine bytecodes as a list of ``bytes``.

        Mirrors upstream ``CFFCIDFont.getLocalSubrIndex(int gid)`` — but
        keyed by FD index rather than GID, so callers reuse the same
        byte arrays across all GIDs that share an FD. Empty list when
        the FD has no Private DICT or no /Subrs INDEX.

        Parallel to :py:meth:`CFFFont.get_global_subr_index`; T2
        charstring decoders need both the global and FD-local subr
        bytecodes to resolve ``callsubr`` / ``callgsubr`` operators.
        """
        font = self._raw_font_dict(fd_index)
        if font is None:
            return []
        priv = getattr(font, "Private", None)
        if priv is None:
            return []
        subrs = getattr(priv, "Subrs", None)
        if subrs is None:
            return []
        out: list[bytes] = []
        for entry in subrs:
            bc = getattr(entry, "bytecode", None)
            if bc is not None:
                out.append(bytes(bc))
            elif isinstance(entry, (bytes, bytearray)):
                out.append(bytes(entry))
            else:
                out.append(b"")
        return out

    def has_private_dict(self, fd_index: int) -> bool:
        """Predicate: whether the FD at ``fd_index`` carries a Private
        DICT. Returns ``False`` for out-of-range indices.

        Mirrors the conventional CFF-shape check upstream callers do
        before reading ``defaultWidthX`` / ``nominalWidthX`` /
        ``Subrs``."""
        font = self._raw_font_dict(fd_index)
        if font is None:
            return False
        return getattr(font, "Private", None) is not None

    def has_local_subrs(self, fd_index: int) -> bool:
        """Predicate: whether the FD's Private DICT carries a non-empty
        /Subrs INDEX. Returns ``False`` for out-of-range indices, FDs
        without a Private DICT, or FDs whose /Subrs is empty."""
        return self.get_local_subrs(fd_index) > 0

    def index_for_font_name(self, name: str) -> int:
        """Return the first FD index whose Font DICT carries the given
        ``FontName``, or ``-1`` when no FD matches.

        Useful for callers that want to look up a sub-font by its
        PostScript name (e.g. inspecting per-FD widths / subrs in a
        diagnostic tool). Empty / ``None`` ``name`` returns ``-1``.
        """
        if not name:
            return -1
        for i in range(self.size()):
            if self.get_font_name(i) == name:
                return i
        return -1

    def get_font_name(self, fd_index: int) -> str:
        """Return the ``FontName`` (PostScript name) of the Font DICT at
        ``fd_index``, or ``""`` when missing / out of range.

        Mirrors the per-FD ``FontName`` Top DICT operator (CFF spec §9,
        Table 9). PDFBox callers typically read this via
        ``getFontDict(i).get("FontName")``; this helper gives a typed
        accessor that also tolerates the fontTools attribute form.
        """
        font = self._raw_font_dict(fd_index)
        if font is None:
            return ""
        # fontTools surfaces ``FontName`` either as an attribute or via
        # the ``rawDict`` mapping; check both.
        name = getattr(font, "FontName", None)
        if name is None:
            raw = getattr(font, "rawDict", None)
            if isinstance(raw, dict):
                name = raw.get("FontName")
        return str(name) if name is not None else ""

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

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for i in range(self.size()):
            yield self.get_font_dict(i)

    def __contains__(self, fd_index: object) -> bool:
        """Whether ``fd_index`` is a valid FDArray slot.

        Mirrors the Pythonic membership test; upstream PDFBox callers
        typically range-check manually (``0 <= i < size()``)."""
        if not isinstance(fd_index, int) or isinstance(fd_index, bool):
            return False
        return 0 <= fd_index < self.size()

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
