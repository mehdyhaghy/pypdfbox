from __future__ import annotations

import math
from collections.abc import Callable

from pypdfbox.cos import COSBase, COSStream

from .pd_function import PDFunction

# Tokens emitted by ``_tokenize`` are either:
#   * ``float``                  — a numeric literal pushed straight onto the stack
#   * ``str``                    — an operator name or boolean literal
#   * ``list[Token]`` (sub-seq)  — a ``{...}`` instruction sub-sequence (operand
#                                  to ``if`` / ``ifelse``)
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

    Numeric stability uses Python ``float`` throughout; booleans pushed by
    ``true``/``false``/comparisons live on the same stack as numbers (per
    spec). Stack underflow, type mismatch, and unknown operators all surface
    as ``OSError`` to mirror upstream ``IOException``. ``def``, ``forall``,
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
        clipped = self.clip_input(input)

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
            # keeping only the last N stack entries before clipping.
            stack = stack[-declared:]

        # Booleans surviving in the output are coerced to floats (1.0 / 0.0)
        # before /Range clipping; /Range is defined over numeric outputs.
        result = [_to_output_float(v) for v in stack]

        return self.clip_output(result)

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
    """Parse ``body`` into a nested instruction sequence.

    The outermost ``{ ... }`` wrap is required (PDF 32000-1 §7.10.5: the
    program "shall consist of a sequence of operators and operands enclosed
    in braces"). An empty body parses as the empty sequence.
    """
    tokens = _tokenize(body)
    if not tokens:
        return []

    pos = [0]

    def parse_block(expect_close: bool) -> Instruction:
        seq: Instruction = []
        while pos[0] < len(tokens):
            tok = tokens[pos[0]]
            pos[0] += 1
            if tok == "{":
                seq.append(parse_block(True))
            elif tok == "}":
                if not expect_close:
                    raise OSError("unexpected closing brace in PostScript body")
                return seq
            else:
                seq.append(_classify(tok))
        if expect_close:
            raise OSError("missing closing brace in PostScript body")
        return seq

    # Strip an optional outer { ... }; any extra braces are reported.
    if tokens[0] == "{":
        pos[0] = 1
        seq = parse_block(True)
        if pos[0] != len(tokens):
            raise OSError(
                f"unexpected trailing tokens in PostScript body: "
                f"{tokens[pos[0]:]!r}"
            )
        return seq
    return parse_block(False)


def _classify(tok: str) -> float | bool | str:
    """Tag a raw token as a numeric literal, boolean literal, or operator
    name. Hex / radix-prefixed numbers (PostScript's ``16#FF`` form) are not
    used by Type 4 programs in practice and are rejected by falling through
    to the operator path — the executor will raise on the unknown name."""
    if tok == "true":
        return True
    if tok == "false":
        return False
    # Numeric literal? Try int first then float.
    try:
        return float(int(tok))
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


# ---------- stack machine ----------


def _pop(stack: Stack) -> object:
    if not stack:
        raise OSError("stack underflow")
    return stack.pop()


def _pop_num(stack: Stack) -> float:
    v = _pop(stack)
    if isinstance(v, bool):
        raise OSError("type mismatch: expected number, got boolean")
    if not isinstance(v, (int, float)):
        raise OSError(f"type mismatch: expected number, got {type(v).__name__}")
    return float(v)


def _pop_int(stack: Stack) -> int:
    v = _pop_num(stack)
    if v != int(v):
        raise OSError(f"type mismatch: expected integer, got {v}")
    return int(v)


def _pop_bool(stack: Stack) -> bool:
    v = _pop(stack)
    if not isinstance(v, bool):
        raise OSError(f"type mismatch: expected boolean, got {type(v).__name__}")
    return v


