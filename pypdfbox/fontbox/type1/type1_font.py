from __future__ import annotations

from typing import Any


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used by ``PD…Font.get_glyph_path``.

    Lazily imports fontTools so this module is cheap to import when no
    glyph paths are ever requested.
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


class Type1Font:
    """Type 1 (PostScript) font wrapper.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.type1.Type1Font`` (a subset — full PostScript
    introspection is not exposed). Internally, parsing is delegated to
    the (MIT-licensed) ``fontTools.t1Lib.T1Font`` which already provides
    a battle-tested PostScript-subset interpreter and eexec / charstring
    decoder. We do not reimplement Type 1 parsing in pure Python.

    The fontTools-side ``T1Font`` requires a file path, but PDF
    ``/FontFile`` streams arrive as in-memory bytes — so this class
    bypasses the file path and feeds the raw bytes through the same
    chunk-discovery + hex-eexec normalisation that ``readOther`` runs.

    fontTools is imported lazily inside :meth:`from_bytes` so callers
    that never touch a Type 1 stream do not pay its import cost.
    """

    def __init__(self) -> None:
        self._t1: Any | None = None  # fontTools T1Font instance
        self._charstrings: dict[str, Any] | None = None
        self._font_matrix: list[float] | None = None
        self._units_per_em: int | None = None
        # Per-glyph advance cache. The fontTools T1CharString sets the
        # advance on the charstring object only after .draw() runs, so we
        # memoise once we've forced a draw.
        self._widths: dict[str, float] = {}

    # ---------- factory ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "Type1Font":
        """Parse a Type 1 PostScript font from raw ``/FontFile`` bytes.

        Bytes must follow the PDF 32000-1 §9.9 layout — cleartext header
        followed by binary eexec section followed by trailing zeros — or
        the equivalent hex-encoded form. PFB-wrapped (0x80-prefixed)
        bytes are NOT supported here; call :meth:`from_pfb_bytes` for
        those (PDF /FontFile streams are never PFB-wrapped).
        """
        from fontTools.t1Lib import (  # noqa: PLC0415
            T1Font,
            assertType1,
            deHexString,
            findEncryptedChunks,
            isHex,
        )
        from fontTools.misc.py23 import bytesjoin  # noqa: PLC0415

        raw = bytes(data)
        assertType1(raw)
        chunks = findEncryptedChunks(raw)
        normalised: list[bytes] = []
        for is_encrypted, chunk in chunks:
            if is_encrypted and isHex(chunk[:4]):
                normalised.append(deHexString(chunk))
            else:
                normalised.append(chunk)
        merged = bytesjoin(normalised)

        # Subclass T1Font in-place to skip its file-path read; everything
        # downstream (parse + draw) keys off self.data + self.encoding.
        t1 = T1Font.__new__(T1Font)
        t1.data = merged
        t1.encoding = "ascii"
        # Touching the font dict triggers parse() which lazily decrypts
        # eexec and converts each charstring to a fontTools T1CharString.
        _ = t1["CharStrings"]

        instance = cls()
        instance._t1 = t1
        return instance

    # ---------- font-level metrics ----------

    @property
    def font_matrix(self) -> list[float]:
        """Six-element font matrix (Type 1 default ``[0.001 0 0 0.001 0 0]``)."""
        if self._font_matrix is None:
            assert self._t1 is not None  # noqa: S101 — guarded by from_bytes
            matrix = self._t1["FontMatrix"]
            self._font_matrix = [float(v) for v in matrix]
        return self._font_matrix

    @property
    def units_per_em(self) -> int:
        """Derived from the font matrix's x-scale (matrix[0]).

        Type 1 fonts do not store ``unitsPerEm`` directly — they encode
        it as ``1 / matrix[0]`` (matrix is em -> user-space). For the
        Adobe-default matrix ``[0.001 ...]`` this yields ``1000``.
        """
        if self._units_per_em is None:
            scale = self.font_matrix[0]
            self._units_per_em = int(round(1.0 / scale)) if scale else 1000
        return self._units_per_em

    # ---------- glyph access ----------

    def has_glyph(self, name: str) -> bool:
        try:
            return name in self._charstrings_dict()
        except AssertionError:
            return False

    def _charstrings_dict(self) -> dict[str, Any]:
        if self._charstrings is None:
            assert self._t1 is not None  # noqa: S101
            self._charstrings = self._t1["CharStrings"]
        return self._charstrings

    def get_width(self, name: str) -> float:
        """Advance width of glyph ``name`` in *font units* (typically 1000-unit em).

        Returns ``0.0`` when the glyph is missing from the charstrings
        table. The fontTools T1CharString stores the advance on the
        instance only after ``.draw()`` has run, so we trigger a one-off
        draw against a no-op pen the first time we ask for a width.
        """
        cached = self._widths.get(name)
        if cached is not None:
            return cached
        cs_map = self._charstrings_dict()
        cs = cs_map.get(name)
        if cs is None:
            return 0.0
        # Force draw to populate .width. We use a no-op pen so we don't
        # build the path twice.
        from fontTools.pens.basePen import NullPen  # noqa: PLC0415

        try:
            cs.draw(NullPen())
        except Exception:  # noqa: BLE001
            return 0.0
        width = float(getattr(cs, "width", 0.0) or 0.0)
        self._widths[name] = width
        return width

    def get_path(self, name: str) -> list[tuple]:
        """Glyph outline for ``name`` as a list of draw commands in
        font units. Returns ``[]`` when the glyph is missing.

        Format: ``("moveto", x, y)``, ``("lineto", x, y)``,
        ``("curveto", x1, y1, x2, y2, x, y)``, ``("closepath",)``.
        """
        cs_map = self._charstrings_dict()
        cs = cs_map.get(name)
        if cs is None:
            return []
        pen = _make_path_pen()
        try:
            cs.draw(pen)
        except Exception:  # noqa: BLE001
            return []
        # Side-effect: the draw populates cs.width — cache it while we're here.
        self._widths.setdefault(name, float(getattr(cs, "width", 0.0) or 0.0))
        return list(pen.commands)  # type: ignore[attr-defined]


__all__ = ["Type1Font"]
