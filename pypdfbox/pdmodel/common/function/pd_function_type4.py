from __future__ import annotations

import math
import re
import struct
from collections.abc import Callable

from pypdfbox.cos import COSBase, COSStream

from .pd_function import PDFunction

# Tokens emitted by ``_classify`` (and held in a parsed instruction list) are:
#   * ``int``                    — an integer literal (PostScript ``Integer``)
#   * ``float``                  — a real literal (PostScript ``Float``)
#   * ``bool``                   — a ``true`` / ``false`` literal
#   * ``str``                    — an operator name
#   * ``list[Token]`` (sub-seq)  — a ``{...}`` instruction sub-sequence (operand
#                                  to ``if`` / ``ifelse``)
#
# Integer-vs-real tagging is load-bearing, not cosmetic: upstream's
# ``ExecutionContext`` keeps an ``Object`` stack of boxed ``Integer`` / ``Float``
# / ``Boolean`` and the strict integer operators (``idiv``, ``mod``, ``bitshift``,
# ``and`` / ``or`` / ``xor``, ``not``) cast ``(Integer)`` and throw
# ``ClassCastException`` on a ``Float`` operand, while the arithmetic operators
# (``add`` / ``sub`` / ``mul`` / ``abs`` / ``neg`` / ``ceiling`` / ``floor`` /
# ``round`` / ``truncate``) branch on the tag to decide whether the result is an
# Integer or a Float. Python's native ``int`` / ``float`` types are the tag:
# integer literals/results push ``int``, reals push ``float``. ``bool`` is a
# subclass of ``int`` in Python, so every type check below tests ``bool`` first.
Instruction = list[object]
Stack = list[object]
Operator = Callable[[Stack], None]


