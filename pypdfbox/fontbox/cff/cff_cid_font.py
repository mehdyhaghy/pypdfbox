from __future__ import annotations

from typing import Any

from .cff_font import CFFFont
from .fd_array import FDArray
from .fd_select import FDSelect


class CFFCIDFont(CFFFont):
    """CIDKeyed (Type 0) Compact Font Format font.

    Mirrors upstream ``org.apache.fontbox.cff.CFFCIDFont`` (which extends
    ``CFFFont``). A CIDKeyed CFF carries a ROS (Registry / Ordering /
    Supplement) tuple, a /CIDCount, a per-glyph /FDSelect mapping each
    GID to a Font DICT index, and an /FDArray of Font DICTs (each with
    its own /Private DICT).

    Parsing stays in :class:`CFFFont` (delegated to fontTools); this
    subclass only adds CID-specific accessors. Construct via
    :meth:`from_bytes` or :meth:`from_cff_font`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._fd_select: FDSelect | None = None
        self._fd_array: FDArray | None = None

    # ---------- factories ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "CFFCIDFont":
        """Parse a CFF byte stream as a CIDKeyed font.

        Raises ``OSError`` when the parsed font is name-keyed (i.e. has
        no /ROS Top DICT entry) — callers wanting permissive parsing
        should use :meth:`CFFFont.from_bytes` and check
        :py:meth:`CFFFont.is_cid_font` first.
        """
        base = CFFFont.from_bytes(data)
        if not base.is_cid_font():
            msg = "CFF font is not CIDKeyed (no /ROS in Top DICT)"
            raise OSError(msg)
        return cls.from_cff_font(base)

    @classmethod
    def from_cff_font(cls, base: CFFFont) -> "CFFCIDFont":
        """Re-wrap an already-parsed :class:`CFFFont` as a
        :class:`CFFCIDFont`. Cheap — shares the underlying fontTools
        font set, no re-decompilation."""
        instance = cls()
        instance._fontset = base._fontset  # noqa: SLF001
        instance._top = base._top  # noqa: SLF001
        return instance

    # ---------- CID-specific accessors ----------

    def get_registry(self) -> str:
        """Registry component of /ROS (e.g. ``"Adobe"``)."""
        ros = self._ros()
        return ros[0] if ros else ""

    def get_ordering(self) -> str:
        """Ordering component of /ROS (e.g. ``"Japan1"``, ``"GB1"``)."""
        ros = self._ros()
        return ros[1] if ros else ""

    def get_supplement(self) -> int:
        """Supplement component of /ROS (e.g. ``6``)."""
        ros = self._ros()
        return int(ros[2]) if ros else 0

    def get_ros(self) -> tuple[str, str, int]:
        """Convenience: full Registry/Ordering/Supplement triple."""
        ros = self._ros()
        if not ros:
            return ("", "", 0)
        return (str(ros[0]), str(ros[1]), int(ros[2]))

    def _ros(self) -> Any:
        if self._top is None:
            return None
        return getattr(self._top, "ROS", None) or self._top.rawDict.get("ROS")

    def get_cid_count(self) -> int:
        """CFF Top DICT /CIDCount (default 8720 per CFF spec §10)."""
        if self._top is None:
            return 0
        return int(getattr(self._top, "CIDCount", 8720))

    def get_fd_select(self) -> FDSelect:
        """The /FDSelect mapping GID → Font DICT index."""
        if self._fd_select is None:
            raw = (
                getattr(self._top, "FDSelect", None) if self._top is not None else None
            )
            self._fd_select = FDSelect.from_fonttools(raw)
        return self._fd_select

    def get_fd_array(self) -> FDArray:
        """The /FDArray of per-FD Font DICTs."""
        if self._fd_array is None:
            raw = (
                getattr(self._top, "FDArray", None) if self._top is not None else None
            )
            self._fd_array = FDArray.from_fonttools(raw)
        return self._fd_array

    # ---------- CID → glyph helpers ----------

    def get_fd_index_for_gid(self, gid: int) -> int:
        """Per-GID Font DICT index. Equivalent to
        ``get_fd_select().get_fd_index(gid)``."""
        return self.get_fd_select().get_fd_index(gid)

    def get_private_dict_for_gid(self, gid: int) -> dict[str, Any]:
        """Private DICT (as a plain ``dict`` snapshot) governing ``gid``.

        For CIDKeyed CFF the Top-DICT /Private is *unused*; the real
        Private DICTs live in /FDArray and are selected per-glyph via
        /FDSelect. This helper does that lookup so callers can interpret
        a glyph's charstring correctly.
        """
        return self.get_fd_array().get_private_dict(self.get_fd_index_for_gid(gid))

    def get_default_width_x_for_gid(self, gid: int) -> float:
        return self.get_fd_array().get_default_width_x(self.get_fd_index_for_gid(gid))

    def get_nominal_width_x_for_gid(self, gid: int) -> float:
        return self.get_fd_array().get_nominal_width_x(self.get_fd_index_for_gid(gid))

    # PDFBox-named per-FD width overrides (upstream override)

    def get_default_width_x(self, gid: int = -1) -> float:  # noqa: D401
        """Per-GID defaultWidthX override. Upstream
        ``CFFCIDFont.getDefaultWidthX(int gid)`` reads the right
        Private DICT through /FDSelect; the no-arg parent form returns
        the Top-DICT /Private value (which is unused for CIDKeyed
        CFF). We honour both shapes: pass ``gid=-1`` (the default) to
        get the Top-DICT value for parity with non-CID fonts.
        """
        if gid < 0:
            return super().get_default_width_x()
        return self.get_default_width_x_for_gid(gid)

    def get_nominal_width_x(self, gid: int = -1) -> float:  # noqa: D401
        """Per-GID nominalWidthX override (mirror of
        :meth:`get_default_width_x`)."""
        if gid < 0:
            return super().get_nominal_width_x()
        return self.get_nominal_width_x_for_gid(gid)

    # ---------- bulk dict accessors ----------

    def get_font_dicts(self) -> list[dict[str, Any]]:
        """PDFBox: ``CFFCIDFont.getFontDicts()`` — every Font DICT in
        /FDArray, in array order. Mirrors upstream's
        ``List<Map<String, Object>>`` shape."""
        arr = self.get_fd_array()
        return [arr.get_font_dict(i) for i in range(arr.size())]

    def get_priv_dicts(self) -> list[dict[str, Any]]:
        """PDFBox: ``CFFCIDFont.getPrivDicts()`` — every Private DICT
        in /FDArray, in array order. (Note the upstream typo ``Priv``
        rather than ``Private`` is preserved for parity.)"""
        arr = self.get_fd_array()
        return [arr.get_private_dict(i) for i in range(arr.size())]

    # ---------- selector-keyed glyph access ----------

    @staticmethod
    def _coerce_to_cid(selector: int | str) -> int:
        """Map a PDFBox-style ``selector`` (integer CID or string of
        the form ``"NNN"`` / ``"cidNNNNN"``) to a CID. Returns ``-1``
        when the input is unparseable."""
        if isinstance(selector, int):
            return selector
        if isinstance(selector, str):
            if selector.startswith("cid"):
                tail = selector[3:]
                if tail.isdigit():
                    return int(tail)
            if selector.lstrip("-").isdigit():
                return int(selector)
        return -1

    def has_glyph(self, selector: int | str) -> bool:  # type: ignore[override]
        """PDFBox: ``CFFCIDFont.hasGlyph(int|String)`` — whether the
        font carries a glyph for the given CID."""
        cid = self._coerce_to_cid(selector)
        if cid < 0:
            return False
        return f"cid{cid:05d}" in self.get_charset()

    def get_path(self, selector: int | str) -> list[tuple]:  # type: ignore[override]
        """PDFBox: ``CFFCIDFont.getPath(int|String)`` — outline for the
        glyph identified by CID."""
        cid = self._coerce_to_cid(selector)
        if cid < 0:
            return []
        gid = self.gid_for_cid(cid)
        name = self.get_name_for_gid(gid)
        if not name:
            return []
        return super().get_path(name)

    def get_width(self, selector: int | str) -> float:  # type: ignore[override]
        """PDFBox: ``CFFCIDFont.getWidth(int|String)`` — advance width
        for the glyph identified by CID."""
        cid = self._coerce_to_cid(selector)
        if cid < 0:
            return 0.0
        gid = self.gid_for_cid(cid)
        name = self.get_name_for_gid(gid)
        if not name:
            return 0.0
        return super().get_width(name)

    def get_type2_char_string(self, cid_or_gid: int) -> Any:  # noqa: D401
        """PDFBox: ``CFFCIDFont.getType2CharString(int cid)`` — wraps
        the GID resolved from the CID into a :class:`Type2CharString`.

        Per upstream contract the parameter is a *CID*, not a GID;
        this method does the CID→GID resolution before delegating
        to the base class accessor. Out-of-range CIDs route through
        the empty-wrapper fallback in :class:`CFFFont`.
        """
        gid = self.gid_for_cid(cid_or_gid)
        return super().get_type2_char_string(gid)

    def gid_for_cid(self, cid: int) -> int:
        """Resolve a CID to a GID via the parsed charset.

        fontTools' charset for CIDKeyed fonts contains synthetic
        ``cid<NNNNN>`` names indexed by GID. We do a linear scan because
        the charset is typically a few thousand entries and this lookup
        is not on the hot rendering path; cache externally if you need it.

        Returns 0 (.notdef GID) for an unmapped CID — matches the PDF
        rendering contract for missing glyphs.
        """
        if cid < 0:
            return 0
        target = f"cid{cid:05d}"
        for gid, name in enumerate(self.get_charset()):
            if name == target:
                return gid
        return 0

    def is_cid_font(self) -> bool:  # noqa: D401 — overrides base
        """A :class:`CFFCIDFont` is, by definition, a CIDKeyed font."""
        return True


__all__ = ["CFFCIDFont"]