def _int_bit_operand(value: object, operator_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OSError(
            f"type mismatch: {operator_name} operands must both be bool or both int"
        )
    return int(value)


def _to_output_float(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
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
            stack.append(float(token))
            continue
        if not isinstance(token, str):
            raise OSError(f"unsupported PostScript token: {token!r}")
        # Operator name.
        op = _OPERATORS.get(token)
        if op is None:
            raise OSError(f"unsupported PostScript operator: {token!r}")
        op(stack)


# ---------- operators ----------
#
# Each handler pops operands from ``stack`` and pushes results in the order
# specified by PDF 32000-1 §7.10.5 / PostScript reference. Unsupported types
# (def, forall, for, dictionaries) are intentionally absent — they raise
# "unsupported operator" via the dispatcher.


def _op_add(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a + b)


def _op_sub(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a - b)


def _op_mul(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a * b)


def _op_div(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
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
    b = _pop_int(s)
    a = _pop_int(s)
    if b == 0:
        raise OSError("integer division by zero")
    # Truncation toward zero (PostScript semantics, not Python floor).
    q = abs(a) // abs(b)
    if (a < 0) ^ (b < 0):
        q = -q
    s.append(float(q))


def _op_mod(s: Stack) -> None:
    b = _pop_int(s)
    a = _pop_int(s)
    if b == 0:
        raise OSError("mod by zero")
    # Sign of result follows dividend (PostScript semantics).
    r = abs(a) % abs(b)
    if a < 0:
        r = -r
    s.append(float(r))


def _op_neg(s: Stack) -> None:
    a = _pop_num(s)
    s.append(-a)


def _op_abs(s: Stack) -> None:
    a = _pop_num(s)
    s.append(abs(a))


def _op_ceiling(s: Stack) -> None:
    a = _pop_num(s)
    s.append(float(math.ceil(a)))


def _op_floor(s: Stack) -> None:
    a = _pop_num(s)
    s.append(float(math.floor(a)))


def _op_round(s: Stack) -> None:
    a = _pop_num(s)
    # PostScript round(): nearest, ties go toward +infinity.
    s.append(float(math.floor(a + 0.5)))


def _op_truncate(s: Stack) -> None:
    a = _pop_num(s)
    s.append(float(math.trunc(a)))


def _op_sqrt(s: Stack) -> None:
    a = _pop_num(s)
    if a < 0:
        raise OSError("sqrt of negative number")
    s.append(math.sqrt(a))


def _op_sin(s: Stack) -> None:
    a = _pop_num(s)  # degrees per PostScript
    s.append(math.sin(math.radians(a)))


def _op_cos(s: Stack) -> None:
    a = _pop_num(s)
    s.append(math.cos(math.radians(a)))


def _op_atan(s: Stack) -> None:
    den = _pop_num(s)
    num = _pop_num(s)
    # PostScript atan(num, den) returns degrees in [0, 360).
    deg = math.degrees(math.atan2(num, den))
    if deg < 0:
        deg += 360.0
    s.append(deg)


def _op_exp(s: Stack) -> None:
    exponent = _pop_num(s)
    base = _pop_num(s)
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
    a = _pop_num(s)
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
    a = _pop_num(s)
    # Mirrors upstream ArithmeticOperators$Log == ``(float) Math.log10(...)``;
    # same -Infinity / NaN edge behaviour as ``ln`` (see above).
    if a == 0.0:
        s.append(-math.inf)
    elif a < 0.0:
        s.append(math.nan)
    else:
        s.append(math.log10(a))


def _op_cvi(s: Stack) -> None:
    a = _pop_num(s)
    s.append(float(int(math.trunc(a))))


def _op_cvr(s: Stack) -> None:
    a = _pop_num(s)
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
    n = _pop_int(s)
    if n < 0 or n > len(s):
        raise OSError("copy operand out of range")
    if n == 0:
        return
    top = s[-n:]
    s.extend(top)


def _op_index(s: Stack) -> None:
    n = _pop_int(s)
    if n < 0 or n >= len(s):
        raise OSError("index operand out of range")
    s.append(s[-1 - n])


def _op_roll(s: Stack) -> None:
    j = _pop_int(s)
    n = _pop_int(s)
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


def _op_eq(s: Stack) -> None:
    a, b = _cmp_pop(s)
    s.append(a == b)


def _op_ne(s: Stack) -> None:
    a, b = _cmp_pop(s)
    s.append(a != b)


def _op_lt(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a < b)


def _op_le(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a <= b)


def _op_gt(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a > b)


def _op_ge(s: Stack) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a >= b)


def _op_and(s: Stack) -> None:
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(a and b)
    elif isinstance(a, bool) or isinstance(b, bool):
        raise OSError("type mismatch: and operands must both be bool or both int")
    else:
        s.append(float(_int_bit_operand(a, "and") & _int_bit_operand(b, "and")))


def _op_or(s: Stack) -> None:
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(a or b)
    elif isinstance(a, bool) or isinstance(b, bool):
        raise OSError("type mismatch: or operands must both be bool or both int")
    else:
        s.append(float(_int_bit_operand(a, "or") | _int_bit_operand(b, "or")))


def _op_xor(s: Stack) -> None:
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(a != b)
    elif isinstance(a, bool) or isinstance(b, bool):
        raise OSError("type mismatch: xor operands must both be bool or both int")
    else:
        s.append(float(_int_bit_operand(a, "xor") ^ _int_bit_operand(b, "xor")))


def _op_not(s: Stack) -> None:
    a = _pop(s)
    if isinstance(a, bool):
        s.append(not a)
    elif isinstance(a, (int, float)):
        # Mirrors upstream PDFBox semantics: ``not`` on an integer is
        # arithmetic negation, NOT bitwise complement. The PostScript
        # Reference does specify bit-invert here, but PDFBox 3.0 negates
        # (``-int1`` in BitwiseOperators$Not), and parity with PDFBox
        # behavior is the contract — see CLAUDE.md "Behavior over style".
        s.append(-float(a))
    else:
        raise OSError("type mismatch: not operand must be bool or int")


def _op_bitshift(s: Stack) -> None:
    shift = _pop_int(s)
    val = _pop_int(s)
    if shift >= 0:
        s.append(float(val << shift))
    else:
        s.append(float(val >> -shift))


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