class PDFunctionType4(PDFunction):
    """
    Type 4 (PostScript calculator) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType4``.

    The function body is a PostScript-calculator expression stored in the
    underlying ``COSStream``. ``eval()`` parses the stream body into a nested
    instruction sequence (each ``{...}`` block becomes a sub-list) and runs
    a small stack machine over the operator subset enumerated in PDF 32000-1
    §7.10.5.

    The stack threads the PostScript Integer-vs-Real type tag faithfully
    (Python ``int`` for integer literals/results, ``float`` for reals, ``bool``
    for booleans) so the strict integer operators reject Float operands exactly
    as upstream's ``(Integer)`` casts do. Stack underflow, type mismatch
    (upstream ``ClassCastException``), unknown operators, and other Type-4-illegal
    constructs all surface as ``OSError`` to mirror upstream's runtime faults
    (which ``PDFunctionType4.eval`` would propagate). ``def``, ``forall``,
    ``for``, dictionaries, and other operators not allowed in Type 4 are
    intentionally rejected.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)
        # Parsed instruction sequence cache. ``None`` is the "not yet parsed"
        # sentinel so a legitimately-empty program (``[]``) is still a hit
        # after the first parse. Shading renderers call ``eval`` millions of
        # times against the same wrapper; tokenising + parsing the body each
        # call is the dominant cost. Body bytes don't mutate after the
        # COSStream is parsed, so a once-parsed cache is safe for the
        # lifetime of the wrapper. Callers that mutate the body via
        # ``pd_stream.set_data(...)`` can invalidate via
        # ``clear_instruction_cache()``.
        self._instruction_cache: Instruction | None = None

    def get_function_type(self) -> int:
        return 4

    # ---------- evaluation ----------

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Evaluate the PostScript-calculator program on ``input`` per
        PDF 32000-1 §7.10.5.

        ``input`` is clipped to ``/Domain`` first, pushed onto an initially
        empty stack (first input on bottom), the program is executed, and
        the remaining stack is returned (bottom-up) clipped to ``/Range``.

        When ``/Range`` is present and the program leaves fewer values on
        the stack than ``getNumberOfOutputParameters()`` declares, this
        raises ``OSError`` — mirrors upstream PDFBox which raises
        ``IllegalStateException`` for under-supply.
        """
        clipped = self._clip_input_unnormalised(input)

        sequence = self.get_instructions()

        stack: Stack = list(clipped)
        _execute(sequence, stack)

        # Upstream parity: when /Range declares N output dimensions, the
        # program must leave at least N values on the stack. Under-supply
        # is a malformed function and bubbles up as OSError (mirrors
        # IllegalStateException in PDFunctionType4.eval). When /Range is
        # absent (e.g. inline shading helpers) we skip the check and
        # return the whole stack — clip_output is a no-op in that case.
        declared = self.get_number_of_output_parameters()
        if declared > 0:
            if len(stack) < declared:
                raise OSError(
                    f"type 4 function returned {len(stack)} values "
                    f"but /Range declares {declared}"
                )
            # Upstream pops the TOP N values off the stack into the output
            # (PDFunctionType4.eval fills output[N-1..0] via popReal), so any
            # surplus values left BELOW the top N — e.g. the original inputs a
            # pure-stack program never consumed — are discarded. Mirror that by
            # keeping only the last N stack entries before clipping. The strict
            # popReal cast (``_pop_output_value``) raises on a Boolean left in a
            # declared /Range slot, exactly like upstream's
            # ``(Number) stack.pop()`` ClassCastException.
            stack = stack[-declared:]
            result = [_pop_output_value(v) for v in stack]
        else:
            # /Range absent: pypdfbox's lenient whole-stack return. Booleans are
            # coerced to 1.0 / 0.0 (Type4Tester-style helpers depend on this);
            # upstream returns an empty output here instead, but the lenient
            # whole-stack behaviour is a long-standing pypdfbox convenience.
            result = [_to_output_float(v) for v in stack]

        return self._clip_output_unnormalised(result)

    # ---------- clipping (non-normalising, upstream-faithful) ----------

    @staticmethod
    def _clip_scalar(x: float, range_min: float, range_max: float) -> float:
        """Non-normalising scalar clamp — direct port of upstream
        ``PDFunction.clipToRange(float, float, float)``.

        ``if x < range_min -> range_min``; ``if x > range_max -> range_max``;
        else ``x``. Crucially this does **not** swap a reversed ``(min, max)``
        pair the way the base :meth:`PDFunction.clip_input` /
        :meth:`PDFunction.clip_output` do. Java's Type 4 ``eval`` clips both
        the input and the output through this exact non-normalising helper
        (``PDFunctionType4.eval`` calls the base ``clipToRange(float[])`` which
        loops over the declared parameter pairs calling the scalar clamp), so a
        reversed ``/Domain`` or ``/Range`` produces the same clamped value as
        upstream rather than a silently-normalised interval. Mirrors the same
        override already present on :class:`PDFunctionType3`."""
        if x < range_min:
            return range_min
        if x > range_max:
            return range_max
        return x

    def _clip_input_unnormalised(self, values: list[float]) -> list[float]:
        """Clip each input to its ``/Domain`` pair with the non-normalising
        scalar clamp. Excess inputs (beyond the declared dimension count) pass
        through unchanged, matching the base ``clip_input`` arity handling."""
        ranges = self.get_ranges_for_inputs()
        out: list[float] = []
        for i, v in enumerate(values):
            if i < len(ranges):
                lo, hi = ranges[i]
                out.append(self._clip_scalar(v, lo, hi))
            else:
                out.append(v)
        return out

    def _clip_output_unnormalised(self, values: list[float]) -> list[float]:
        """Clip each output to its ``/Range`` pair with the non-normalising
        scalar clamp. Returns the values unchanged when ``/Range`` is absent
        (the lenient whole-stack mode)."""
        ranges = self.get_ranges_for_outputs()
        if not ranges:
            return list(values)
        out: list[float] = []
        for i, v in enumerate(values):
            if i < len(ranges):
                lo, hi = ranges[i]
                out.append(self._clip_scalar(v, lo, hi))
            else:
                out.append(v)
        return out

    def get_instructions(self) -> Instruction:
        """Return the cached parsed instruction sequence, parsing the
        underlying stream body on first access.

        The returned list is the same list cached internally — callers must
        not mutate it. Provided as a typed accessor mirroring the upstream
        ``InstructionSequence`` surface (PDFBox holds the parsed program in
        a final field on the wrapper). Useful for tools that want to
        inspect / dump a Type 4 program without driving ``eval``.
        """
        sequence = self._instruction_cache
        if sequence is None:
            sequence = _parse(self._read_body())
            self._instruction_cache = sequence
        return sequence

    def clear_instruction_cache(self) -> None:
        """Drop the cached parsed instruction sequence so the next ``eval``
        re-tokenises and re-parses the underlying stream body.

        Not present in upstream PDFBox (which has no such cache to begin
        with). Provided as a defensive escape hatch for callers that mutate
        the underlying ``COSStream`` body via ``pd_stream.set_data(...)``
        after the first ``eval``.
        """
        self._instruction_cache = None

    # ---------- helpers ----------

    def _read_body(self) -> str:
        stream = self.get_pd_stream()
        if stream is None:
            return ""
        cos_stream = stream.get_cos_object()
        if not isinstance(cos_stream, COSStream):
            return ""
        with cos_stream.create_input_stream() as src:
            raw = src.read()
        # PostScript bodies are 7-bit ASCII; tolerate a stray Latin-1 byte.
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")


# ---------- tokeniser / parser ----------


def _tokenize(body: str) -> list[str]:
    """Whitespace-split the body, splitting ``{`` and ``}`` into their own
    tokens regardless of whitespace adjacency and skipping PostScript
    ``%`` comments through end-of-line."""
    out: list[str] = []
    buf: list[str] = []
    in_comment = False

    def flush() -> None:
        if buf:
            out.append("".join(buf))
            buf.clear()

    for ch in body:
        if in_comment:
            if ch in "\r\n":
                in_comment = False
            continue
        if ch == "%":
            flush()
            in_comment = True
        elif ch in "{}":
            flush()
            out.append(ch)
        elif ch.isspace():
            flush()
        else:
            buf.append(ch)
    flush()
    return out


