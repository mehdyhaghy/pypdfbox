from __future__ import annotations

import math

from pypdfbox.cos import COSBase, COSStream

from .pd_function import PDFunction

# Tokens emitted by ``_tokenize`` are either:
#   * ``float``                  — a numeric literal pushed straight onto the stack
#   * ``str``                    — an operator name or boolean literal
#   * ``list[Token]`` (sub-seq)  — a ``{...}`` instruction sub-sequence (operand
#                                  to ``if`` / ``ifelse``)
Token = "float | bool | str | list"


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

    def get_function_type(self) -> int:
        return 4

    # ---------- evaluation ----------

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Evaluate the PostScript-calculator program on ``input`` per
        PDF 32000-1 §7.10.5.

        ``input`` is clipped to ``/Domain`` first, pushed onto an initially
        empty stack (first input on bottom), the program is executed, and
        the remaining stack is returned (bottom-up) clipped to ``/Range``.
        """
        clipped = self.clip_input(input)

        body = self._read_body()
        sequence = _parse(body)

        stack: list[float | bool] = list(clipped)
        _execute(sequence, stack)

        # Booleans surviving in the output are coerced to floats (1.0 / 0.0)
        # before /Range clipping; /Range is defined over numeric outputs.
        result = [float(v) for v in stack]
        return self.clip_output(result)

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
    tokens regardless of whitespace adjacency."""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            out.append("".join(buf))
            buf.clear()

    for ch in body:
        if ch in "{}":
            flush()
            out.append(ch)
        elif ch.isspace():
            flush()
        else:
            buf.append(ch)
    flush()
    return out


def _parse(body: str) -> list:
    """Parse ``body`` into a nested instruction sequence.

    The outermost ``{ ... }`` wrap is required (PDF 32000-1 §7.10.5: the
    program "shall consist of a sequence of operators and operands enclosed
    in braces"). An empty body parses as the empty sequence.
    """
    tokens = _tokenize(body)
    if not tokens:
        return []

    pos = [0]

    def parse_block() -> list:
        seq: list = []
        while pos[0] < len(tokens):
            tok = tokens[pos[0]]
            pos[0] += 1
            if tok == "{":
                seq.append(parse_block())
            elif tok == "}":
                return seq
            else:
                seq.append(_classify(tok))
        return seq

    # Strip an optional outer { ... }; any extra braces are reported.
    if tokens[0] == "{":
        pos[0] = 1
        seq = parse_block()
        if pos[0] != len(tokens):
            raise OSError(
                f"unexpected trailing tokens in PostScript body: "
                f"{tokens[pos[0]:]!r}"
            )
        return seq
    return parse_block()


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


def _pop(stack: list) -> float | bool:
    if not stack:
        raise OSError("stack underflow")
    return stack.pop()


def _pop_num(stack: list) -> float:
    v = _pop(stack)
    if isinstance(v, bool):
        raise OSError("type mismatch: expected number, got boolean")
    if not isinstance(v, (int, float)):
        raise OSError(f"type mismatch: expected number, got {type(v).__name__}")
    return float(v)


def _pop_int(stack: list) -> int:
    v = _pop_num(stack)
    if v != int(v):
        raise OSError(f"type mismatch: expected integer, got {v}")
    return int(v)


def _pop_bool(stack: list) -> bool:
    v = _pop(stack)
    if not isinstance(v, bool):
        raise OSError(f"type mismatch: expected boolean, got {type(v).__name__}")
    return v


def _execute(sequence: list, stack: list) -> None:
    for token in sequence:
        if isinstance(token, list):
            # A ``{ ... }`` substack is a literal — push for ``if``/``ifelse``
            # to consume. Bare execution would consume the whole frame.
            stack.append(token)  # type: ignore[arg-type]
            continue
        if isinstance(token, bool):
            stack.append(token)
            continue
        if isinstance(token, (int, float)):
            stack.append(float(token))
            continue
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


def _op_add(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a + b)


def _op_sub(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a - b)


def _op_mul(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a * b)


