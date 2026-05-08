from __future__ import annotations

from typing import Any


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used elsewhere in pypdfbox
    (mirrors ``cff_font._make_path_pen``).
    """
    from fontTools.pens.basePen import BasePen  # type: ignore[import-untyped]  # noqa: PLC0415

    class _PathPen(BasePen):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(glyphSet=None)
            self.commands: list[tuple[Any, ...]] = []

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


class Type2CharString:
    """CFF Type 2 charstring wrapper.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.cff.Type2CharString`` (which itself extends
    ``Type1CharString``). Internally we delegate **all** charstring
    interpretation — opcodes, subroutine recursion, hint masks, the
    width prologue per CFF spec §3.1, flex/hflex/hflex1/flex1
    expansion, etc. — to ``fontTools.misc.psCharStrings.T2CharString``
    (MIT-licensed). We do not reimplement Type 2 → Type 1 conversion in
    pure Python; per the project's library-first rule, generic font /
    charstring concerns wrap an existing permissive library.

    The constructor accepts either:

    * a fontTools ``T2CharString`` instance directly (preferred, when
      the caller already has one from a parsed ``CFFFontSet``), passed
      via the ``sequence`` parameter;
    * raw Type 2 bytecode as ``bytes`` / ``bytearray``, in which case a
      fresh ``T2CharString`` is decompiled here;
    * a Python list of operands and ``CharStringCommand``-shaped
      tokens, exposed as the upstream ``sequence`` parameter — this is
      compiled into a fontTools program list when possible. Mixed
      sequences fall back to storing the raw program; ``draw()`` will
      then need a ``T2CharString`` already attached.
    """

    def __init__(
        self,
        font: Any,
        font_name: str,
        glyph_name: str,
        gid: int,
        sequence: Any,
        default_width_x: int = 0,
        nominal_width_x: int = 0,
    ) -> None:
        # Upstream signature (camelCase → snake_case per CLAUDE.md):
        #   Type2CharString(Type1CharStringReader font, String fontName,
        #                   String glyphName, int gid, List<Object> sequence,
        #                   int defaultWidthX, int nomWidthX)
        self._font = font
        self._font_name = font_name
        self._glyph_name = glyph_name
        self._gid = int(gid)
        self._default_width_x = float(default_width_x)
        self._nominal_width_x = float(nominal_width_x)
        self._t2: Any = None
        self._cached_path: list[tuple[Any, ...]] | None = None
        self._cached_width: float | None = None
        # Mirror upstream's ``type1Sequence`` (inherited from
        # ``Type1CharString`` in Java). Upstream's
        # ``convertType1ToType2`` populates this buffer via
        # ``addCommand`` as it walks the Type 2 program; the rendering
        # path then iterates over it. We don't reimplement that
        # conversion (fontTools handles Type 2 → Path directly), but we
        # expose the same accessor surface so callers / parity tests can
        # build / inspect a Type 1 sequence buffer.
        self._type1_sequence: list[Any] = []

        from fontTools.misc import psCharStrings  # type: ignore[import-untyped]  # noqa: PLC0415

        if isinstance(sequence, psCharStrings.T2CharString):
            self._t2 = sequence
        elif isinstance(sequence, (bytes, bytearray, memoryview)):
            self._t2 = psCharStrings.T2CharString(bytecode=bytes(sequence))
        elif isinstance(sequence, list):
            # Caller passed a pre-decompiled program list. fontTools
            # accepts a heterogeneous list of numbers + string operator
            # names, which is exactly what upstream PDFBox's
            # ``List<Object>`` carries (numbers + CharStringCommand).
            program = [
                _coerce_program_token(tok) for tok in sequence
            ]
            self._t2 = psCharStrings.T2CharString(program=program)
            # Preserve the original tokens for sequence accessors and
            # upstream-shaped stringification, matching Type1CharString.
            self._type1_sequence = list(sequence)
        elif sequence is None:
            self._t2 = psCharStrings.T2CharString()
        else:
            msg = (
                "sequence must be a T2CharString, bytes, list of program "
                f"tokens, or None — got {type(sequence).__name__}"
            )
            raise TypeError(msg)

    # ---------- accessors (PDFBox-shaped) -----------------------------------

    def get_gid(self) -> int:
        """PDFBox: ``Type2CharString.getGID()`` — glyph index in the parent CFF font."""
        return self._gid

    def get_name(self) -> str:
        """PDFBox: ``Type1CharString.getName()`` — glyph name (or ``cid<NNNNN>``
        for CID-keyed fonts)."""
        return self._glyph_name

    def get_font_name(self) -> str:
        """PostScript name of the parent font (``Type1CharString.getFontName()``)."""
        return self._font_name

    def get_default_width_x(self) -> float:
        return self._default_width_x

    def get_nominal_width_x(self) -> float:
        return self._nominal_width_x

    # ---------- behaviour ---------------------------------------------------

    def get_width(self) -> float:
        """Advance width of this glyph in font units.

        Mirrors ``Type1CharString.getWidth()``. CFF spec §3.1 / §10:
        a leading operand on the stack before the first moveto is
        interpreted as ``width - nominalWidthX``; charstrings without
        such a leading operand inherit ``defaultWidthX``.

        Width extraction is delegated to fontTools'
        ``T2WidthExtractor``; we do not parse the charstring prologue
        ourselves.
        """
        if self._cached_width is not None:
            return self._cached_width
        from fontTools.misc import psCharStrings  # noqa: PLC0415

        # The width extractor needs access to local + global subrs to
        # follow callsubr / callgsubr in the prologue. fontTools
        # T2CharString carries pointers to both via .private / .globalSubrs
        # when sourced from a parsed CFFFontSet; when constructed bare
        # we fall back to empty indexes.
        priv = getattr(self._t2, "private", None)
        local_subrs = getattr(priv, "Subrs", []) or []
        global_subrs = getattr(self._t2, "globalSubrs", []) or []
        extractor = psCharStrings.T2WidthExtractor(
            local_subrs,
            global_subrs,
            self._nominal_width_x,
            self._default_width_x,
        )
        try:
            extractor.execute(self._t2)
        except Exception:  # noqa: BLE001
            self._cached_width = self._default_width_x
            return self._cached_width
        self._cached_width = float(extractor.width)
        return self._cached_width

    def get_path(self) -> list[tuple[Any, ...]]:
        """Glyph outline as a list of draw commands in font units.

        Mirrors ``Type1CharString.getPath()``. Returns the same
        list-of-tuples format used by ``CFFFont.get_path``:

        * ``("moveto", x, y)``
        * ``("lineto", x, y)``
        * ``("curveto", x1, y1, x2, y2, x3, y3)``
        * ``("closepath",)``

        All charstring interpretation (operators, subroutine recursion,
        flex variants, hint masks) is delegated to fontTools.
        """
        if self._cached_path is not None:
            return list(self._cached_path)
        pen = _make_path_pen()
        try:
            self._t2.draw(pen)
        except Exception:  # noqa: BLE001
            self._cached_path = []
            return []
        self._cached_path = list(pen.commands)
        return list(self._cached_path)

    def get_bounds(self) -> tuple[float, float, float, float] | None:
        """Bounding box ``(xmin, ymin, xmax, ymax)`` of the glyph outline,
        or ``None`` for an empty path. Equivalent to upstream
        ``Type1CharString.getBounds()`` returning ``Rectangle2D``."""
        path = self.get_path()
        xs: list[float] = []
        ys: list[float] = []
        for cmd in path:
            tag = cmd[0]
            if tag == "moveto" or tag == "lineto":
                xs.append(cmd[1])
                ys.append(cmd[2])
            elif tag == "curveto":
                xs.extend((cmd[1], cmd[3], cmd[5]))
                ys.extend((cmd[2], cmd[4], cmd[6]))
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    # ---------- sequence accessors (parity with upstream protected API) ----

    def add_command(self, numbers: list[Any], command: Any) -> None:
        """Append a list of operands followed by a single command token to
        the Type 1 sequence buffer inherited from ``Type1CharString``
        upstream. Mirrors ``Type1CharString.addCommand(List<Number>,
        CharStringCommand)`` — used by upstream's
        ``Type2CharString.convertType1ToType2``."""
        self._type1_sequence.extend(numbers)
        self._type1_sequence.append(command)

    def is_sequence_empty(self) -> bool:
        """``True`` when the Type 1 sequence buffer is empty. Mirrors
        upstream ``Type1CharString.isSequenceEmpty()`` (package-protected)."""
        return not self._type1_sequence

    def get_last_sequence_entry(self) -> Any:
        """Return the last entry of the Type 1 sequence buffer, or
        ``None`` when empty. Mirrors upstream
        ``Type1CharString.getLastSequenceEntry()`` (package-protected)."""
        if not self._type1_sequence:
            return None
        return self._type1_sequence[-1]

    # ---------- low-level access -------------------------------------------

    @property
    def t2(self) -> Any:
        """The underlying ``fontTools.misc.psCharStrings.T2CharString``.

        Exposed for callers that want to introspect the bytecode /
        program list or run their own pen against it.
        """
        return self._t2

    def __repr__(self) -> str:
        return (
            f"Type2CharString(font={self._font_name!r}, "
            f"glyph={self._glyph_name!r}, gid={self._gid})"
        )

    def __str__(self) -> str:
        """Stringified Type 1 sequence — mirrors upstream
        ``Type1CharString.toString()`` (inherited). Operates on the
        preserved list-form sequence when available; falls back to the
        fontTools ``T2CharString`` program list otherwise. Returns
        ``"[]"`` when neither is populated.
        """
        seq = self._type1_sequence
        if not seq:
            program = getattr(self._t2, "program", None)
            seq = list(program) if program else []
        if not seq:
            return "[]"
        body = ", ".join(_stringify_token(tok) for tok in seq)
        return ("[" + body + "]").replace("|", "\n").replace(",", " ")


def _stringify_token(tok: Any) -> str:
    """Render a sequence token the way Java ``List.toString()`` would.

    Numbers stringify via ``str()``; ``CharStringCommand``-shaped tokens
    expose a ``.name`` attribute we prefer; everything else falls back to
    ``str()``.
    """
    if isinstance(tok, (int, float)):
        return str(tok)
    name = getattr(tok, "name", None)
    if isinstance(name, str):
        return name
    return str(tok)


def _coerce_program_token(tok: Any) -> Any:
    """Translate an upstream-shaped program token (number, str, or
    object exposing a ``.name`` attribute à la ``CharStringCommand``)
    into the form fontTools' ``T2CharString.program`` expects:
    numbers as-is, operators as their string mnemonic.
    """
    if isinstance(tok, (int, float)):
        return tok
    if isinstance(tok, str):
        return tok
    name = getattr(tok, "name", None)
    if isinstance(name, str):
        return name
    # Last resort: stringify. fontTools' decompiler may reject this,
    # but we never silently drop tokens.
    return str(tok)


__all__ = ["Type2CharString"]