def _parse(body: str) -> Instruction:
    """Parse ``body`` into a nested instruction sequence, mirroring upstream
    ``InstructionSequenceBuilder``'s lenient stack semantics.

    Upstream PDFBox builds the program with a streaming SAX-style handler
    (``InstructionSequenceBuilder``) that maintains a ``mainSequence`` and a
    stack of open procedures: ``{`` adds a fresh sub-sequence to the current
    sequence and pushes it; ``}`` simply pops the stack *without any balance
    check*. Consequently a missing closing brace, a stray closing brace,
    an absent outer wrapper, and tokens trailing the outer ``}`` are all
    tolerated — the structure already accumulated into ``mainSequence``
    survives, and the executor (see :func:`_execute`) auto-runs a trailing
    procedure left on top of the stack. pypdfbox previously used a strict
    recursive-descent parser that rejected every one of these malformed
    shapes; wave 1509 aligned this path with the upstream lenience contract
    (differential-pinned by ``FunctionEvalFuzzProbe``).

    An empty body parses as the empty sequence.
    """
    tokens = _tokenize(body)
    if not tokens:
        return []

    # ``main`` is upstream's ``mainSequence``; ``stack`` is its ``seqStack``,
    # which always has at least the main sequence at the bottom. ``}`` pops
    # the stack but never below the main sequence (Java's Stack.pop would
    # throw EmptyStackException, but in practice the extra-close cases all
    # leave at least the main sequence — guard against underflow so a stray
    # ``}`` degrades to lenient instead of erroring, matching the observed
    # Java behaviour where excess closes simply unwind to the main level).
    main: Instruction = []
    stack: list[Instruction] = [main]
    for tok in tokens:
        if tok == "{":
            child: Instruction = []
            stack[-1].append(child)
            stack.append(child)
        elif tok == "}":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].append(_classify(tok))
    return main


# Upstream ``InstructionSequenceBuilder`` classifies a token with two regexes,
# in this order: ``[+-]?\d+`` => Integer, then ``-?\d*\.\d*([Ee]-?\d+)?`` =>
# Real. The integer regex is tried FIRST, so ``42`` is an Integer while ``42.0``
# (matches the real regex, not the integer one) is a Float. This ordering is the
# whole point of the type discipline: ``8 2 idiv`` works but ``8.0 2 idiv``
# raises ClassCastException (verified against the live jar). We reproduce the
# exact patterns so a literal lands on the same tag Java would assign.
_INTEGER_RE = re.compile(r"[+-]?\d+")
_REAL_RE = re.compile(r"-?\d*\.\d*([Ee]-?\d+)?")


def _classify(tok: str) -> int | float | bool | str:
    """Tag a raw token as an integer literal, real literal, boolean literal,
    or operator name, mirroring upstream ``InstructionSequenceBuilder.token``.

    Note: upstream does NOT special-case ``true`` / ``false`` in the builder —
    they fall through to ``addName`` and are handled by the ``True`` / ``False``
    operators at execution time. We classify them to Python ``bool`` here as an
    equivalent shortcut (the executor pushes a bare ``bool`` token directly), so
    the observable stack contents are identical.

    Hex / radix-prefixed numbers (PostScript's ``16#FF`` form) match neither
    regex (upstream leaves them as a TODO) and fall through to the operator
    path — the executor raises on the resulting unknown name."""
    if tok == "true":
        return True
    if tok == "false":
        return False
    if _INTEGER_RE.fullmatch(tok):
        return int(tok)
    if _REAL_RE.fullmatch(tok):
        return float(tok)
    return tok


# ---------- stack machine ----------


def _pop(stack: Stack) -> object:
    if not stack:
        raise OSError("stack underflow")
    return stack.pop()


def _pop_number(stack: Stack) -> int | float:
    """Pop a number preserving its int/float tag — upstream ``popNumber()``
    (``(Number) stack.pop()``). A ``Boolean`` on top raises (Java's cast to
    ``Number`` throws ClassCastException); we surface it as ``OSError``."""
    v = _pop(stack)
    if isinstance(v, bool):
        raise OSError("type mismatch: expected number, got boolean")
    if not isinstance(v, (int, float)):
        raise OSError(f"type mismatch: expected number, got {type(v).__name__}")
    return v


def _pop_real(stack: Stack) -> float:
    """Pop a number and return it as a float — upstream ``popReal()``
    (``((Number) stack.pop()).floatValue()``). The tag is discarded; both
    Integer and Float operands are accepted."""
    return float(_pop_number(stack))


def _pop_int_strict(stack: Stack) -> int:
    """Pop a strictly-Integer value — upstream ``popInt()`` (``(Integer)
    stack.pop()``). A Float (even an int-valued one like ``8.0`` or a ``div``
    result) raises ClassCastException in Java; we surface that as ``OSError``.
    Used by the strict integer operators ``idiv`` / ``mod`` / ``bitshift``."""
    v = _pop(stack)
    if isinstance(v, bool) or not isinstance(v, int):
        got = "float" if isinstance(v, float) else type(v).__name__
        raise OSError(f"type mismatch: expected integer (Integer cast), got {got}")
    return v