def _op_div(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    if b == 0:
        raise OSError("division by zero")
    s.append(a / b)


def _op_idiv(s: list) -> None:
    b = _pop_int(s)
    a = _pop_int(s)
    if b == 0:
        raise OSError("integer division by zero")
    # Truncation toward zero (PostScript semantics, not Python floor).
    q = abs(a) // abs(b)
    if (a < 0) ^ (b < 0):
        q = -q
    s.append(float(q))


def _op_mod(s: list) -> None:
    b = _pop_int(s)
    a = _pop_int(s)
    if b == 0:
        raise OSError("mod by zero")
    # Sign of result follows dividend (PostScript semantics).
    r = abs(a) % abs(b)
    if a < 0:
        r = -r
    s.append(float(r))


def _op_neg(s: list) -> None:
    a = _pop_num(s)
    s.append(-a)


def _op_abs(s: list) -> None:
    a = _pop_num(s)
    s.append(abs(a))


def _op_ceiling(s: list) -> None:
    a = _pop_num(s)
    s.append(float(math.ceil(a)))


def _op_floor(s: list) -> None:
    a = _pop_num(s)
    s.append(float(math.floor(a)))


def _op_round(s: list) -> None:
    a = _pop_num(s)
    # PostScript round(): nearest, ties go toward +infinity.
    s.append(float(math.floor(a + 0.5)))


def _op_truncate(s: list) -> None:
    a = _pop_num(s)
    s.append(float(math.trunc(a)))


def _op_sqrt(s: list) -> None:
    a = _pop_num(s)
    if a < 0:
        raise OSError("sqrt of negative number")
    s.append(math.sqrt(a))


def _op_sin(s: list) -> None:
    a = _pop_num(s)  # degrees per PostScript
    s.append(math.sin(math.radians(a)))


def _op_cos(s: list) -> None:
    a = _pop_num(s)
    s.append(math.cos(math.radians(a)))


def _op_atan(s: list) -> None:
    den = _pop_num(s)
    num = _pop_num(s)
    # PostScript atan(num, den) returns degrees in [0, 360).
    deg = math.degrees(math.atan2(num, den))
    if deg < 0:
        deg += 360.0
    s.append(deg)


def _op_exp(s: list) -> None:
    exponent = _pop_num(s)
    base = _pop_num(s)
    s.append(math.pow(base, exponent))


def _op_ln(s: list) -> None:
    a = _pop_num(s)
    if a <= 0:
        raise OSError("ln of non-positive number")
    s.append(math.log(a))


def _op_log(s: list) -> None:
    a = _pop_num(s)
    if a <= 0:
        raise OSError("log of non-positive number")
    s.append(math.log10(a))


def _op_cvi(s: list) -> None:
    a = _pop_num(s)
    s.append(float(int(math.trunc(a))))


def _op_cvr(s: list) -> None:
    a = _pop_num(s)
    s.append(float(a))


# ---------- stack ----------


def _op_dup(s: list) -> None:
    if not s:
        raise OSError("stack underflow")
    s.append(s[-1])


def _op_exch(s: list) -> None:
    b = _pop(s)
    a = _pop(s)
    s.append(b)
    s.append(a)


def _op_pop(s: list) -> None:
    _pop(s)


def _op_copy(s: list) -> None:
    n = _pop_int(s)
    if n < 0 or n > len(s):
        raise OSError("copy operand out of range")
    if n == 0:
        return
    top = s[-n:]
    s.extend(top)


def _op_index(s: list) -> None:
    n = _pop_int(s)
    if n < 0 or n >= len(s):
        raise OSError("index operand out of range")
    s.append(s[-1 - n])


def _op_roll(s: list) -> None:
    j = _pop_int(s)
    n = _pop_int(s)
    if n < 0 or n > len(s):
        raise OSError("roll operand out of range")
    if n == 0:
        return
    j %= n
    if j == 0:
        return
    top = s[-n:]
    rolled = top[-j:] + top[:-j]
    s[-n:] = rolled


# ---------- boolean ----------


def _cmp_pop(s: list) -> tuple:
    b = _pop(s)
    a = _pop(s)
    return a, b


def _op_eq(s: list) -> None:
    a, b = _cmp_pop(s)
    s.append(a == b)


def _op_ne(s: list) -> None:
    a, b = _cmp_pop(s)
    s.append(a != b)


def _op_lt(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a < b)


def _op_le(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a <= b)


def _op_gt(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a > b)


def _op_ge(s: list) -> None:
    b = _pop_num(s)
    a = _pop_num(s)
    s.append(a >= b)


def _op_and(s: list) -> None:
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(a and b)
    elif isinstance(a, bool) or isinstance(b, bool):
        raise OSError("type mismatch: and operands must both be bool or both int")
    else:
        s.append(float(int(a) & int(b)))


def _op_or(s: list) -> None:
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(a or b)
    elif isinstance(a, bool) or isinstance(b, bool):
        raise OSError("type mismatch: or operands must both be bool or both int")
    else:
        s.append(float(int(a) | int(b)))


def _op_xor(s: list) -> None:
    b = _pop(s)
    a = _pop(s)
    if isinstance(a, bool) and isinstance(b, bool):
        s.append(a != b)
    elif isinstance(a, bool) or isinstance(b, bool):
        raise OSError("type mismatch: xor operands must both be bool or both int")
    else:
        s.append(float(int(a) ^ int(b)))


def _op_not(s: list) -> None:
    a = _pop(s)
    if isinstance(a, bool):
        s.append(not a)
    elif isinstance(a, (int, float)):
        s.append(float(~int(a)))
    else:
        raise OSError("type mismatch: not operand must be bool or int")


def _op_bitshift(s: list) -> None:
    shift = _pop_int(s)
    val = _pop_int(s)
    if shift >= 0:
        s.append(float(val << shift))
    else:
        s.append(float(val >> -shift))


def _op_true(s: list) -> None:
    s.append(True)


def _op_false(s: list) -> None:
    s.append(False)


# ---------- conditional ----------


def _op_if(s: list) -> None:
    proc = _pop(s)
    cond = _pop(s)
    if not isinstance(proc, list):
        raise OSError("if expects a procedure on top of stack")
    if not isinstance(cond, bool):
        raise OSError("if expects a boolean condition")
    if cond:
        _execute(proc, s)


def _op_ifelse(s: list) -> None:
    proc_false = _pop(s)
    proc_true = _pop(s)
    cond = _pop(s)
    if not (isinstance(proc_true, list) and isinstance(proc_false, list)):
        raise OSError("ifelse expects two procedures")
    if not isinstance(cond, bool):
        raise OSError("ifelse expects a boolean condition")
    _execute(proc_true if cond else proc_false, s)


_OPERATORS = {
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


__all__ = ["PDFunctionType4"]
