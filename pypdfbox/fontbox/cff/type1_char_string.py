from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _RenderContext:
    """Mutable state for a Type 1 charstring render pass.

    Mirrors the per-render fields on upstream ``Type1CharString``
    (``current``, ``leftSideBearing``, ``isFlex``, ``flexPoints``,
    ``width``, ``path``). Encapsulated as a small dataclass so the
    upstream-shaped private helpers (``rmove_to``, ``rline_to``,
    ``rrcurve_to``, ``close_char_string1_path``, ``call_other_subr``,
    ``set_current_point``, ``seac``, ``handle_type1_command``) can take
    explicit context rather than mutate ``self`` — this keeps the
    fontTools-based ``render()`` reentrant.
    """

    current: tuple[float, float] = (0.0, 0.0)
    left_side_bearing: tuple[float, float] = (0.0, 0.0)
    width: int = 0
    is_flex: bool = False
    flex_points: list[tuple[float, float]] = field(default_factory=list)
    path: list[tuple[Any, ...]] = field(default_factory=list)


def _font_subrs_as_charstrings(font: Any, ps_char_strings: Any) -> list[Any]:
    """Return the parent font's local ``/Private /Subrs`` as a list of
    executable fontTools ``T1CharString`` objects, suitable for assignment
    to a ``T1CharString.subrs`` so ``op_callsubr`` can ``execute`` them.

    The in-memory ``create_with_pfb`` path stores each subr as already-
    decrypted charstring *bytes*; the reload path stores decompiled
    ``T1CharString`` objects. Normalise both to ``T1CharString`` here.
    Anything we cannot interpret (no parent / no subrs / odd entry types)
    degrades to an empty list — a glyph that then issues ``callsubr`` will
    decode to a blank path, matching upstream's warn-and-drop for a
    charstring referencing a missing subroutine.
    """
    get = getattr(font, "get_subrs_array", None)
    if get is None:
        return []
    try:
        raw_subrs = get()
    except Exception:  # noqa: BLE001
        return []
    wrapped: list[Any] = []
    for entry in raw_subrs:
        if isinstance(entry, ps_char_strings.T1CharString):
            wrapped.append(entry)
        elif isinstance(entry, (bytes, bytearray, memoryview)):
            wrapped.append(ps_char_strings.T1CharString(bytecode=bytes(entry)))
        else:
            # Unknown subr representation — push a no-op so the index
            # stays aligned (a charstring calling it draws nothing rather
            # than raising and dropping the whole glyph).
            wrapped.append(ps_char_strings.T1CharString())
    return wrapped


def _command_name(command: Any) -> str:
    """Extract the operator mnemonic from a token.

    Accepts a plain ``str``, a ``CharStringCommand``-shaped object with a
    ``.name`` attribute, or anything else (returns ``""`` then). Mirrors
    the upstream ``CharStringCommand.getType1KeyWord()`` lookup but in
    the reduced surface fontTools exposes (string mnemonics).
    """
    if isinstance(command, str):
        return command
    name = getattr(command, "name", None)
    if isinstance(name, str):
        return name
    return ""


def _has_current_point(ctx: _RenderContext) -> bool:
    """Whether the path has an established current point.

    Upstream uses ``GeneralPath.getCurrentPoint() != null``. We track
    this by looking for any path command in ``ctx.path`` (an empty path
    has no current point).
    """
    return bool(ctx.path)


def _translate_path_cmd(
    cmd: tuple[Any, ...], tx: float, ty: float
) -> tuple[Any, ...]:
    """Translate a single path command by ``(tx, ty)``. Used by
    ``seac`` for the accent-character composite step."""
    tag = cmd[0]
    if tag in ("moveto", "lineto"):
        return (tag, cmd[1] + tx, cmd[2] + ty)
    if tag == "curveto":
        return (
            tag,
            cmd[1] + tx, cmd[2] + ty,
            cmd[3] + tx, cmd[4] + ty,
            cmd[5] + tx, cmd[6] + ty,
        )
    return cmd


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

        def op_sbw(self, index: int) -> None:
            # ``sbw`` (sbx sby wx wy sbw): the full side-bearing + width
            # prologue used by vertical writing-mode glyphs (Adobe Type 1
            # spec §6.4). fontTools' stock ``op_sbw`` is a no-op stub
            # (``self.popall()  # XXX``) that DISCARDS the operands and
            # never records the advance, so an ``sbw``-prologued glyph drew
            # with width 0. Apache FontBox's ``Type1CharString`` handles
            # ``sbw`` by setting the left side bearing to (sbx, sby), the
            # advance to wx, and the current point to (sbx, sby) — mirror
            # that so ``get_width`` returns the real horizontal advance.
            sbx, sby, wx, _wy = self.popall()
            self.width = wx
            self.sbx = sbx
            self.sby = sby
            self.currentPoint = sbx, sby

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