def _pop_int_value(stack: Stack) -> int:
    """Pop a number and truncate to int — upstream's stack operators use
    ``((Number) stack.pop()).intValue()`` for ``copy`` / ``index`` / ``roll``
    counts, which leniently accepts a Float and truncates toward zero. A
    Boolean still raises (cast to Number fails)."""
    return math.trunc(_pop_number(stack))


def _to_output_float(value: object) -> float:
    # When /Range is absent (pypdfbox's lenient whole-stack-return mode, used by
    # Type4Tester-style helpers and inline shading callers) a surviving Boolean
    # is coerced to 1.0 / 0.0. The strict /Range path raises on a Boolean
    # instead (see ``_pop_output_value`` / PDFunctionType4.eval) — that is the
    # branch that mirrors upstream's ``(Number) popReal`` cast.
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    raise OSError(f"type mismatch: expected numeric output, got {type(value).__name__}")


def _pop_output_value(value: object) -> float:
    # Strict /Range output path: upstream PDFunctionType4.eval fills the output
    # array with ``((Number) stack.pop()).floatValue()`` (popReal). A Boolean
    # left in the declared /Range slots is cast to Number and throws
    # ClassCastException, which we surface as OSError. So ``{ pop true }`` or
    # ``{ pop 5 5 eq }`` over a non-empty /Range is a runtime fault, NOT a
    # 1.0/0.0 coercion — verified against the jar. A Boolean is legal only as an
    # intermediate consumed by if/ifelse/and/or/xor/not before the program ends.
    if isinstance(value, bool):
        raise OSError("type mismatch: boolean left in function output (Number cast)")
    if isinstance(value, (int, float)):
        return float(value)
    raise OSError(f"type mismatch: expected numeric output, got {type(value).__name__}")


def _execute(sequence: Instruction, stack: Stack) -> None:
    for token in sequence:
        if isinstance(token, list):
            # A ``{ ... }`` substack is a literal — push for ``if``/``ifelse``
            # to consume. Bare execution would consume the whole frame.
            stack.append(token)
            continue
        if isinstance(token, bool):
            stack.append(token)
            continue
        if isinstance(token, (int, float)):
            # Preserve the int/float tag (upstream pushes the boxed Integer or
            # Float literal verbatim). Do NOT coerce to float here — that is the
            # exact loss of the type tag this rewrite restores.
            stack.append(token)
            continue
        if not isinstance(token, str):
            raise OSError(f"unsupported PostScript token: {token!r}")
        # Operator name.
        op = _OPERATORS.get(token)
        if op is None:
            raise OSError(f"unsupported PostScript operator: {token!r}")
        op(stack)

    # Upstream ``InstructionSequence.execute`` finishes by auto-running any
    # procedure left on top of the stack (PDFunctionType4's top-level program
    # is itself a procedure pushed by the outer ``{``; this is what runs it).
    # A ``while`` loop drains a chain of trailing procs, mirroring upstream.
    while stack and isinstance(stack[-1], list):
        nested = stack.pop()
        _execute(nested, stack)


# ---------- operators ----------
#
# Each handler pops operands from ``stack`` and pushes results in the order
# specified by PDF 32000-1 §7.10.5 / PostScript reference. Unsupported types
# (def, forall, for, dictionaries) are intentionally absent — they raise
# "unsupported operator" via the dispatcher.


# Java ``int`` is a 32-bit two's-complement type. The arithmetic operators that
# preserve the Integer tag (add/sub/mul) compute in ``long`` and only stay
# Integer when the result fits in the 32-bit range, otherwise overflow to Float.
_INT_MIN = -(2**31)
_INT_MAX = 2**31 - 1


