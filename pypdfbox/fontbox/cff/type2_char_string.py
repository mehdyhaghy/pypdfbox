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
        # Mirrors upstream ``Type2CharString.pathCount`` — tracked by
        # ``markPath`` / ``closeCharString2Path`` during conversion.
        self._path_count: int = 0
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

    # ---------- Type 2 → Type 1 conversion (parity with upstream private API)

    def convert_type1_to_type2(self, sequence: list[Any]) -> None:
        """Convert a Type 2 char-string sequence into a Type 1 command
        sequence appended to the internal buffer.

        Mirrors upstream private ``Type2CharString.convertType1ToType2``
        (Type2CharString.java:75). Operands are numbers; operators are
        string mnemonics (matching ``fontTools.misc.psCharStrings``
        conventions) or ``CharStringCommand``-shaped tokens exposing a
        ``.name``. The actual outline interpretation is delegated to
        fontTools — this method is provided for upstream-shape parity
        callers and tests that want the Type 1 sequence buffer
        populated explicitly.

        PDFBOX-5987: collapse ``num denom DIV`` triplets into their
        evaluated quotient before the conversion walk. See
        Type2CharString.java:79–110.
        """
        self._path_count = 0
        # PDFBOX-5987: replace "num denom DIV" with the quotient.
        new_sequence: list[Any] = []
        for i, tok in enumerate(sequence):
            if (
                _token_name(tok) == "div"
                and i >= 2
                and isinstance(sequence[i - 2], (int, float))
                and isinstance(sequence[i - 1], (int, float))
                and len(new_sequence) >= 2
            ):
                num = float(sequence[i - 2])
                den = float(sequence[i - 1])
                if den != 0.0:
                    new_sequence.pop()
                    new_sequence.pop()
                    new_sequence.append(num / den)
                else:
                    new_sequence.append(tok)  # GIGO
            else:
                new_sequence.append(tok)

        numbers: list[Any] = []
        for obj in new_sequence:
            if _is_command_token(obj):
                results = self.convert_type2_command(numbers, obj)
                numbers = list(results)
            else:
                numbers.append(obj)

    def convert_type2_command(
        self, numbers: list[Any], command: Any
    ) -> list[Any]:
        """Dispatch a single Type 2 operator. Mirrors upstream
        ``convertType2Command`` (Type2CharString.java:127)."""
        kw = _token_name(command)
        if kw in ("hstem", "hstemhm", "vstem", "vstemhm", "hintmask", "cntrmask"):
            numbers = self.clear_stack(numbers, len(numbers) % 2 != 0)
            self.expand_stem_hints(numbers, kw in ("hstem", "hstemhm"))
        elif kw in ("hmoveto", "vmoveto"):
            numbers = self.clear_stack(numbers, len(numbers) > 1)
            self.mark_path()
            self.add_command(numbers, command)
        elif kw == "rlineto":
            self.add_command_list(self.split(numbers, 2), command)
        elif kw in ("hlineto", "vlineto"):
            self.add_alternating_line(list(numbers), kw == "hlineto")
        elif kw == "rrcurveto":
            self.add_command_list(self.split(numbers, 6), command)
        elif kw == "endchar":
            numbers = self.clear_stack(
                numbers, len(numbers) == 5 or len(numbers) == 1
            )
            self.close_char_string2_path()
            if len(numbers) == 4:
                # Deprecated "seac" operator (CharStringCommand 12 6).
                seac_args = [0, *numbers]
                self.add_command(seac_args, "seac")
            else:
                self.add_command(numbers, command)
        elif kw == "rmoveto":
            numbers = self.clear_stack(numbers, len(numbers) > 2)
            self.mark_path()
            self.add_command(numbers, command)
        elif kw in ("hvcurveto", "vhcurveto"):
            self.add_alternating_curve(list(numbers), kw == "hvcurveto")
        elif kw == "hflex":
            if len(numbers) >= 7:
                first = [numbers[0], 0, numbers[1], numbers[2], numbers[3], 0]
                second = [
                    numbers[4],
                    0,
                    numbers[5],
                    -float(numbers[2]),
                    numbers[6],
                    0,
                ]
                self.add_command_list([first, second], "rrcurveto")
        elif kw == "flex":
            if len(numbers) >= 12:
                first = list(numbers[0:6])
                second = list(numbers[6:12])
                self.add_command_list([first, second], "rrcurveto")
        elif kw == "hflex1":
            if len(numbers) >= 9:
                first = [
                    numbers[0],
                    numbers[1],
                    numbers[2],
                    numbers[3],
                    numbers[4],
                    0,
                ]
                second = [
                    numbers[5],
                    0,
                    numbers[6],
                    numbers[7],
                    numbers[8],
                    0,
                ]
                self.add_command_list([first, second], "rrcurveto")
        elif kw == "flex1":
            if len(numbers) >= 11:
                dx = 0
                dy = 0
                for i in range(5):
                    dx += int(numbers[i * 2])
                    dy += int(numbers[i * 2 + 1])
                first = list(numbers[0:6])
                dx_is_bigger = abs(dx) > abs(dy)
                second = [
                    numbers[6],
                    numbers[7],
                    numbers[8],
                    numbers[9],
                    numbers[10] if dx_is_bigger else -dx,
                    -dy if dx_is_bigger else numbers[10],
                ]
                self.add_command_list([first, second], "rrcurveto")
        elif kw == "rcurveline":
            if len(numbers) >= 2:
                self.add_command_list(self.split(numbers[:-2], 6), "rrcurveto")
                self.add_command(list(numbers[-2:]), "rlineto")
        elif kw == "rlinecurve":
            if len(numbers) >= 6:
                self.add_command_list(self.split(numbers[:-6], 2), "rlineto")
                self.add_command(list(numbers[-6:]), "rrcurveto")
        elif kw in ("hhcurveto", "vvcurveto"):
            self.add_curve(list(numbers), kw == "hhcurveto")
        else:
            self.add_command(numbers, command)
        return []

    def clear_stack(self, numbers: list[Any], flag: bool) -> list[Any]:
        """Mirrors upstream ``clearStack`` (Type2CharString.java:264).

        On the *first* operator, drain any leading width operand into a
        synthetic ``hsbw`` command; otherwise pass the stack through.
        """
        if self.is_sequence_empty():
            if flag and numbers:
                self.add_command(
                    [0, float(numbers[0]) + self._nominal_width_x], "hsbw"
                )
                return list(numbers[1:])
            self.add_command([0, self._default_width_x], "hsbw")
        return list(numbers)

    def expand_stem_hints(self, numbers: list[Any], horizontal: bool) -> None:
        """Mirrors upstream ``expandStemHints`` (Type2CharString.java:286).

        Upstream ships this as a ``// TODO`` no-op — we match that
        behaviour exactly. The unused parameters carry parity intent.
        """
        del numbers, horizontal

    def mark_path(self) -> None:
        """Mirrors upstream ``markPath`` (Type2CharString.java:291)."""
        if self._path_count > 0:
            self.close_char_string2_path()
        self._path_count += 1

    def close_char_string2_path(self) -> None:
        """Mirrors upstream ``closeCharString2Path``
        (Type2CharString.java:300). Emits a ``closepath`` only when the
        last command is not already a ``closepath``."""
        last = self.get_last_sequence_entry() if self._path_count > 0 else None
        if last is not None and _token_name(last) != "closepath":
            self.add_command([], "closepath")

    def add_alternating_line(
        self, numbers: list[Any], horizontal: bool
    ) -> None:
        """Mirrors upstream ``addAlternatingLine``
        (Type2CharString.java:310)."""
        while numbers:
            self.add_command(
                [numbers[0]], "hlineto" if horizontal else "vlineto"
            )
            numbers = numbers[1:]
            horizontal = not horizontal

    def add_alternating_curve(
        self, numbers: list[Any], horizontal: bool
    ) -> None:
        """Mirrors upstream ``addAlternatingCurve``
        (Type2CharString.java:321)."""
        while len(numbers) >= 4:
            last = len(numbers) == 5
            if horizontal:
                self.add_command(
                    [
                        numbers[0],
                        0,
                        numbers[1],
                        numbers[2],
                        numbers[4] if last else 0,
                        numbers[3],
                    ],
                    "rrcurveto",
                )
            else:
                self.add_command(
                    [
                        0,
                        numbers[0],
                        numbers[1],
                        numbers[2],
                        numbers[3],
                        numbers[4] if last else 0,
                    ],
                    "rrcurveto",
                )
            numbers = numbers[5 if last else 4 :]
            horizontal = not horizontal

    def add_curve(self, numbers: list[Any], horizontal: bool) -> None:
        """Mirrors upstream ``addCurve`` (Type2CharString.java:345)."""
        while len(numbers) >= 4:
            first = len(numbers) % 4 == 1
            if horizontal:
                self.add_command(
                    [
                        numbers[1 if first else 0],
                        numbers[0] if first else 0,
                        numbers[2 if first else 1],
                        numbers[3 if first else 2],
                        numbers[4 if first else 3],
                        0,
                    ],
                    "rrcurveto",
                )
            else:
                self.add_command(
                    [
                        numbers[0] if first else 0,
                        numbers[1 if first else 0],
                        numbers[2 if first else 1],
                        numbers[3 if first else 2],
                        0,
                        numbers[4 if first else 3],
                    ],
                    "rrcurveto",
                )
            numbers = numbers[5 if first else 4 :]

    def add_command_list(
        self, numbers: list[list[Any]], command: Any
    ) -> None:
        """Mirrors upstream ``addCommandList``
        (Type2CharString.java:370)."""
        for ns in numbers:
            self.add_command(list(ns), command)

    @staticmethod
    def split(items: list[Any], size: int) -> list[list[Any]]:
        """Mirrors upstream static ``split(List<E> list, int size)``
        (Type2CharString.java:375). Slices ``items`` into consecutive
        chunks of ``size``; trailing partial chunks are dropped (matches
        upstream which iterates ``list.size() / size`` whole chunks)."""
        return _split(items, size)

    # ---------- back-compat aliases (underscored names from wave 397) -------
    # Wave 397 originally introduced these helpers as private (``_foo``).
    # Wave 1269 promotes them to public ``foo`` to match upstream Java
    # method names; the underscored aliases stay so any callers / tests
    # that pinned the old name keep working.

    _convert_type2_command = convert_type2_command
    _clear_stack = clear_stack
    _expand_stem_hints = expand_stem_hints
    _mark_path = mark_path
    _close_char_string2_path = close_char_string2_path
    _add_alternating_line = add_alternating_line
    _add_alternating_curve = add_alternating_curve
    _add_curve = add_curve
    _add_command_list = add_command_list

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


def _token_name(tok: Any) -> str | None:
    """Return the operator mnemonic for a token, or ``None`` if it is a
    plain operand. Strings pass through unchanged; objects exposing a
    ``.name`` attribute (CharStringCommand-shaped) yield that name;
    numbers and unknown shapes return ``None``."""
    if isinstance(tok, str):
        return tok
    if isinstance(tok, (int, float)):
        return None
    name = getattr(tok, "name", None)
    if isinstance(name, str):
        return name
    return None


def _is_command_token(tok: Any) -> bool:
    """``True`` when ``tok`` represents a charstring operator rather
    than an operand. Mirrors the ``obj instanceof CharStringCommand``
    guard upstream uses inside ``convertType1ToType2``."""
    return _token_name(tok) is not None


def _split(items: list[Any], size: int) -> list[list[Any]]:
    """Mirrors upstream static ``split(List<E> list, int size)``
    (Type2CharString.java:375). Slices ``items`` into consecutive
    chunks of ``size``; trailing partial chunks are dropped (matches
    upstream which iterates ``list.size() / size`` whole chunks)."""
    if size <= 0:
        return []
    n = len(items) // size
    return [list(items[i * size : (i + 1) * size]) for i in range(n)]


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
