from __future__ import annotations

from typing import Any


def _make_extended_extractor(pen: Any, subrs: Any) -> Any:
    """Build a T1 outline extractor that fills in the arithmetic / stack
    operators fontTools leaves as ``NotImplementedError``.

    fontTools' ``T1OutlineExtractor`` (MIT, vendored only at runtime) has
    full coverage for the path / subroutine / flex operators we need —
    ``hstem``, ``vstem``, ``vmoveto``, ``rlineto``, ``hlineto``,
    ``vlineto``, ``rrcurveto``, ``closepath``, ``hmoveto``, ``rmoveto``,
    ``callsubr``, ``return``, ``endchar``, ``hsbw``, ``sbw``, the
    Adobe-Type-1 flex sequence (``1 0 callothersubr`` … ``3 0
    callothersubr 0 callsubr``), ``setcurrentpoint``, ``seac``, ``div``,
    ``pop``. It explicitly raises ``NotImplementedError`` for ``dup``
    and ``exch`` (see ``op_dup`` / ``op_exch`` in
    ``fontTools.misc.psCharStrings``). Real-world Type 1 glyph
    charstrings rarely use these on the operand stack — they appear in
    Other-Subroutine machinery — but PDFBox handles them, so we do too.
    """
    from fontTools.misc import psCharStrings  # type: ignore[import-untyped]  # noqa: PLC0415

    class _Type1ExtendedExtractor(psCharStrings.T1OutlineExtractor):  # type: ignore[misc]
        def op_dup(self, index: int) -> None:
            # PostScript ``dup``: duplicate the top of the operand stack.
            top = self.pop()
            self.push(top)
            self.push(top)

        def op_exch(self, index: int) -> None:
            # PostScript ``exch``: swap the top two operands.
            top = self.pop()
            second = self.pop()
            self.push(top)
            self.push(second)

    return _Type1ExtendedExtractor(pen, subrs)


def _draw_with_extended_extractor(t1: Any, pen: Any) -> float:
    """Run the wrapped charstring against ``pen`` using the extended
    extractor (with ``dup`` / ``exch`` filled in). Returns the advance
    width recorded by the ``hsbw`` / ``sbw`` prologue."""
    extractor = _make_extended_extractor(pen, getattr(t1, "subrs", None))
    extractor.execute(t1)
    width = float(getattr(extractor, "width", 0.0) or 0.0)
    # Mirror fontTools' own ``T1CharString.draw`` side-effect: stash the
    # width on the charstring so a follow-up ``getattr(t1, "width")``
    # returns the same value as native fontTools.
    t1.width = width
    return width


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used elsewhere in pypdfbox
    (mirrors ``cff_font._make_path_pen`` and
    ``type2_char_string._make_path_pen``).
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


