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
        # ROS / FDArray overrides populated by the ``set_*`` mirror-methods
        # below. Upstream these setters are package-private; we expose
        # them for parity with callers (and tests) that synthesise a
        # :class:`CFFCIDFont` outside the parser path.
        self._registry_override: str | None = None
        self._ordering_override: str | None = None
        self._supplement_override: int | None = None
        self._font_dicts_override: list[dict[str, Any]] | None = None
        self._priv_dicts_override: list[dict[str, Any]] | None = None
        # Lazy Type 2 charstring parser handle (upstream
        # ``charStringParser`` / ``getParser()``); see :meth:`get_parser`.
        self._char_string_parser: Any = None

    # ---------- factories ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> CFFCIDFont:
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
    def from_cff_font(cls, base: CFFFont) -> CFFCIDFont:
        """Re-wrap an already-parsed :class:`CFFFont` as a
        :class:`CFFCIDFont`. Cheap — shares the underlying fontTools
        font set, no re-decompilation."""
        instance = cls()
        instance._copy_base_state_from(base)
        return instance

    # ---------- CID-specific accessors ----------

    def get_registry(self) -> str:
        """Registry component of /ROS (e.g. ``"Adobe"``)."""
        if self._registry_override is not None:
            return self._registry_override
        ros = self._ros()
        return ros[0] if ros else ""

    def set_registry(self, registry: str) -> None:
        """PDFBox: ``CFFCIDFont.setRegistry(String)`` — override the
        Registry component of /ROS. Upstream this is package-private;
        we expose it for parity with callers that synthesise a
        :class:`CFFCIDFont` outside the parser path."""
        self._registry_override = registry

    def get_ordering(self) -> str:
        """Ordering component of /ROS (e.g. ``"Japan1"``, ``"GB1"``)."""
        if self._ordering_override is not None:
            return self._ordering_override
        ros = self._ros()
        return ros[1] if ros else ""

    def set_ordering(self, ordering: str) -> None:
        """PDFBox: ``CFFCIDFont.setOrdering(String)`` — override the
        Ordering component of /ROS."""
        self._ordering_override = ordering

    def get_supplement(self) -> int:
        """Supplement component of /ROS (e.g. ``6``)."""
        if self._supplement_override is not None:
            return self._supplement_override
        ros = self._ros()
        return int(ros[2]) if ros else 0

    def set_supplement(self, supplement: int) -> None:
        """PDFBox: ``CFFCIDFont.setSupplement(int)`` — override the
        Supplement component of /ROS."""
        self._supplement_override = int(supplement)

    def get_ros(self) -> tuple[str, str, int]:
        """Convenience: full Registry/Ordering/Supplement triple."""
        # Honour ``set_*`` overrides individually so callers can
        # partially override (e.g. set the supplement only).
        if (
            self._registry_override is not None
            or self._ordering_override is not None
            or self._supplement_override is not None
        ):
            return (self.get_registry(), self.get_ordering(), self.get_supplement())
        ros = self._ros()
        if not ros:
            return ("", "", 0)
        return (str(ros[0]), str(ros[1]), int(ros[2]))

    def _ros(self) -> Any:
        if self._top is None:
            return None
        return getattr(self._top, "ROS", None) or self._top.rawDict.get("ROS")

    def get_cid_count(self) -> int:
        """CFF Top DICT /CIDCount (default :data:`CFFFont.DEFAULT_CID_COUNT`
        per CFF spec §10)."""
        if self._top is None:
            return 0
        return int(getattr(self._top, "CIDCount", self.DEFAULT_CID_COUNT))

    def get_fd_select(self) -> FDSelect:
        """The /FDSelect mapping GID → Font DICT index."""
        if self._fd_select is None:
            raw = (
                getattr(self._top, "FDSelect", None) if self._top is not None else None
            )
            self._fd_select = FDSelect.from_fonttools(raw)
        return self._fd_select

    def set_fd_select(self, fd_select: FDSelect) -> None:
        """PDFBox: ``CFFCIDFont.setFdSelect(FDSelect)`` — override the
        /FDSelect returned by :meth:`get_fd_select`."""
        self._fd_select = fd_select

    def get_fd_array(self) -> FDArray:
        """The /FDArray of per-FD Font DICTs."""
        if self._fd_array is None:
            raw = (
                getattr(self._top, "FDArray", None) if self._top is not None else None
            )
            self._fd_array = FDArray.from_fonttools(raw)
        return self._fd_array

    def has_fd_select(self) -> bool:
        """Predicate: whether the font carries a non-empty /FDSelect.

        A well-formed CIDKeyed CFF always has /FDSelect; this helper is
        for callers parsing partially-decoded payloads (e.g. synthesis
        in tests, or fonts loaded from /FontFile3 with the Top DICT
        only)."""
        return self.get_fd_select().get_num_glyphs() > 0

    def has_fd_array(self) -> bool:
        """Predicate: whether the font carries a non-empty /FDArray.

        Parallel to :py:meth:`has_fd_select`. False for synthetic
        :class:`CFFCIDFont` instances constructed without a backing
        font set."""
        return not self.get_fd_array().is_empty()

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

    def get_local_subr_index_for_gid(self, gid: int) -> list[bytes]:
        """Per-GID local subroutine bytecodes as a list of ``bytes``.

        Mirrors upstream package-private ``CFFCIDFont.getLocalSubrIndex(int gid)``:
        resolves the GID through /FDSelect to its FD index and returns
        the matching FD's /Subrs INDEX. T2 charstring decoders need this
        to resolve ``callsubr`` operators inside CIDKeyed CFF charstrings
        (each FD has its own local subrs).

        Empty list when the resolved FD has no Private DICT, no /Subrs,
        or when ``gid`` is out of range."""
        return self.get_fd_array().get_local_subr_index(
            self.get_fd_index_for_gid(gid)
        )

    def get_local_subr_index(self, gid: int) -> list[bytes]:
        """PDFBox: ``CFFCIDFont.getLocalSubrIndex(int gid)`` — strict
        snake_case parity alias for :meth:`get_local_subr_index_for_gid`.

        Upstream this is package-private; we expose it as a public method
        because charstring decoders sit in a separate module and cannot
        rely on Java's package-visibility scoping.
        """
        return self.get_local_subr_index_for_gid(gid)

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
        if self._font_dicts_override is not None:
            return list(self._font_dicts_override)
        arr = self.get_fd_array()
        return [arr.get_font_dict(i) for i in range(arr.size())]

    def set_font_dict(self, font_dict: list[dict[str, Any]]) -> None:
        """PDFBox: ``CFFCIDFont.setFontDict(List<Map<String, Object>>)``
        — override the Font DICT list returned by
        :meth:`get_font_dicts`. Upstream this is package-private; we
        expose it for parity."""
        self._font_dicts_override = list(font_dict)

    def get_priv_dicts(self) -> list[dict[str, Any]]:
        """PDFBox: ``CFFCIDFont.getPrivDicts()`` — every Private DICT
        in /FDArray, in array order. (Note the upstream typo ``Priv``
        rather than ``Private`` is preserved for parity.)"""
        if self._priv_dicts_override is not None:
            return list(self._priv_dicts_override)
        arr = self.get_fd_array()
        return [arr.get_private_dict(i) for i in range(arr.size())]

    def set_priv_dict(self, priv_dict: list[dict[str, Any]]) -> None:
        """PDFBox: ``CFFCIDFont.setPrivDict(List<Map<String, Object>>)``
        — override the Private DICT list returned by
        :meth:`get_priv_dicts`."""
        self._priv_dicts_override = list(priv_dict)

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

    @staticmethod
    def selector_to_cid(selector: str) -> int:
        """PDFBox: private ``CFFCIDFont.selectorToCID(String)`` —
        strict-form parser for the CID selector syntax used in PDFBox
        rendering paths (``"\\NNN"`` where ``NNN`` is the CID in
        decimal). Raises :class:`ValueError` for malformed input
        (upstream raises ``IllegalArgumentException``).

        We expose this publicly because Python lacks Java's package-
        private scoping; downstream charstring code may need the same
        strict parse for parity with rendering tests. The looser
        :meth:`_coerce_to_cid` (which also accepts bare digits and the
        ``"cidNNNNN"`` charset-name form) is preferred for general
        glyph access.
        """
        if not isinstance(selector, str) or not selector.startswith("\\"):
            msg = "Invalid selector"
            raise ValueError(msg)
        tail = selector[1:]
        if not tail or not tail.lstrip("-").isdigit():
            msg = "Invalid selector"
            raise ValueError(msg)
        return int(tail)

    def has_glyph(self, selector: int | str) -> bool:
        """PDFBox: ``CFFCIDFont.hasGlyph(int|String)`` — whether the
        font carries a glyph for the given CID."""
        cid = self._coerce_to_cid(selector)
        if cid < 0:
            return False
        return f"cid{cid:05d}" in self.get_charset()

    def get_path(self, selector: int | str) -> list[tuple[Any, ...]]:
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

    def get_width(self, selector: int | str) -> float:
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

    def get_parser(self) -> Any:
        """PDFBox: private ``CFFCIDFont.getParser()`` — lazy accessor
        for the per-font Type 2 charstring parser.

        Upstream this returns a ``Type2CharStringParser`` keyed by the
        font name. We do not have a hand-rolled Type2 parser (fontTools
        does the heavy lifting in :meth:`get_type2_char_string`); the
        returned object is a small adapter exposing a ``parse(bytes,
        global_subrs, local_subrs, glyph_id)`` shim that matches the
        upstream signature. Most callers only need this to interrogate
        the parser's ``font_name`` attribute.
        """
        if self._char_string_parser is None:
            self._char_string_parser = _Type2CharStringParser(self.get_name())
        return self._char_string_parser

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


class _Type2CharStringParser:
    """Minimal stand-in for upstream ``Type2CharStringParser``.

    Upstream's parser interprets raw Type 2 bytecode against global +
    local subroutines and emits a token sequence consumable by
    :class:`Type2CharString`. fontTools already does this end-to-end
    when it decompiles ``CharStrings``, so the stand-in only exists to
    give :meth:`CFFCIDFont.get_parser` something whose ``font_name``
    attribute callers can read for parity. The :meth:`parse` shim
    raises ``NotImplementedError`` — callers that hit it should switch
    to :meth:`CFFCIDFont.get_type2_char_string` (which uses fontTools).
    """

    def __init__(self, font_name: str) -> None:
        self.font_name = font_name

    def parse(
        self,
        bytecode: bytes,
        global_subrs: list[bytes],
        local_subrs: list[bytes] | None,
        glyph_id: str,
    ) -> list[Any]:
        msg = (
            "Standalone Type2CharStringParser is not implemented; use "
            "CFFCIDFont.get_type2_char_string(cid) which delegates to "
            "fontTools."
        )
        raise NotImplementedError(msg)

    def __repr__(self) -> str:
        return f"_Type2CharStringParser(font_name={self.font_name!r})"


__all__ = ["CFFCIDFont"]