def _apply_affine(
    cmd: tuple[Any, ...],
    transform: tuple[float, float, float, float, float, float],
) -> tuple[Any, ...]:
    """Apply a 6-tuple affine ``(a, b, c, d, e, f)`` to a path command.

    Point ``(x, y)`` maps to ``(a*x + c*y + e, b*x + d*y + f)``. Used by
    the path pen's ``add_component`` to replay a seac base/accent glyph's
    outline under the component transform fontTools' ``op_seac`` supplies
    (``(1, 0, 0, 1, adx, ady)`` — the ``adx`` already carries the
    ``sbx - asb`` seac adjustment).
    """
    a, b, c, d, e, f = transform

    def _pt(x: float, y: float) -> tuple[float, float]:
        return (a * x + c * y + e, b * x + d * y + f)

    tag = cmd[0]
    if tag in ("moveto", "lineto"):
        nx, ny = _pt(cmd[1], cmd[2])
        return (tag, nx, ny)
    if tag == "curveto":
        x1, y1 = _pt(cmd[1], cmd[2])
        x2, y2 = _pt(cmd[3], cmd[4])
        x3, y3 = _pt(cmd[5], cmd[6])
        return (tag, x1, y1, x2, y2, x3, y3)
    return cmd


def _make_path_pen(font: Any = None) -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used elsewhere in pypdfbox
    (mirrors ``cff_font._make_path_pen`` and
    ``type2_char_string._make_path_pen``).

    ``font`` is the parent Type 1 charstring reader (a ``Type1Font`` /
    ``Type1CharStringReader``). It is consulted by ``add_component`` to
    resolve a ``seac`` composite's base/accent component outlines.
    fontTools' ``op_seac`` (in ``T1OutlineExtractor``) does not assemble
    the composite itself — it emits two ``pen.addComponent(glyphName,
    transform)`` calls (one per StandardEncoding component) and relies on
    the pen to fetch and replay each component's outline. ``BasePen``'s
    own ``addComponent`` raises ``NotImplementedError`` (and, with the
    ``glyphSet=None`` we pass, even the inherited fallback dereferences
    ``None`` and raises ``TypeError``), so without this override every
    seac accented glyph (``é``/``à``/``ñ``/``ç`` …) decoded to an empty
    path and rendered **blank** — the Type 1 analogue of the wave-1438
    TrueType composite-component drop.
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

        def addComponent(  # noqa: N802 (fontTools BasePen hook name)
            self,
            glyph_name: str,
            transformation: tuple[
                float, float, float, float, float, float
            ],
        ) -> None:
            """Resolve a ``seac`` component glyph by name and replay its
            (transformed) outline into this pen.

            ``op_seac`` calls this once for the base glyph (identity
            transform) and once for the accent glyph (translate by the
            ``adx``/``ady`` it already adjusted for the side bearing).
            We fetch the component outline through the parent reader's
            ``get_type1_char_string`` and append each command under the
            affine ``transformation``. Missing reader / lookup / self-
            recursion degrade to a no-op, matching upstream's seac
            warn-and-skip.
            """
            get = getattr(font, "get_type1_char_string", None)
            if get is None:
                return
            try:
                component = get(glyph_name)
                outline = component.get_path() or []
            except Exception:  # noqa: BLE001
                # Missing component / decode failure / runaway recursion
                # (a seac whose component resolves back to itself,
                # PDFBOX-5339) — skip, matching upstream warn-and-skip.
                return
            for cmd in outline:
                self.commands.append(_apply_affine(cmd, transformation))

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

        # Wire up the parent font's local /Private /Subrs so the charstring
        # interpreter can resolve ``callsubr`` (Adobe Type 1 spec §8.3). A
        # real .pfb's flex / hint-replacement machinery is reached through
        # ``callsubr`` into the four standard subroutines (Subr 0 = flex end,
        # Subr 1 = flex begin, Subr 2 = flex point, Subr 3 = hint
        # replacement), each of which fronts a ``callothersubr`` (OtherSubrs
        # 0/1/2/3). fontTools' ``op_callsubr`` does ``self.subrs[index]`` and
        # ``self.execute(subr)``, so the charstring must carry a ``subrs``
        # list of executable ``T1CharString`` objects.
        #
        # When ``sequence`` is already a ``T1CharString`` (the embedded
        # ``/FontFile`` reload path, where fontTools' ``t1Lib`` parse attaches
        # decompiled subrs), it already has them — leave those alone. For the
        # in-memory ``create_with_pfb`` path the charstring is built from raw
        # *bytes* / a program list with no subrs attached, so ``callsubr``
        # raised ``TypeError`` (``self.subrs`` was ``None``) and the whole
        # glyph was swallowed to a blank path. Pull the parent's subrs and
        # wrap each (raw bytes → ``T1CharString``) so the in-memory path
        # resolves ``callsubr`` exactly as the reload path does.
        if getattr(self._t1, "subrs", None) is None:
            self._t1.subrs = _font_subrs_as_charstrings(font, psCharStrings)

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
        pen = _make_path_pen(self._font)
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

    # ---------- private helpers (parity with upstream) ---------------------
    #
    # The methods below mirror the *private* Java helpers on upstream
    # ``Type1CharString`` (``render``, ``handleType1Command``,
    # ``setCurrentPoint``, ``callOtherSubr``, ``rmoveTo``, ``rlineTo``,
    # ``rrcurveTo``, ``closeCharString1Path``, ``seac``). Upstream
    # implements the Type 1 interpreter inline; we delegate the heavy
    # lifting to fontTools' ``T1OutlineExtractor`` (per the project's
    # library-first rule for font / charstring concerns). These shims
    # exist for two reasons:
    #
    #   1. They preserve the upstream API surface so subclasses /
    #      direct-port code from PDFBox can call the same names.
    #   2. They give parity tooling (``scripts/parity.py``) the snake_case
    #      method names it scans for.
    #
    # Each helper operates on a small ``_RenderContext`` (current point,
    # left side bearing, flex state, recording pen) so they can be called
    # individually by code that wants to drive the path step-by-step
    # without going through the full charstring interpreter — e.g. when
    # synthesising glyph outlines from a Java-style sequence list.

    def render(self) -> list[tuple[Any, ...]]:
        """Render the Type 1 char string sequence to a path.

        Mirrors upstream ``Type1CharString.render()`` (private). Drives
        the underlying fontTools ``T1CharString`` through the extended
        outline extractor and returns the recorded path. The path and
        advance width are cached so a follow-up ``get_path()`` /
        ``get_width()`` is a no-op.
        """
        if self._cached_path is not None:
            return list(self._cached_path)
        pen = _make_path_pen(self._font)
        try:
            width = _draw_with_extended_extractor(self._t1, pen)
        except Exception:  # noqa: BLE001
            self._cached_path = []
            self._cached_width = self._cached_width or 0.0
            return []
        self._cached_width = width
        self._cached_path = list(pen.commands)
        return list(self._cached_path)

    def handle_type1_command(
        self,
        ctx: _RenderContext,
        numbers: list[Any],
        command: Any,
    ) -> None:
        """Dispatch a single Type 1 charstring command against ``ctx``.

        Mirrors upstream ``Type1CharString.handleType1Command(List<Number>,
        CharStringCommand)`` (private). Operates on an explicit
        ``_RenderContext`` so callers can drive the interpreter step-by-
        step. Unknown / unsupported keywords clear the operand list and
        return silently — matching upstream's "warn and drop" policy for
        invalid charstrings.
        """
        op = _command_name(command)
        n = numbers
        if op == "rmoveto":
            if len(n) >= 2:
                if ctx.is_flex:
                    ctx.flex_points.append((float(n[0]), float(n[1])))
                else:
                    self.rmove_to(ctx, n[0], n[1])
        elif op == "vmoveto":
            if n:
                if ctx.is_flex:
                    ctx.flex_points.append((0.0, float(n[0])))
                else:
                    self.rmove_to(ctx, 0, n[0])
        elif op == "hmoveto":
            if n:
                if ctx.is_flex:
                    ctx.flex_points.append((float(n[0]), 0.0))
                else:
                    self.rmove_to(ctx, n[0], 0)
        elif op == "rlineto":
            if len(n) >= 2:
                self.rline_to(ctx, n[0], n[1])
        elif op == "hlineto":
            if n:
                self.rline_to(ctx, n[0], 0)
        elif op == "vlineto":
            if n:
                self.rline_to(ctx, 0, n[0])
        elif op == "rrcurveto":
            if len(n) >= 6:
                self.rrcurve_to(ctx, n[0], n[1], n[2], n[3], n[4], n[5])
        elif op == "closepath":
            self.close_char_string1_path(ctx)
        elif op == "sbw":
            if len(n) >= 3:
                ctx.left_side_bearing = (float(n[0]), float(n[1]))
                ctx.width = int(n[2])
                ctx.current = ctx.left_side_bearing
        elif op == "hsbw":
            if len(n) >= 2:
                ctx.left_side_bearing = (float(n[0]), 0.0)
                ctx.width = int(n[1])
                ctx.current = ctx.left_side_bearing
        elif op == "vhcurveto":
            if len(n) >= 4:
                self.rrcurve_to(ctx, 0, n[0], n[1], n[2], n[3], 0)
        elif op == "hvcurveto":
            if len(n) >= 4:
                self.rrcurve_to(ctx, n[0], 0, n[1], n[2], 0, n[3])
        elif op == "seac":
            if len(n) >= 5:
                self.seac(ctx, n[0], n[1], n[2], n[3], n[4])
        elif op == "setcurrentpoint":
            if len(n) >= 2:
                self.set_current_point(ctx, n[0], n[1])
        elif op == "callothersubr":
            if n:
                self.call_other_subr(ctx, int(n[0]))
        elif op == "div":
            if len(n) >= 2:
                b = float(n[-1])
                a = float(n[-2])
                n.pop()
                n.pop()
                n.append(a / b)
                return
        elif op in ("hstem", "vstem", "hstem3", "vstem3", "dotsection"):
            pass  # ignore hints
        elif op == "endchar":
            pass
        elif op in ("return", "callsubr"):
            pass  # invalid in flattened sequence — warn-and-drop
        n.clear()

    def set_current_point(self, ctx: _RenderContext, x: Any, y: Any) -> None:
        """Set the current absolute point without performing a moveto.

        Mirrors upstream ``Type1CharString.setCurrentPoint(Number,
        Number)`` (private). Used only with results from
        ``callothersubr``.
        """
        ctx.current = (float(x), float(y))

    def call_other_subr(self, ctx: _RenderContext, num: int) -> None:
        """Adobe Type 1 OtherSubrs dispatch (flex begin / end).

        Mirrors upstream ``Type1CharString.callOtherSubr(int)`` (private).
        ``num == 1`` begins a flex sequence; ``num == 0`` flushes the
        seven flex points as two ``rrcurveto`` segments. Other values
        are recorded as a no-op (upstream just warns).
        """
        if num == 0:
            ctx.is_flex = False
            if len(ctx.flex_points) < 7:
                ctx.flex_points.clear()
                return
            ref = ctx.flex_points[0]
            ref = (ctx.current[0] + ref[0], ctx.current[1] + ref[1])
            first = ctx.flex_points[1]
            first = (ref[0] + first[0], ref[1] + first[1])
            first = (first[0] - ctx.current[0], first[1] - ctx.current[1])
            p2 = ctx.flex_points[2]
            p3 = ctx.flex_points[3]
            self.rrcurve_to(ctx, first[0], first[1], p2[0], p2[1], p3[0], p3[1])
            p4 = ctx.flex_points[4]
            p5 = ctx.flex_points[5]
            p6 = ctx.flex_points[6]
            self.rrcurve_to(ctx, p4[0], p4[1], p5[0], p5[1], p6[0], p6[1])
            ctx.flex_points.clear()
        elif num == 1:
            ctx.is_flex = True

    def rmove_to(self, ctx: _RenderContext, dx: Any, dy: Any) -> None:
        """Relative moveto on ``ctx``. Mirrors upstream
        ``Type1CharString.rmoveTo(Number, Number)`` (private)."""
        x = ctx.current[0] + float(dx)
        y = ctx.current[1] + float(dy)
        ctx.path.append(("moveto", x, y))
        ctx.current = (x, y)

    def rline_to(self, ctx: _RenderContext, dx: Any, dy: Any) -> None:
        """Relative lineto on ``ctx``. Mirrors upstream
        ``Type1CharString.rlineTo(Number, Number)`` (private). When the
        path has no current point yet, falls back to a moveto — matching
        upstream's "warn-and-recover" policy."""
        x = ctx.current[0] + float(dx)
        y = ctx.current[1] + float(dy)
        if not _has_current_point(ctx):
            ctx.path.append(("moveto", x, y))
        else:
            ctx.path.append(("lineto", x, y))
        ctx.current = (x, y)

    def rrcurve_to(
        self,
        ctx: _RenderContext,
        dx1: Any,
        dy1: Any,
        dx2: Any,
        dy2: Any,
        dx3: Any,
        dy3: Any,
    ) -> None:
        """Relative curveto on ``ctx``. Mirrors upstream
        ``Type1CharString.rrcurveTo(Number*6)`` (private). When the path
        has no current point yet, falls back to a moveto at the final
        point — matching upstream's "warn-and-recover" policy."""
        x1 = ctx.current[0] + float(dx1)
        y1 = ctx.current[1] + float(dy1)
        x2 = x1 + float(dx2)
        y2 = y1 + float(dy2)
        x3 = x2 + float(dx3)
        y3 = y2 + float(dy3)
        if not _has_current_point(ctx):
            ctx.path.append(("moveto", x3, y3))
        else:
            ctx.path.append(("curveto", x1, y1, x2, y2, x3, y3))
        ctx.current = (x3, y3)

    def close_char_string1_path(self, ctx: _RenderContext) -> None:
        """Close the current sub-path on ``ctx``. Mirrors upstream
        ``Type1CharString.closeCharString1Path()`` (private). Always
        moves to the current point afterwards so the next segment starts
        cleanly — matching upstream's ``GeneralPath.moveTo(current)``."""
        if _has_current_point(ctx):
            ctx.path.append(("closepath",))
        ctx.path.append(("moveto", ctx.current[0], ctx.current[1]))

    def seac(
        self,
        ctx: _RenderContext,
        asb: Any,
        adx: Any,
        ady: Any,
        bchar: Any,
        achar: Any,
    ) -> None:
        """Standard-Encoding Accented Character composite.

        Mirrors upstream ``Type1CharString.seac(Number*5)`` (private).
        Looks up base + accent glyph names through the parent
        ``Type1CharStringReader`` (``self._font``), retrieves their paths
        and appends them to ``ctx.path`` with the accent translated by
        ``(lsb.x + adx - asb, lsb.y + ady)``. Missing parent / lookup
        failures degrade to no-ops (matching upstream's warn-and-skip).
        """
        try:
            from pypdfbox.fontbox.encoding.standard_encoding import (  # noqa: PLC0415
                StandardEncoding,
            )
            std = StandardEncoding.INSTANCE
        except Exception:  # noqa: BLE001
            std = None

        def _name(idx: Any) -> str | None:
            try:
                code = int(idx)
            except (TypeError, ValueError):
                return None
            if std is not None:
                try:
                    return std.get_name(code)
                except Exception:  # noqa: BLE001
                    return None
            return None

        base_name = _name(bchar)
        accent_name = _name(achar)
        font = self._font
        get = getattr(font, "get_type1_char_string", None)
        if get is None:
            return
        # Base character — appended with no transform.
        if base_name is not None:
            try:
                base_cs = get(base_name)
                ctx.path.extend(base_cs.get_path() or [])
            except Exception:  # noqa: BLE001
                pass
        # Accent character — translated by (lsb.x + adx - asb, lsb.y + ady).
        if accent_name is not None:
            try:
                accent_cs = get(accent_name)
                if accent_cs is self:
                    return  # PDFBOX-5339: avoid self-recursion.
                accent_path = accent_cs.get_path() or []
                tx = ctx.left_side_bearing[0] + float(adx) - float(asb)
                ty = ctx.left_side_bearing[1] + float(ady)
                for cmd in accent_path:
                    ctx.path.append(_translate_path_cmd(cmd, tx, ty))
            except Exception:  # noqa: BLE001
                pass

    def to_string(self) -> str:
        """Stringified Type 1 sequence — explicit alias of ``__str__``.

        Mirrors upstream ``Type1CharString.toString()``. Kept as an
        explicit method so direct-port callers can use the upstream name
        (Java's ``toString`` is conventionally invoked explicitly, not
        only via implicit conversion).
        """
        return self.__str__()

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