def _wrap_int32(value: int) -> int:
    """Reduce ``value`` to the signed 32-bit two's-complement range, mirroring
    how a Java ``int`` truncates an out-of-range result. Java's ``<<`` / ``>>``
    operate on 32-bit ints, so ``1 << 31`` wraps to ``Integer.MIN_VALUE`` and
    ``65536 << 16`` wraps to ``0`` rather than growing without bound the way a
    Python ``int`` would."""
    return ((value & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000


def _is_int(value: object) -> bool:
    """True for a PostScript Integer tag (Python ``int`` but not ``bool``)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    """True for a PostScript number (Integer or Real) — excludes Boolean.
    Mirrors a Java ``instanceof Number`` test, which Boolean fails."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _both_int(a: object, b: object) -> bool:
    # bool is a subclass of int — exclude it (a Boolean is never an Integer here;
    # arithmetic on a Boolean already raised in _pop_number).
    return (
        isinstance(a, int)
        and not isinstance(a, bool)
        and isinstance(b, int)
        and not isinstance(b, bool)
    )


def _op_add(s: Stack) -> None:
    b = _pop_number(s)
    a = _pop_number(s)
    if _both_int(a, b):
        total = a + b
        s.append(total if _INT_MIN <= total <= _INT_MAX else float(total))
    else:
        s.append(float(a) + float(b))


def _op_sub(s: Stack) -> None:
    b = _pop_number(s)
    a = _pop_number(s)
    if _both_int(a, b):
        result = a - b
        s.append(result if _INT_MIN <= result <= _INT_MAX else float(result))
    else:
        s.append(float(a) - float(b))


def _op_mul(s: Stack) -> None:
    b = _pop_number(s)
    a = _pop_number(s)
    if _both_int(a, b):
        result = a * b
        s.append(result if _INT_MIN <= result <= _INT_MAX else float(result))
    else:
        s.append(float(a) * float(b))


def _op_div(s: Stack) -> None:
    # Upstream ``Div`` always casts both operands to float and pushes a Float,
    # regardless of operand tags — ``6 2 div`` => 3.0 (Float). So idiv after a
    # div always sees a Float and raises (the strict-xfail case).
    b = float(_pop_number(s))
    a = float(_pop_number(s))
    # Upstream ArithmeticOperators$Div is plain ``num1.floatValue() /
    # num2.floatValue()`` — IEEE-754 float division, so a zero divisor yields
    # +/-Infinity (or NaN for 0/0), which the subsequent /Range clip clamps to
    # the range bound. Mirror that instead of raising: a Type 4 program that
    # divides by zero must produce the same clamped output as Java, not an
    # exception (verified against the jar: ``{ 1 0 div }`` over /Range [-1000,
    # 1000] returns 1000.0).
    if b == 0.0:
        if a == 0.0:
            s.append(math.nan)
        else:
            s.append(math.inf if a > 0.0 else -math.inf)
        return
    s.append(a / b)


def _op_idiv(s: Stack) -> None:
    # Strict ``(Integer)`` pops — a Float operand raises (matches the jar).
    b = _pop_int_strict(s)
    a = _pop_int_strict(s)
    if b == 0:
        raise OSError("integer division by zero")
    # Java integer division truncates toward zero (not Python floor); the
    # result keeps the Integer tag.
    q = abs(a) // abs(b)
    if (a < 0) ^ (b < 0):
        q = -q
    s.append(q)


def _op_mod(s: Stack) -> None:
    b = _pop_int_strict(s)
    a = _pop_int_strict(s)
    if b == 0:
        raise OSError("mod by zero")
    # Java ``%`` — sign of result follows the dividend; result stays Integer.
    r = abs(a) % abs(b)
    if a < 0:
        r = -r
    s.append(r)


def _op_neg(s: Stack) -> None:
    a = _pop_number(s)
    if _is_int(a):
        # Java guards Integer.MIN_VALUE (negation overflows int) by promoting to
        # Float; every other int stays Integer.
        s.append(float(-a) if a == _INT_MIN else -a)
    else:
        s.append(-float(a))


def _op_abs(s: Stack) -> None:
    a = _pop_number(s)
    # Integer in => Integer out; Float in => Float out (upstream branches on tag).
    # Upstream ArithmeticOperators$Abs on an Integer is ``Math.abs(int)``, which
    # leaves ``Integer.MIN_VALUE`` NEGATIVE (its magnitude overflows a 32-bit
    # int, so ``Math.abs`` returns it unchanged). Mirror that single overflow
    # corner; every other int negates normally.
    if _is_int(a):
        s.append(a if a == _INT_MIN else abs(a))
    else:
        s.append(abs(float(a)))


def _op_ceiling(s: Stack) -> None:
    a = _pop_number(s)
    # Integer is returned unchanged (already whole); Float is ceil'd to a Float.
    s.append(a if _is_int(a) else float(math.ceil(a)))


def _op_floor(s: Stack) -> None:
    a = _pop_number(s)
    s.append(a if _is_int(a) else float(math.floor(a)))


def _op_round(s: Stack) -> None:
    a = _pop_number(s)
    if _is_int(a):
        s.append(a)
        return
    # Float branch: Java ``Math.round`` is ``floor(x + 0.5)`` — ties to +inf.
    s.append(float(math.floor(a + 0.5)))


def _op_truncate(s: Stack) -> None:
    a = _pop_number(s)
    s.append(a if _is_int(a) else float(math.trunc(a)))


def _op_sqrt(s: Stack) -> None:
    a = _pop_real(s)
    if a < 0:
        raise OSError("sqrt of negative number")
    s.append(math.sqrt(a))


def _op_sin(s: Stack) -> None:
    a = _pop_real(s)  # degrees per PostScript
    s.append(math.sin(math.radians(a)))


def _op_cos(s: Stack) -> None:
    a = _pop_real(s)
    s.append(math.cos(math.radians(a)))


def _op_atan(s: Stack) -> None:
    den = _pop_real(s)
    num = _pop_real(s)
    # PostScript atan(num, den) returns degrees in [0, 360).
    deg = math.degrees(math.atan2(num, den))
    if deg < 0:
        deg += 360.0
    s.append(deg)


def _op_exp(s: Stack) -> None:
    exponent = float(_pop_number(s))
    base = float(_pop_number(s))
    # Upstream ArithmeticOperators$Exp == ``(float) Math.pow(base, exp)``.
    # Java's Math.pow returns NaN for a negative base with a non-integer
    # exponent (and for other indeterminate forms) rather than throwing;
    # Python's math.pow raises ValueError on the same inputs. Catch and emit
    # NaN so the /Range clip handles it exactly as Java does (jar: ``{ -2 0.5
    # exp }`` returns NaN).
    try:
        s.append(math.pow(base, exponent))
    except ValueError:
        s.append(math.nan)


def _op_ln(s: Stack) -> None:
    a = float(_pop_number(s))
    # Upstream ArithmeticOperators$Ln is plain ``(float) Math.log(...)`` with no
    # domain guard: Math.log(0) == -Infinity and Math.log(negative) == NaN. The
    # subsequent /Range clip turns -Infinity into the range min and passes NaN
    # through, so mirror Java rather than raising (jar: ``{ 0 ln }`` clamps to
    # the range min).
    if a == 0.0:
        s.append(-math.inf)
    elif a < 0.0:
        s.append(math.nan)
    else:
        s.append(math.log(a))


def _op_log(s: Stack) -> None:
    a = float(_pop_number(s))
    # Mirrors upstream ArithmeticOperators$Log == ``(float) Math.log10(...)``;
    # same -Infinity / NaN edge behaviour as ``ln`` (see above).
    if a == 0.0:
        s.append(-math.inf)
    elif a < 0.0:
        s.append(math.nan)
    else:
        s.append(math.log10(a))


def _op_cvi(s: Stack) -> None:
    # Upstream ``Cvi`` == ``num.intValue()`` — truncates toward zero and pushes
    # an Integer. Crucially this RE-tags a Float as an Integer, so ``7.9 cvi 2
    # idiv`` works where ``7.9 2 idiv`` would raise.
    a = _pop_number(s)
    s.append(math.trunc(a))


def _op_cvr(s: Stack) -> None:
    # Upstream ``Cvr`` == ``num.floatValue()`` — pushes a Float (re-tags an
    # Integer as a Real).
    a = _pop_number(s)
    s.append(float(a))


# ---------- stack ----------


def _op_dup(s: Stack) -> None:
    if not s:
        raise OSError("stack underflow")
    s.append(s[-1])


def _op_exch(s: Stack) -> None:
    b = _pop(s)
    a = _pop(s)
    s.append(b)
    s.append(a)


def _op_pop(s: Stack) -> None:
    _pop(s)


def _op_copy(s: Stack) -> None:
    # Upstream ``Copy`` uses ``((Number) pop).intValue()`` — a Float count is
    # accepted and truncated. Java only branches on ``n > 0``; a negative or
    # over-large ``n`` either no-ops or throws IndexOutOfBounds (a
    # RuntimeException), which we surface as OSError.
    n = _pop_int_value(s)
    if n <= 0:
        return
    if n > len(s):
        raise OSError("copy operand out of range")
    top = s[-n:]
    s.extend(top)


def _op_index(s: Stack) -> None:
    # Upstream ``Index`` uses ``((Number) pop).intValue()`` (Float accepted,
    # truncated); only ``n < 0`` is an explicit rangecheck, an over-large ``n``
    # throws IndexOutOfBounds (RuntimeException) -> OSError here.
    n = _pop_int_value(s)
    if n < 0 or n >= len(s):
        raise OSError("index operand out of range")
    s.append(s[-1 - n])


def _op_roll(s: Stack) -> None:
    # Upstream ``Roll`` uses ``((Number) pop).intValue()`` for both j and n
    # (Float counts accepted, truncated).
    j = _pop_int_value(s)
    n = _pop_int_value(s)
    # Mirror upstream PDFBox StackOperators$Roll EXACTLY (parity over the
    # cleaner PostScript-Reference semantics): it does NOT reduce ``j`` modulo
    # ``n``. ``j == 0`` is a no-op; ``n < 0`` is a range error. For any other
    # ``j`` it pops ``j`` (or ``n + j`` when ``j < 0``) elements followed by the
    # remaining group and re-pushes them rotated. When ``|j| > n`` upstream pops
    # more entries than the stack holds and throws ``EmptyStackException`` — we
    # surface the same condition as ``OSError`` (our IOException analogue)
    # rather than silently rotating like a mod-reduced implementation would.
    if j == 0:
        return
    if n < 0:
        raise OSError(f"roll rangecheck: n={n}")
    if abs(j) > n:
        # Upstream tries to pop |j| (or n - |j| more) past the top n entries.
        raise OSError("roll: rotation count out of range (stack underflow)")
    if n == 0:
        return
    if n > len(s):
        # Upstream StackOperators$Roll pops ``n`` entries off the stack before
        # rotating; when the stack holds fewer than ``n`` the pop loop drains it
        # and the next pop throws EmptyStackException. Surface that as OSError
        # (our IOException analogue) instead of silently rolling the short slice
        # a Python ``s[-n:]`` would otherwise produce (jar: ``{ 1 2 9 1 roll }``
        # over a 2-deep stack raises EmptyStackException).
        raise OSError("roll: n exceeds stack depth (stack underflow)")
    top = s[-n:]
    # Split point in the top-``n`` window matching upstream StackOperators$Roll:
    #   j > 0: the top ``j`` entries wrap to the bottom; cut at ``n - j``.
    #   j < 0: the top ``-j`` entries wrap to the bottom; cut at ``-j``.
    cut = -j if j < 0 else n - j
    rolled = top[cut:] + top[:cut]
    s[-n:] = rolled


# ---------- boolean ----------


def _cmp_pop(s: Stack) -> tuple[object, object]:
    b = _pop(s)
    a = _pop(s)
    return a, b


def _float32_compare_eq(a: int | float, b: int | float) -> bool:
    # Upstream ``Eq`` compares via ``Float.compare(a.floatValue(),
    # b.floatValue())`` — both operands are narrowed to 32-bit float first. For
    # the magnitudes Type 4 programs use this is indistinguishable from a direct
    # compare, but narrow explicitly so a value that differs only beyond float32
    # precision compares equal exactly as Java does.
    fa = struct.unpack("f", struct.pack("f", float(a)))[0]
    fb = struct.unpack("f", struct.pack("f", float(b)))[0]
    return fa == fb


def _boxed_equals(a: object, b: object) -> bool:
    """Mirror Java ``Object.equals`` across the boxed Type-4 value types.

    Upstream RelationalOperators$Eq does ``op1.equals(op2)`` when not both are
    Numbers. Java's ``Boolean.equals`` returns false for any non-Boolean
    argument and ``Integer.equals`` for any non-Integer, so a Boolean and a
    Number are NEVER equal — unlike Python where ``True == 1`` is true (``bool``
    subclasses ``int``). Treat a mixed boolean/number pair as unequal to match."""
    a_bool = isinstance(a, bool)
    b_bool = isinstance(b, bool)
    if a_bool != b_bool:
        # One side is a Boolean, the other isn't — Java's equals is always false.
        return False
    return a == b


def _op_eq(s: Stack) -> None:
    a, b = _cmp_pop(s)
    # Upstream: both Number => float32 compare; otherwise Object.equals. A
    # number-vs-boolean pair takes the equals branch (always unequal).
    if _is_number(a) and _is_number(b):
        s.append(_float32_compare_eq(a, b))
    else:
        s.append(_boxed_equals(a, b))


def _op_ne(s: Stack) -> None:
    a, b = _cmp_pop(s)
    if _is_number(a) and _is_number(b):
        s.append(not _float32_compare_eq(a, b))
    else:
        s.append(not _boxed_equals(a, b))


def _op_lt(s: Stack) -> None:
    # Comparison ops cast both operands to (Number) (popReal); a Boolean raises.
    b = _pop_real(s)
    a = _pop_real(s)
    s.append(a < b)


def _op_le(s: Stack) -> None:
    b = _pop_real(s)
    a = _pop_real(s)
    s.append(a <= b)


def _op_gt(s: Stack) -> None:
    b = _pop_real(s)
    a = _pop_real(s)
    s.append(a > b)


def _op_ge(s: Stack) -> None:
    b = _pop_real(s)
    a = _pop_real(s)
    s.append(a >= b)


def _logical(s: Stack, name: str, bool_fn: Callable, int_fn: Callable) -> None:
    """Shared body for ``and`` / ``or`` / ``xor`` — upstream
    ``AbstractLogicalOperator``: both Boolean => boolean op (Boolean result);
    both Integer => int op (Integer result); anything else (notably any Float,
    or a mixed bool/int pair) => ClassCastException."""
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(bool_fn(a, b))
    elif _is_int(a) and _is_int(b):
        s.append(int_fn(a, b))
    else:
        raise OSError(f"type mismatch: {name} operands must be bool/bool or int/int")


def _op_and(s: Stack) -> None:
    _logical(s, "and", lambda a, b: a and b, lambda a, b: a & b)


def _op_or(s: Stack) -> None:
    _logical(s, "or", lambda a, b: a or b, lambda a, b: a | b)


def _op_xor(s: Stack) -> None:
    _logical(s, "xor", lambda a, b: a != b, lambda a, b: a ^ b)


def _op_not(s: Stack) -> None:
    a = _pop(s)
    if isinstance(a, bool):
        s.append(not a)
    elif _is_int(a):
        # Upstream ``Not`` on an Integer is arithmetic negation (``-int1``),
        # NOT a bitwise complement, and the result keeps the Integer tag. A
        # Float raises ClassCastException (the strict int discipline). See
        # CLAUDE.md "Behavior over style".
        s.append(-a)
    else:
        raise OSError("type mismatch: not operand must be bool or int")


def _op_bitshift(s: Stack) -> None:
    # Both operands are ``(Integer)`` casts — a Float shift count or value
    # raises ClassCastException. Result keeps the Integer tag.
    #
    # Upstream BitwiseOperators$Bitshift is plain Java ``int1 << shift`` /
    # ``int1 >> -shift``. Java's shift operators use only the low 5 bits of the
    # shift count (``shift & 0x1f``) and compute in 32-bit two's-complement, so
    # ``1 40 bitshift`` is ``1 << (40 & 31)`` == 256 (not ``1 << 40``) and
    # ``1 31 bitshift`` wraps to ``Integer.MIN_VALUE``. The right shift is
    # arithmetic (sign-preserving). A Python ``int`` is unbounded, so we mask
    # the count to 5 bits, then wrap the result back into the 32-bit range to
    # reproduce Java's truncation exactly.
    shift = _pop_int_strict(s)
    val = _pop_int_strict(s)
    if shift >= 0:
        s.append(_wrap_int32(val << (shift & 0x1F)))
    else:
        # Java arithmetic right shift: ``val >> (-shift & 0x1f)``. Python's
        # ``>>`` is already arithmetic on a (sign-correct) int; wrap defensively.
        s.append(_wrap_int32(val >> ((-shift) & 0x1F)))


def _op_true(s: Stack) -> None:
    s.append(True)


def _op_false(s: Stack) -> None:
    s.append(False)


# ---------- conditional ----------


def _op_if(s: Stack) -> None:
    proc = _pop(s)
    cond = _pop(s)
    if not isinstance(proc, list):
        raise OSError("if expects a procedure on top of stack")
    if not isinstance(cond, bool):
        raise OSError("if expects a boolean condition")
    if cond:
        _execute(proc, s)


def _op_ifelse(s: Stack) -> None:
    proc_false = _pop(s)
    proc_true = _pop(s)
    cond = _pop(s)
    if not (isinstance(proc_true, list) and isinstance(proc_false, list)):
        raise OSError("ifelse expects two procedures")
    if not isinstance(cond, bool):
        raise OSError("ifelse expects a boolean condition")
    _execute(proc_true if cond else proc_false, s)


# Operator-name groupings mirror the source organisation in upstream
# ``Operators.java``: ARITHMETIC pulls from ArithmeticOperators, STACK
# from StackOperators, BOOLEAN merges Bitwise + Relational (the upstream
# splits those into two files but registers them in one map; we keep the
# combined view because the executor doesn't distinguish them), and
# CONDITIONAL holds ``if`` / ``ifelse``. Tuples (not lists) so callers
# can safely treat them as immutable.
ARITHMETIC_OPERATORS: tuple[str, ...] = (
    "add", "sub", "mul", "div", "idiv", "mod", "neg", "abs",
    "ceiling", "floor", "round", "truncate", "sqrt", "sin", "cos",
    "atan", "exp", "ln", "log", "cvi", "cvr",
)
STACK_OPERATORS: tuple[str, ...] = (
    "dup", "exch", "pop", "copy", "index", "roll",
)
BOOLEAN_OPERATORS: tuple[str, ...] = (
    "eq", "ne", "lt", "le", "gt", "ge",
    "and", "or", "xor", "not", "bitshift",
    "true", "false",
)
CONDITIONAL_OPERATORS: tuple[str, ...] = ("if", "ifelse")


_OPERATORS: dict[str, Operator] = {
    # arithmetic
    "add": _op_add,
    "sub": _op_sub,
    "mul": _op_mul,
    "div": _op_div,
    "idiv": _op_idiv,
    "mod": _op_mod,
    "neg": _op_neg,
    "abs": _op_abs,
    "ceiling": _op_ceiling,
    "floor": _op_floor,
    "round": _op_round,
    "truncate": _op_truncate,
    "sqrt": _op_sqrt,
    "sin": _op_sin,
    "cos": _op_cos,
    "atan": _op_atan,
    "exp": _op_exp,
    "ln": _op_ln,
    "log": _op_log,
    "cvi": _op_cvi,
    "cvr": _op_cvr,
    # stack
    "dup": _op_dup,
    "exch": _op_exch,
    "pop": _op_pop,
    "copy": _op_copy,
    "index": _op_index,
    "roll": _op_roll,
    # boolean
    "eq": _op_eq,
    "ne": _op_ne,
    "lt": _op_lt,
    "le": _op_le,
    "gt": _op_gt,
    "ge": _op_ge,
    "and": _op_and,
    "or": _op_or,
    "xor": _op_xor,
    "not": _op_not,
    "bitshift": _op_bitshift,
    "true": _op_true,
    "false": _op_false,
    # conditional
    "if": _op_if,
    "ifelse": _op_ifelse,
}

# Built after _OPERATORS so the union below covers every registered name.
ALL_OPERATORS: tuple[str, ...] = tuple(_OPERATORS.keys())


def get_operator(name: str) -> Operator | None:
    """Return the executor callable registered for PostScript operator
    ``name``, or ``None`` when no such operator exists.

    Mirrors upstream ``Operators.getOperator(String)``. Useful for tools
    that want to introspect the supported operator set without
    instantiating a function. The returned callable takes a single
    ``stack`` argument and mutates it in place; callers should not rely
    on its identity (it is a private implementation detail and may be
    swapped for an equivalent callable in future releases).
    """
    return _OPERATORS.get(name)


def is_supported_operator(name: str) -> bool:
    """Return ``True`` when ``name`` is a recognised Type 4 PostScript
    operator. Pythonic predicate form alongside :func:`get_operator`."""
    return name in _OPERATORS


__all__ = [
    "ALL_OPERATORS",
    "ARITHMETIC_OPERATORS",
    "BOOLEAN_OPERATORS",
    "CONDITIONAL_OPERATORS",
    "PDFunctionType4",
    "STACK_OPERATORS",
    "get_operator",
    "is_supported_operator",
]