class Type1CharString:
    """Type 1 charstring wrapper.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.cff.Type1CharString``. Internally we delegate
    **all** charstring interpretation — opcodes (rmoveto / hmoveto /
    vmoveto / rlineto / hlineto / vlineto / rrcurveto / vhcurveto /
    hvcurveto / closepath), the ``hsbw`` / ``sbw`` width prologue, the
    ``seac`` accented-character composite, ``callsubr`` recursion and
    the flex / setcurrentpoint othersubr machinery — to
    ``fontTools.misc.psCharStrings.T1CharString`` (MIT-licensed). We do
    not reimplement the Type 1 interpreter in pure Python; per the
    project's library-first rule, generic font / charstring concerns
    wrap an existing permissive library.

    The constructor accepts either:

    * a fontTools ``T1CharString`` instance directly (preferred, when
      the caller already has one from a parsed Type 1 program), passed
      via the ``sequence`` parameter;
    * raw Type 1 bytecode as ``bytes`` / ``bytearray``, in which case a
      fresh ``T1CharString`` is decompiled here;
    * a Python list of operands and ``CharStringCommand``-shaped
      tokens, exposed as the upstream ``sequence`` parameter — this is
      compiled into a fontTools program list when possible. Mixed
      sequences fall back to storing the raw program; ``draw()`` will
      then need a ``T1CharString`` already attached.
    * ``None`` for an empty wrapper (path is ``[]``, width is ``0``).

    Upstream's ``Type1CharString`` does not expose a glyph index — only
    ``Type2CharString`` carries a GID. We carry a ``gid`` field anyway
    so subclasses (and parity tests) can mirror the same constructor
    shape; pass ``-1`` (or any sentinel) when the index is undefined.
    """

    def __init__(
        self,
        font: Any,
        font_name: str,
        glyph_name: str,
        sequence: Any,
        gid: int = -1,
    ) -> None:
        # Upstream signature (camelCase → snake_case per CLAUDE.md):
        #   Type1CharString(Type1CharStringReader font, String fontName,
        #                   String glyphName, List<Object> sequence)
        # plus the optional ``gid`` so Type2CharString-shaped callers
        # (and our parity tests) have a uniform constructor.
        self._font = font
        self._font_name = font_name
        self._glyph_name = glyph_name
        self._gid = int(gid)
        self._t1: Any = None
        self._cached_path: list[tuple[Any, ...]] | None = None
        self._cached_width: float | None = None
        # Mirror upstream's ``type1Sequence`` — the raw list of operands +
        # ``CharStringCommand``-shaped tokens. Subclasses (notably
        # ``Type2CharString``) and parity callers use ``add_command`` /
        # ``is_sequence_empty`` / ``get_last_sequence_entry`` against this
        # buffer. We also keep a copy of the originally-supplied list when
        # the caller passes one, for ``__str__``-style introspection.
        self._type1_sequence: list[Any] = []

        from fontTools.misc import psCharStrings  # noqa: PLC0415

        if isinstance(sequence, psCharStrings.T1CharString):
            self._t1 = sequence
        elif isinstance(sequence, (bytes, bytearray, memoryview)):
            self._t1 = psCharStrings.T1CharString(bytecode=bytes(sequence))
        elif isinstance(sequence, list):
            # Caller passed a pre-decompiled program list. fontTools
            # accepts a heterogeneous list of numbers + string operator
            # names, which is exactly what upstream PDFBox's
            # ``List<Object>`` carries (numbers + CharStringCommand).
            program = [_coerce_program_token(tok) for tok in sequence]
            self._t1 = psCharStrings.T1CharString(program=program)
            # Preserve the original tokens for sequence accessors.
            self._type1_sequence = list(sequence)
        elif sequence is None:
            self._t1 = psCharStrings.T1CharString()
        else:
            msg = (
                "sequence must be a T1CharString, bytes, list of program "
                f"tokens, or None — got {type(sequence).__name__}"
            )
            raise TypeError(msg)

    # ---------- accessors (PDFBox-shaped) -----------------------------------

    def get_gid(self) -> int:
        """Glyph index. Upstream ``Type1CharString`` has no GID accessor;
        this is the same field carried for ``Type2CharString``-shaped
        symmetry. Returns ``-1`` when undefined."""
        return self._gid

    def get_name(self) -> str:
        """PDFBox: ``Type1CharString.getName()`` — glyph name."""
        return self._glyph_name

    def get_font_name(self) -> str:
        """PostScript name of the parent font (upstream
        ``Type1CharString.getFontName()`` is package-private; we expose
        it for parity with ``Type2CharString``)."""
        return self._font_name

    # ---------- behaviour ---------------------------------------------------

    def get_width(self) -> float:
        """Advance width of this glyph in font units.

        Mirrors ``Type1CharString.getWidth()``. Adobe Type 1 spec §6.4:
        the ``hsbw`` / ``sbw`` prologue carries the advance. The
        fontTools ``T1OutlineExtractor`` records this as ``self.width``
        on the underlying ``T1CharString`` after ``draw()`` runs, so we
        force a one-off draw against a ``NullPen`` if we have not yet
        rendered the glyph.
        """
        if self._cached_width is not None:
            return self._cached_width
        # If we already rendered (path cached), the width attribute is
        # already populated by fontTools — read it directly.
        if self._cached_path is not None:
            self._cached_width = float(getattr(self._t1, "width", 0.0) or 0.0)
            return self._cached_width

        from fontTools.pens.basePen import NullPen  # noqa: PLC0415

        try:
            self._cached_width = _draw_with_extended_extractor(
                self._t1, NullPen()
            )
        except Exception:  # noqa: BLE001
            self._cached_width = 0.0
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
        seac accented composites, flex variants) is delegated to
        fontTools.
        """
        if self._cached_path is not None:
            return list(self._cached_path)
        pen = _make_path_pen()
        try:
            width = _draw_with_extended_extractor(self._t1, pen)
        except Exception:  # noqa: BLE001
            self._cached_path = []
            return []
        # Side-effect: extractor populates the advance width — cache it
        # now so a follow-up ``get_width()`` avoids a second draw.
        if self._cached_width is None:
            self._cached_width = width
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
            if tag in ("moveto", "lineto"):
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
        the underlying Type 1 sequence buffer.

        Mirrors upstream ``Type1CharString.addCommand(List<Number>,
        CharStringCommand)`` (package-protected). ``Type2CharString`` uses
        this to materialize converted Type 1 commands during the Type 2 →
        Type 1 conversion pass.
        """
        self._type1_sequence.extend(numbers)
        self._type1_sequence.append(command)

    def is_sequence_empty(self) -> bool:
        """Return ``True`` when the underlying Type 1 sequence buffer has
        no entries. Mirrors upstream ``Type1CharString.isSequenceEmpty()``
        (package-protected)."""
        return not self._type1_sequence

    def get_last_sequence_entry(self) -> Any:
        """Return the last entry of the underlying Type 1 sequence buffer,
        or ``None`` when empty. Mirrors upstream
        ``Type1CharString.getLastSequenceEntry()`` (package-protected)."""
        if not self._type1_sequence:
            return None
        return self._type1_sequence[-1]

    # ---------- low-level access -------------------------------------------

    @property
    def t1(self) -> Any:
        """The underlying ``fontTools.misc.psCharStrings.T1CharString``.

        Exposed for callers that want to introspect the bytecode /
        program list or run their own pen against it.
        """
        return self._t1

    def __repr__(self) -> str:
        return (
            f"Type1CharString(font={self._font_name!r}, "
            f"glyph={self._glyph_name!r}, gid={self._gid})"
        )

    def __str__(self) -> str:
        """Stringified Type 1 sequence — mirrors upstream
        ``Type1CharString.toString()`` which returns
        ``type1Sequence.toString().replace("|","\\n").replace(",", " ")``.

        Operates on the preserved list-form sequence when available;
        falls back to the fontTools ``T1CharString`` program list
        otherwise. Returns ``"[]"`` when neither is populated.
        """
        seq = self._type1_sequence
        if not seq:
            program = getattr(self._t1, "program", None)
            seq = list(program) if program else []
        if not seq:
            return "[]"
        # Java's ``List.toString()`` is "[a, b, c]"; upstream then swaps
        # ',' → ' ' and '|' → '\n'. Numbers / strings stringify directly.
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
    into the form fontTools' ``T1CharString.program`` expects:
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


__all__ = ["Type1CharString"]
