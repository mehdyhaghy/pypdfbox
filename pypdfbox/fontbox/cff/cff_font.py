from __future__ import annotations

import io
from typing import Any


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used by ``PD…Font.get_glyph_path``.
    """
    from fontTools.pens.basePen import BasePen  # noqa: PLC0415

    class _PathPen(BasePen):
        def __init__(self) -> None:
            super().__init__(glyphSet=None)
            self.commands: list[tuple] = []

        def _moveTo(self, pt: tuple[float, float]) -> None:
            self.commands.append(("moveto", float(pt[0]), float(pt[1])))

        def _lineTo(self, pt: tuple[float, float]) -> None:
            self.commands.append(("lineto", float(pt[0]), float(pt[1])))

        def _curveToOne(
            self,
            pt1: tuple[float, float],
            pt2: tuple[float, float],
            pt3: tuple[float, float],
        ) -> None:
            self.commands.append(
                (
                    "curveto",
                    float(pt1[0]),
                    float(pt1[1]),
                    float(pt2[0]),
                    float(pt2[1]),
                    float(pt3[0]),
                    float(pt3[1]),
                )
            )

        def _closePath(self) -> None:
            self.commands.append(("closepath",))

    return _PathPen()


class CFFFont:
    """Compact Font Format (CFF / Type 1C) font wrapper.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.cff.CFFFont`` (subset). Internally, parsing is
    delegated to ``fontTools.cffLib.CFFFontSet`` (MIT) — we do not
    reimplement CFF DICT / INDEX / charstring parsing in pure Python.

    A CFF *font set* may contain multiple top-level fonts; for the
    PDF /FontFile3 use-case there is always exactly one and we expose
    it as the ``primary`` font transparently.
    """

    def __init__(self) -> None:
        self._fontset: Any | None = None  # fontTools CFFFontSet
        self._top: Any | None = None  # primary top-level font dict
        self._charstrings: Any | None = None
        self._private: Any | None = None
        self._font_matrix: list[float] | None = None
        self._units_per_em: int | None = None
        # Per-glyph width cache. CFF charstring widths are computed by
        # the T2WidthExtractor below and memoised here.
        self._widths: dict[str, float] = {}

    # ---------- factory ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "CFFFont":
        """Parse a CFF font from raw ``/FontFile3`` bytes (``/Subtype /Type1C``)."""
        from fontTools.cffLib import CFFFontSet  # noqa: PLC0415

        fontset = CFFFontSet()
        fontset.decompile(io.BytesIO(bytes(data)), otFont=None)
        if not fontset.fontNames:
            msg = "CFF font set is empty"
            raise OSError(msg)

        instance = cls()
        instance._fontset = fontset
        instance._top = fontset[fontset.fontNames[0]]
        return instance

    # ---------- font-level metrics ----------

    @property
    def font_names(self) -> list[str]:
        if self._fontset is None:
            return []
        return list(self._fontset.fontNames)

    @property
    def name(self) -> str | None:
        names = self.font_names
        return names[0] if names else None

    @property
    def font_matrix(self) -> list[float]:
        """Six-element font matrix. Default for CFF is ``[0.001 0 0 0.001 0 0]``."""
        if self._font_matrix is None:
            assert self._top is not None  # noqa: S101
            matrix = self._top.FontMatrix
            self._font_matrix = [float(v) for v in matrix]
        return self._font_matrix

    @property
    def units_per_em(self) -> int:
        """Derived from the font matrix's x-scale (matrix[0]).

        CFF defaults to ``[0.001 0 0 0.001 0 0]`` → 1000-unit em.
        """
        if self._units_per_em is None:
            scale = self.font_matrix[0]
            self._units_per_em = int(round(1.0 / scale)) if scale else 1000
        return self._units_per_em

    # ---------- glyph access ----------

    def _charstrings_dict(self) -> Any:
        if self._charstrings is None:
            assert self._top is not None  # noqa: S101
            self._charstrings = self._top.CharStrings
        return self._charstrings

    def has_glyph(self, name: str) -> bool:
        if self._top is None:
            return False
        try:
            return name in self._charstrings_dict()
        except Exception:  # noqa: BLE001
            return False

    def get_width(self, name: str) -> float:
        """Advance width of glyph ``name`` in *font units* (typically 1000-unit em).

        Uses fontTools' ``T2WidthExtractor`` to interpret the charstring
        prologue per CFF spec §3.1: a leading operand on the stack
        before the first moveto is interpreted as ``width - nominalWidthX``.
        Glyphs without a leading width operand default to ``defaultWidthX``.
        """
        cached = self._widths.get(name)
        if cached is not None:
            return cached
        cs_map = self._charstrings_dict()
        try:
            cs = cs_map[name]
        except KeyError:
            return 0.0

        from fontTools.misc.psCharStrings import T2WidthExtractor  # noqa: PLC0415

        assert self._top is not None  # noqa: S101
        priv = self._top.Private
        extractor = T2WidthExtractor(
            [],  # local subrs — fontTools resolves CharString.private.Subrs internally
            self._top.GlobalSubrs,
            getattr(priv, "nominalWidthX", 0),
            getattr(priv, "defaultWidthX", 0),
        )
        try:
            extractor.execute(cs)
        except Exception:  # noqa: BLE001
            return 0.0
        width = float(extractor.width)
        self._widths[name] = width
        return width

    def get_path(self, name: str) -> list[tuple]:
        """Glyph outline for ``name`` as a list of draw commands in
        font units. Returns ``[]`` when the glyph is missing."""
        cs_map = self._charstrings_dict()
        try:
            cs = cs_map[name]
        except KeyError:
            return []
        pen = _make_path_pen()
        try:
            cs.draw(pen)
        except Exception:  # noqa: BLE001
            return []
        return list(pen.commands)  # type: ignore[attr-defined]


__all__ = ["CFFFont"]
