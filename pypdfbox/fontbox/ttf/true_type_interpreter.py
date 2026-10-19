"""The TrueType bytecode interpreter: the VM driver and the 256-entry opcode dispatch table.

It carries the execution engine - the :class:`BytecodeStream` cursor driven
dispatch loop, function definition and calling with a depth cap, branching,
the push family, and the stack/arithmetic/logical/storage and point-moving
opcodes - plus the size lifecycle: ``fpgm`` executed once, ``prep`` executed
per ppem change with the result saved as the per-glyph template. An opcode
with no handler and no ``IDEF`` binding raises :class:`HintingException`,
which the caller catches per glyph and falls back to the raw outline.

Performance design (behaviour is upstream's; only the mechanics differ):

* ``_dispatch`` is a 256-entry list of closures, built once per interpreter,
  exactly like upstream's ``OpHandler[]``. Opcodes whose behaviour depends
  only on bits of the opcode (``MDRP``/``MIRP``/``PUSHB[n]`` ...) get one
  closure per opcode with the flags pre-decoded.
* The dispatch loop and the push/branch handlers read the stream's slots
  directly instead of calling ``next_byte``; each still applies the same
  bounds rule and raises the same :class:`HintingException`.
* The operand stack is a Python ``list``. Growing opcodes enforce the
  ``maxStackElements`` capacity; an ``IndexError`` from popping an empty stack
  is converted to ``HintingException("interpreter stack underflow")`` by
  :meth:`TrueTypeInterpreter.run`. Every other index the bytecode supplies
  (points, storage, CVT, contours) is range-checked explicitly, so negative
  values never reach Python's wrap-around indexing, and so do the contour
  ends IUP walks; any other ``IndexError`` is reported as "interpreter index
  out of range", not as an underflow.
* Values are plain Python ``int``\\ s. Every place upstream relies on Java's
  32-bit ``int`` wrapping (arithmetic opcodes, coordinate stores, ``long`` to
  ``int`` casts in :mod:`fixed`) narrows explicitly, with an in-range fast
  path so the common case costs one chained comparison.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from itertools import chain

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.execution_context import ExecutionContext
from pypdfbox.fontbox.ttf.execution_tracer import ExecutionTracer
from pypdfbox.fontbox.ttf.fixed import (
    ONE,
    ONE_F2DOT14,
    ceil,
    div,
    div_fix,
    mul,
    mul14,
    mul_div,
    scale,
    to_int32,
)
from pypdfbox.fontbox.ttf.function_def import FunctionDef
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.unit_vector import UnitVector
from pypdfbox.fontbox.ttf.zone import Zone

OpHandler = Callable[[ExecutionContext], None]

# opcodes referenced by the engine itself (control flow / push)
_NPUSHB = 0x40
_NPUSHW = 0x41
_PUSHB_BASE = 0xB0
_PUSHW_BASE = 0xB8
_ELSE = 0x1B
_IF = 0x58
_EIF = 0x59
_FDEF = 0x2C
_ENDF = 0x2D
_IDEF = 0x89

_INT_MIN = -0x80000000
_INT_MAX = 0x7FFFFFFF

_CONTROL_VALUE = ExecutionContext.CodeRange.CONTROL_VALUE
_GLYPH = ExecutionContext.CodeRange.GLYPH

# inline operand bytes of each opcode when skipped: n for PUSHB/PUSHW[n], -1 / -2 for NPUSHB /
# NPUSHW (count byte follows; one or two bytes per value), 0 otherwise
_PUSH_SKIP = [0] * 256
_PUSH_SKIP[_NPUSHB] = -1
_PUSH_SKIP[_NPUSHW] = -2
for _k in range(8):
    _PUSH_SKIP[_PUSHB_BASE + _k] = _k + 1
    _PUSH_SKIP[_PUSHW_BASE + _k] = 2 * (_k + 1)
del _k

# big-endian signed 16-bit word unpackers for 0..255 words
_WORDS = [struct.Struct(f">{n}h") for n in range(256)]


def _i32(value: int) -> int:
    return ((value + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def _abs32(value: int) -> int:
    """Java ``Math.abs`` of the Java ``int`` ``value``: ``abs(MIN_VALUE)`` stays negative."""
    value = to_int32(value)
    return _INT_MIN if value == _INT_MIN else abs(value)


def _short(value: int) -> int:
    """Java ``(short)`` cast: the low 16 bits, sign-extended."""
    return ((value + 0x8000) & 0xFFFF) - 0x8000


def _is_stack_underflow(error: IndexError, stack: list[int]) -> bool:
    """Whether ``error`` came from reaching past the bottom of the operand stack.

    The stack handlers either pop (``list.pop`` reports "pop from empty list"
    or "pop index out of range") or index the top one or two slots, which
    can only fail while fewer than two values are left.
    """
    message = str(error)
    if message.startswith("pop "):
        return True
    return message == "list index out of range" and len(stack) < 2


def _skip_push_operands(opcode: int, code: bytes, ip: int, limit: int) -> int:
    """Returns the position past the inline operands of a push opcode (``ip`` for other opcodes).

    Mirrors upstream ``skipPushOperands``: the count byte of NPUSHB/NPUSHW is
    a bounds-checked read and the skip is a bounds-checked seek.
    """
    k = _PUSH_SKIP[opcode]
    if k == 0:
        return ip
    if k < 0:
        if ip >= limit:
            raise HintingException(f"bytecode read past end at {ip}")
        k = -k * code[ip]
        ip += 1
    target = ip + k
    if target > limit:
        raise HintingException(f"bytecode seek out of range: {target} of {limit}")
    return target


class TrueTypeInterpreter:
    """Mirrors upstream package-private ``TrueTypeInterpreter``."""

    MAX_CALL_DEPTH = 64
    """Maximum ``CALL``/``LOOPCALL`` nesting depth, matching FreeType."""

    __slots__ = (
        "_control_value_program",
        "_dispatch",
        "_font_program",
        "_functions",
        "_instruction_defs",
        "_max_stack_elements",
        "_point_size",
        "_ppem",
        "_raw_control_values",
        "_saved_state",
        "_scaled_control_values",
        "_storage",
        "_tracer",
        "_twilight_zone",
        "_units_per_em",
    )

    def __init__(
        self,
        max_stack_elements: int,
        max_storage: int,
        max_twilight_points: int,
        units_per_em: int,
    ) -> None:
        """Sizes the interpreter from ``maxp`` (stack, storage, twilight) and ``head`` (upem)."""
        self._max_stack_elements = max_stack_elements
        self._units_per_em = units_per_em
        # The storage area and twilight zone belong to the size, not to one program run: a font
        # may seed them in prep and read them back from every glyph program. FreeType keeps both
        # on the TT_Size and clears them in tt_size_run_prep, which is what set_ppem does below.
        self._storage = [0] * max(max_storage, 0)
        self._twilight_zone = Zone(max(max_twilight_points, 0), 0)
        self._functions: dict[int, FunctionDef] = {}
        self._instruction_defs: dict[int, FunctionDef] = {}
        self._font_program: bytes | None = None
        self._control_value_program: bytes | None = None
        self._raw_control_values: list[int] = []
        self._scaled_control_values: list[int] = []
        self._ppem = 0
        self._point_size = 0
        self._saved_state: GraphicsState | None = None
        self._tracer: ExecutionTracer | None = None
        self._dispatch: list[OpHandler] = [None] * 256  # type: ignore[list-item]
        self._build_dispatch()

    # --- configuration ---------------------------------------------------

    def set_font_program(self, program: bytes | None) -> None:
        """Sets the raw ``fpgm`` bytecode, or ``None``."""
        self._font_program = program

    def set_control_value_program(self, program: bytes | None) -> None:
        """Sets the raw ``prep`` bytecode, or ``None``."""
        self._control_value_program = program

    def set_control_values(self, values: list[int] | None) -> None:
        """Sets the raw control values in font units, or ``None``."""
        self._raw_control_values = values if values is not None else []

    def set_tracer(self, tracer: ExecutionTracer | None) -> None:
        """Attaches (or clears with ``None``) an execution tracer.

        The tracer emits one FreeType-comparable line per executed
        instruction. Used by the trace-diff tooling to localize divergence;
        off in normal operation.
        """
        self._tracer = tracer

    # --- lifecycle -------------------------------------------------------

    def prepare_font_program(self) -> None:
        """Runs the font program (``fpgm``) once, populating the function table.

        Safe to call when there is no font program.
        """
        self._functions.clear()
        self._instruction_defs.clear()
        if not self._font_program:
            return
        ctx = self.new_context(GraphicsState())
        ctx.set_code_range(ExecutionContext.CodeRange.FONT)
        self.run(ctx, BytecodeStream(self._font_program))

    def set_ppem(self, ppem_value: int, point_size_value: int) -> None:
        """Establishes a new ppem and runs ``prep``, saving the per-glyph template state.

        Scales the control values, clears the storage area and twilight zone,
        runs the control value program (``prep``) from a default graphics
        state, and saves the resulting state as the per-glyph template.
        Whatever ``prep`` leaves in storage and the twilight zone stays there
        for every glyph hinted at this size, which is why they are cleared
        here and not per glyph - after FreeType's ``tt_size_run_prep``.
        Anything the font program wrote to storage is discarded, again as
        FreeType does: ``fpgm`` is only meant to define functions.
        """
        self._ppem = ppem_value
        self._point_size = point_size_value
        self._scale_control_values()
        self._storage[:] = [0] * len(self._storage)
        self._twilight_zone.reset()

        gs = GraphicsState()
        if self._control_value_program:
            ctx = self.new_context(gs)
            ctx.set_code_range(ExecutionContext.CodeRange.CONTROL_VALUE)
            self.run(ctx, BytecodeStream(self._control_value_program))
        self._saved_state = gs

    def _scale_control_values(self) -> None:
        ppem = self._ppem
        upem = self._units_per_em
        self._scaled_control_values = [scale(v, ppem, upem) for v in self._raw_control_values]

    def new_context(self, gs: GraphicsState) -> ExecutionContext:
        """Builds a fresh execution context wired to this interpreter's sizes and state.

        The stack and per-run counters are new; the storage area and twilight
        zone are the interpreter's own, so values ``prep`` left there are
        visible to the glyph programs.
        """
        ctx = ExecutionContext(
            self,
            gs,
            self._max_stack_elements,
            self._storage,
            self._scaled_control_values,
            self._twilight_zone,
        )
        ctx._units_per_em = self._units_per_em
        ctx._ppem = self._ppem
        ctx._point_size = self._point_size
        return ctx

    def execute_program(self, program: bytes, ppem_value: int) -> ExecutionContext:
        """Test/utility entry point: runs a standalone program from the saved state.

        Runs from the saved (post-``prep``) state, or a default state if no
        size has been set, and returns the resulting context so callers can
        inspect the stack and state.
        """
        self._ppem = ppem_value
        gs = self._saved_state.copy() if self._saved_state is not None else GraphicsState()
        ctx = self.new_context(gs)
        self.run(ctx, BytecodeStream(program))
        return ctx

    def get_saved_state(self) -> GraphicsState | None:
        """Returns the saved post-``prep`` graphics state, or ``None`` if no size has been set."""
        return self._saved_state

    def get_functions(self) -> dict[int, FunctionDef]:
        """Returns the function table populated by ``fpgm``."""
        return self._functions

    # --- execution engine ------------------------------------------------

    def run(self, ctx: ExecutionContext, s: BytecodeStream) -> None:
        """Runs a bytecode stream to completion (or until an ``ENDF`` returns from a body)."""
        previous = ctx._stream
        ctx._stream = s
        dispatch = self._dispatch
        code = s._code
        tracer = self._tracer
        try:
            if tracer is None:
                while s._ip < s._limit and not ctx._return_from_function:
                    ip = s._ip
                    s._instruction_start = ip
                    s._ip = ip + 1
                    dispatch[code[ip]](ctx)
            else:
                while s._ip < s._limit and not ctx._return_from_function:
                    ip = s._ip
                    s._instruction_start = ip
                    s._ip = ip + 1
                    opcode = code[ip]
                    tracer.trace(ip, opcode, ctx)
                    dispatch[opcode](ctx)
        except IndexError as e:
            # The only index left unchecked is the operand stack's: popping or peeking past its
            # bottom. Every other index is range-checked where it is used, so an IndexError from
            # anywhere else is a bug here and is reported as such rather than as an underflow.
            # (Classified only on this error path, so the dispatch loop pays nothing for it.)
            if _is_stack_underflow(e, ctx._stack):
                raise HintingException("interpreter stack underflow", e) from e
            raise HintingException(f"interpreter index out of range: {e}", e) from e
        finally:
            ctx._stream = previous

    def call_function(self, ctx: ExecutionContext, function_number: int) -> None:
        """Calls the function with the given number, running its body until the matching ENDF."""
        fdef = self._functions.get(function_number)
        if fdef is None:
            raise HintingException(f"call to undefined function {function_number}")
        self._call_body(ctx, fdef)

    def _call_body(self, ctx: ExecutionContext, fdef: FunctionDef) -> None:
        """Runs a function/instruction body from its entry point until the matching ENDF."""
        if ctx._call_depth >= TrueTypeInterpreter.MAX_CALL_DEPTH:
            raise HintingException(
                f"maximum call depth {TrueTypeInterpreter.MAX_CALL_DEPTH} exceeded"
            )
        ctx._call_depth += 1
        try:
            body = BytecodeStream(fdef._program)
            body.set_end(fdef._end)
            body.seek(fdef._entry_point)
            self.run(ctx, body)
            ctx._return_from_function = False
        finally:
            ctx._call_depth -= 1

    def _define_function(self, ctx: ExecutionContext) -> None:
        function_number = ctx._stack.pop()
        s = ctx._stream
        entry = s._ip
        end = self._skip_function_body(s)
        self._functions[function_number] = FunctionDef(s._code, entry, end)

    def _define_instruction(self, ctx: ExecutionContext) -> None:
        """IDEF: binds the opcode on top of the stack to the following instructions (to ENDF)."""
        opcode = ctx._stack.pop()
        s = ctx._stream
        entry = s._ip
        end = self._skip_function_body(s)
        self._instruction_defs[opcode & 0xFF] = FunctionDef(s._code, entry, end)

    @staticmethod
    def _skip_function_body(s: BytecodeStream) -> int:
        """Skips to the ENDF closing a function/instruction body, leaving the stream after it.

        A nested FDEF/IDEF is an error, as in FreeType (Nested_DEFS). Returns
        the position of the ENDF.
        """
        code = s._code
        limit = s._limit
        ip = s._ip
        while ip < limit:
            opcode = code[ip]
            ip += 1
            if opcode == _ENDF:
                s._ip = ip
                return ip - 1
            if opcode in (_FDEF, _IDEF):
                s._ip = ip
                raise HintingException("nested function definition")
            if _PUSH_SKIP[opcode]:
                ip = _skip_push_operands(opcode, code, ip, limit)
        s._ip = ip
        raise HintingException("FDEF without matching ENDF")

    @staticmethod
    def _skip_to_else_or_eif(s: BytecodeStream) -> None:
        """On a false IF, skips forward to the matching ELSE or EIF.

        Accounts for nested IF blocks and for the inline operands of push
        instructions. Leaves the stream positioned just after the terminator.
        """
        code = s._code
        limit = s._limit
        ip = s._ip
        depth = 0
        while ip < limit:
            opcode = code[ip]
            ip += 1
            if opcode == _IF:
                depth += 1
            elif opcode == _EIF:
                if depth == 0:
                    s._ip = ip
                    return
                depth -= 1
            elif opcode == _ELSE and depth == 0:
                s._ip = ip
                return
            elif _PUSH_SKIP[opcode]:
                ip = _skip_push_operands(opcode, code, ip, limit)
        s._ip = ip
        raise HintingException("IF without matching EIF")

    @staticmethod
    def _skip_to_eif(s: BytecodeStream) -> None:
        """After a true IF branch reaches its ELSE, skips the else-branch to the matching EIF."""
        code = s._code
        limit = s._limit
        ip = s._ip
        depth = 0
        while ip < limit:
            opcode = code[ip]
            ip += 1
            if opcode == _IF:
                depth += 1
            elif opcode == _EIF:
                if depth == 0:
                    s._ip = ip
                    return
                depth -= 1
            elif _PUSH_SKIP[opcode]:
                ip = _skip_push_operands(opcode, code, ip, limit)
        s._ip = ip
        raise HintingException("ELSE without matching EIF")

    # --- dispatch table --------------------------------------------------

    def _build_dispatch(self) -> None:
        dispatch = self._dispatch
        instruction_defs = self._instruction_defs

        def make_default(opcode: int) -> OpHandler:
            def handler(ctx: ExecutionContext) -> None:
                # an opcode with no built-in handler may have been given one by IDEF
                fdef = instruction_defs.get(opcode)
                if fdef is not None:
                    self._call_body(ctx, fdef)
                    return
                raise HintingException(f"unsupported TrueType opcode 0x{opcode:02X}")

            return handler

        for i in range(256):
            dispatch[i] = make_default(i)

        self._install_push_ops()
        self._install_stack_ops()
        self._install_arithmetic_ops()
        self._install_logical_ops()
        self._install_flow_ops()
        self._install_state_ops()
        self._install_storage_and_cvt_ops()
        self._install_misc_ops()
        self._install_vector_ops()
        self._install_round_ops()
        self._install_point_ops()
        self._install_interpolation_ops()
        self._install_measure_ops()
        self._install_delta_ops()
        self._install_flip_ops()

    def _install_push_ops(self) -> None:
        d = self._dispatch

        def npushb(ctx: ExecutionContext) -> None:
            s = ctx._stream
            ip = s._ip
            limit = s._limit
            if ip >= limit:
                raise HintingException(f"bytecode read past end at {ip}")
            code = s._code
            n = code[ip]
            ip += 1
            end = ip + n
            st = ctx._stack
            if end <= limit and len(st) + n <= ctx._stack_capacity:
                st.extend(code[ip:end])
                s._ip = end
                return
            s._ip = ip
            for _ in range(n):
                ctx.push(s.next_byte())

        def npushw(ctx: ExecutionContext) -> None:
            s = ctx._stream
            ip = s._ip
            limit = s._limit
            if ip >= limit:
                raise HintingException(f"bytecode read past end at {ip}")
            code = s._code
            n = code[ip]
            ip += 1
            end = ip + 2 * n
            st = ctx._stack
            if end <= limit and len(st) + n <= ctx._stack_capacity:
                st.extend(_WORDS[n].unpack_from(code, ip))
                s._ip = end
                return
            s._ip = ip
            for _ in range(n):
                ctx.push(s.next_word())

        d[_NPUSHB] = npushb
        d[_NPUSHW] = npushw

        def pushb1(ctx: ExecutionContext) -> None:
            s = ctx._stream
            ip = s._ip
            st = ctx._stack
            if ip < s._limit and len(st) < ctx._stack_capacity:
                st.append(s._code[ip])
                s._ip = ip + 1
                return
            ctx.push(s.next_byte())

        def pushw1(ctx: ExecutionContext) -> None:
            s = ctx._stream
            ip = s._ip
            st = ctx._stack
            if ip + 2 <= s._limit and len(st) < ctx._stack_capacity:
                code = s._code
                value = (code[ip] << 8) | code[ip + 1]
                st.append(value - 0x10000 if value & 0x8000 else value)
                s._ip = ip + 2
                return
            ctx.push(s.next_word())

        def make_pushb(count: int) -> OpHandler:
            def pushb(ctx: ExecutionContext) -> None:
                s = ctx._stream
                ip = s._ip
                end = ip + count
                st = ctx._stack
                if end <= s._limit and len(st) + count <= ctx._stack_capacity:
                    st.extend(s._code[ip:end])
                    s._ip = end
                    return
                for _ in range(count):
                    ctx.push(s.next_byte())

            return pushb

        def make_pushw(count: int) -> OpHandler:
            unpack_from = _WORDS[count].unpack_from

            def pushw(ctx: ExecutionContext) -> None:
                s = ctx._stream
                ip = s._ip
                end = ip + 2 * count
                st = ctx._stack
                if end <= s._limit and len(st) + count <= ctx._stack_capacity:
                    st.extend(unpack_from(s._code, ip))
                    s._ip = end
                    return
                for _ in range(count):
                    ctx.push(s.next_word())

            return pushw

        d[_PUSHB_BASE] = pushb1
        d[_PUSHW_BASE] = pushw1
        for k in range(1, 8):
            d[_PUSHB_BASE + k] = make_pushb(k + 1)
            d[_PUSHW_BASE + k] = make_pushw(k + 1)

    def _install_stack_ops(self) -> None:
        d = self._dispatch

        def dup(ctx: ExecutionContext) -> None:  # DUP
            st = ctx._stack
            if not st:
                raise HintingException("interpreter stack peek out of range: 0")
            if len(st) >= ctx._stack_capacity:
                raise HintingException(f"interpreter stack overflow at {len(st)}")
            st.append(st[-1])

        def pop(ctx: ExecutionContext) -> None:  # POP
            ctx._stack.pop()

        def clear(ctx: ExecutionContext) -> None:  # CLEAR
            ctx._stack.clear()

        def swap(ctx: ExecutionContext) -> None:  # SWAP
            st = ctx._stack
            st[-1], st[-2] = st[-2], st[-1]

        def depth(ctx: ExecutionContext) -> None:  # DEPTH
            ctx.push(len(ctx._stack))

        # CINDEX/MINDEX: k counts from the top, 1-based. An out-of-range k is ignored (the index
        # operand has been consumed and the stack is otherwise left alone), as FreeType does
        # outside pedantic mode, rather than aborting the glyph.
        def cindex(ctx: ExecutionContext) -> None:  # CINDEX
            st = ctx._stack
            k = st.pop()
            if 0 < k <= len(st):
                ctx.push(st[-k])

        def mindex(ctx: ExecutionContext) -> None:  # MINDEX
            st = ctx._stack
            k = st.pop()
            if k <= 0 or k > len(st):
                return
            # move the k-th element to the top; the k-1 elements above it keep their order
            st.append(st.pop(-k))

        def roll(ctx: ExecutionContext) -> None:  # ROLL
            # [a b c] -> [b c a]
            st = ctx._stack
            st.append(st.pop(-3))

        d[0x20] = dup
        d[0x21] = pop
        d[0x22] = clear
        d[0x23] = swap
        d[0x24] = depth
        d[0x25] = cindex
        d[0x26] = mindex
        d[0x8A] = roll

    def _install_arithmetic_ops(self) -> None:
        d = self._dispatch

        def add(ctx: ExecutionContext) -> None:  # ADD
            st = ctx._stack
            b = st.pop()
            v = st[-1] + b
            st[-1] = v if _INT_MIN <= v <= _INT_MAX else _i32(v)

        def sub(ctx: ExecutionContext) -> None:  # SUB
            st = ctx._stack
            b = st.pop()
            v = st[-1] - b
            st[-1] = v if _INT_MIN <= v <= _INT_MAX else _i32(v)

        def div_op(ctx: ExecutionContext) -> None:  # DIV
            st = ctx._stack
            b = st.pop()
            st[-1] = div(st[-1], b)

        def mul_op(ctx: ExecutionContext) -> None:  # MUL
            st = ctx._stack
            b = st.pop()
            st[-1] = mul(st[-1], b)

        def abs_op(ctx: ExecutionContext) -> None:  # ABS
            st = ctx._stack
            v = st[-1]
            if v < 0:
                st[-1] = _i32(-v)

        def neg(ctx: ExecutionContext) -> None:  # NEG
            st = ctx._stack
            st[-1] = _i32(-st[-1])

        def floor_op(ctx: ExecutionContext) -> None:  # FLOOR
            st = ctx._stack
            st[-1] = st[-1] & ~63

        def ceiling(ctx: ExecutionContext) -> None:  # CEILING
            st = ctx._stack
            st[-1] = ceil(st[-1])

        def max_op(ctx: ExecutionContext) -> None:  # MAX
            st = ctx._stack
            b = st.pop()
            if b > st[-1]:
                st[-1] = b

        def min_op(ctx: ExecutionContext) -> None:  # MIN
            st = ctx._stack
            b = st.pop()
            if b < st[-1]:
                st[-1] = b

        d[0x60] = add
        d[0x61] = sub
        d[0x62] = div_op
        d[0x63] = mul_op
        d[0x64] = abs_op
        d[0x65] = neg
        d[0x66] = floor_op
        d[0x67] = ceiling
        d[0x8B] = max_op
        d[0x8C] = min_op

    def _install_logical_ops(self) -> None:
        d = self._dispatch

        def lt(ctx: ExecutionContext) -> None:  # LT
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] < b else 0

        def lteq(ctx: ExecutionContext) -> None:  # LTEQ
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] <= b else 0

        def gt(ctx: ExecutionContext) -> None:  # GT
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] > b else 0

        def gteq(ctx: ExecutionContext) -> None:  # GTEQ
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] >= b else 0

        def eq(ctx: ExecutionContext) -> None:  # EQ
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] == b else 0

        def neq(ctx: ExecutionContext) -> None:  # NEQ
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] != b else 0

        # ODD/EVEN round with the *current round state* (not plain round-to-grid) and then test
        # the parity of the resulting pixel, as the spec says and FreeType does (Ins_ODD/Ins_EVEN)
        def odd(ctx: ExecutionContext) -> None:  # ODD
            st = ctx._stack
            st[-1] = 1 if (ctx._graphics_state.round(st[-1]) & 127) == 64 else 0

        def even(ctx: ExecutionContext) -> None:  # EVEN
            st = ctx._stack
            st[-1] = 1 if (ctx._graphics_state.round(st[-1]) & 127) == 0 else 0

        def and_op(ctx: ExecutionContext) -> None:  # AND
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] != 0 and b != 0 else 0

        def or_op(ctx: ExecutionContext) -> None:  # OR
            st = ctx._stack
            b = st.pop()
            st[-1] = 1 if st[-1] != 0 or b != 0 else 0

        def not_op(ctx: ExecutionContext) -> None:  # NOT
            st = ctx._stack
            st[-1] = 1 if st[-1] == 0 else 0

        d[0x50] = lt
        d[0x51] = lteq
        d[0x52] = gt
        d[0x53] = gteq
        d[0x54] = eq
        d[0x55] = neq
        d[0x56] = odd
        d[0x57] = even
        d[0x5A] = and_op
        d[0x5B] = or_op
        d[0x5C] = not_op

    def _install_flow_ops(self) -> None:
        d = self._dispatch
        skip_to_else_or_eif = TrueTypeInterpreter._skip_to_else_or_eif
        skip_to_eif = TrueTypeInterpreter._skip_to_eif
        jump = TrueTypeInterpreter._jump

        def if_op(ctx: ExecutionContext) -> None:  # IF
            if ctx._stack.pop() == 0:
                skip_to_else_or_eif(ctx._stream)

        def else_op(ctx: ExecutionContext) -> None:  # ELSE
            skip_to_eif(ctx._stream)

        def eif(ctx: ExecutionContext) -> None:  # EIF: no-op terminator
            pass

        def jmpr(ctx: ExecutionContext) -> None:  # JMPR
            jump(ctx, ctx._stack.pop())

        def jrot(ctx: ExecutionContext) -> None:  # JROT
            st = ctx._stack
            e = st.pop()
            offset = st.pop()
            if e != 0:
                jump(ctx, offset)

        def jrof(ctx: ExecutionContext) -> None:  # JROF
            st = ctx._stack
            e = st.pop()
            offset = st.pop()
            if e == 0:
                jump(ctx, offset)

        def endf(ctx: ExecutionContext) -> None:  # ENDF
            # ENDF outside a function body is an error in FreeType (ENDF_In_Exec_Stream); an FDEF
            # that was skipped correctly never lets its ENDF execute at the top level
            if ctx._call_depth <= 0:
                raise HintingException("ENDF outside a function body")
            ctx._return_from_function = True

        def call(ctx: ExecutionContext) -> None:  # CALL
            self.call_function(ctx, ctx._stack.pop())

        def loopcall(ctx: ExecutionContext) -> None:  # LOOPCALL
            st = ctx._stack
            function_number = st.pop()
            count = st.pop()
            # the spec calls the count unsigned; FreeType runs nothing at all when it is not
            # positive
            if count <= 0:
                return
            # charge the whole loop up front, so an absurd count fails before a single iteration
            ctx.count_loop_calls(count)
            call_function = self.call_function
            for _ in range(count):
                call_function(ctx, function_number)

        d[_IF] = if_op
        d[_ELSE] = else_op
        d[_EIF] = eif
        d[0x1C] = jmpr
        d[0x78] = jrot
        d[0x79] = jrof
        d[_FDEF] = self._define_function
        d[_ENDF] = endf
        d[_IDEF] = self._define_instruction
        d[0x2B] = call
        d[0x2A] = loopcall

    @staticmethod
    def _jump(ctx: ExecutionContext, offset: int) -> None:
        """Jumps to ``offset`` bytes from the start of the current instruction.

        A backward jump is the only way TrueType bytecode can loop other than
        ``LOOPCALL``, so those are counted against the run's budget and the
        program is abandoned once it exceeds it.
        """
        if offset < 0:
            ctx.count_negative_jump()
        s = ctx._stream
        target = s._instruction_start + offset
        if not _INT_MIN <= target <= _INT_MAX:
            target = _i32(target)
        if target < 0 or target > s._limit:
            raise HintingException(f"bytecode seek out of range: {target} of {s._limit}")
        s._ip = target

    def _install_state_ops(self) -> None:
        d = self._dispatch

        def sloop(ctx: ExecutionContext) -> None:  # SLOOP
            ctx._graphics_state._loop = ctx._stack.pop()

        def srp0(ctx: ExecutionContext) -> None:  # SRP0
            ctx._graphics_state._rp0 = ctx._stack.pop()

        def srp1(ctx: ExecutionContext) -> None:  # SRP1
            ctx._graphics_state._rp1 = ctx._stack.pop()

        def srp2(ctx: ExecutionContext) -> None:  # SRP2
            ctx._graphics_state._rp2 = ctx._stack.pop()

        def smd(ctx: ExecutionContext) -> None:  # SMD
            ctx._graphics_state._minimum_distance = ctx._stack.pop()

        def sdb(ctx: ExecutionContext) -> None:  # SDB
            ctx._graphics_state._delta_base = ctx._stack.pop()

        def sds(ctx: ExecutionContext) -> None:  # SDS
            ctx._graphics_state._delta_shift = ctx._stack.pop()

        def scvtci(ctx: ExecutionContext) -> None:  # SCVTCI
            ctx._graphics_state._control_value_cut_in = ctx._stack.pop()

        def sswci(ctx: ExecutionContext) -> None:  # SSWCI
            ctx._graphics_state._single_width_cut_in = ctx._stack.pop()

        def ssw(ctx: ExecutionContext) -> None:  # SSW
            ctx._graphics_state._single_width_value = ctx._stack.pop()

        def round_state(state: int) -> OpHandler:
            def handler(ctx: ExecutionContext) -> None:
                ctx._graphics_state.set_round_state(state)

            return handler

        # grid period in F2Dot14: one pixel for SROUND, the 45-degree diagonal sqrt(2)/2 for
        # S45ROUND
        def sround(ctx: ExecutionContext) -> None:  # SROUND
            ctx._graphics_state.set_super_round(0x4000, ctx._stack.pop())

        def s45round(ctx: ExecutionContext) -> None:  # S45ROUND
            ctx._graphics_state.set_super_round(0x2D41, ctx._stack.pop())

        def szp0(ctx: ExecutionContext) -> None:  # SZP0
            ctx._graphics_state._zp0 = ctx._stack.pop()

        def szp1(ctx: ExecutionContext) -> None:  # SZP1
            ctx._graphics_state._zp1 = ctx._stack.pop()

        def szp2(ctx: ExecutionContext) -> None:  # SZP2
            ctx._graphics_state._zp2 = ctx._stack.pop()

        def szps(ctx: ExecutionContext) -> None:  # SZPS
            zone = ctx._stack.pop()
            gs = ctx._graphics_state
            gs._zp0 = zone
            gs._zp1 = zone
            gs._zp2 = zone

        d[0x17] = sloop
        d[0x10] = srp0
        d[0x11] = srp1
        d[0x12] = srp2
        d[0x1A] = smd
        d[0x5E] = sdb
        d[0x5F] = sds
        d[0x1D] = scvtci
        d[0x1E] = sswci
        d[0x1F] = ssw
        d[0x18] = round_state(GraphicsState.ROUND_TO_GRID)  # RTG
        d[0x19] = round_state(GraphicsState.ROUND_TO_HALF_GRID)  # RTHG
        d[0x3D] = round_state(GraphicsState.ROUND_TO_DOUBLE_GRID)  # RTDG
        d[0x7C] = round_state(GraphicsState.ROUND_UP_TO_GRID)  # RUTG
        d[0x7D] = round_state(GraphicsState.ROUND_DOWN_TO_GRID)  # RDTG
        d[0x7A] = round_state(GraphicsState.ROUND_OFF)  # ROFF
        d[0x76] = sround
        d[0x77] = s45round
        d[0x13] = szp0
        d[0x14] = szp1
        d[0x15] = szp2
        d[0x16] = szps

    def _install_storage_and_cvt_ops(self) -> None:
        d = self._dispatch

        def rs(ctx: ExecutionContext) -> None:  # RS
            st = ctx._stack
            index = st.pop()
            storage = ctx._storage
            if index < 0 or index >= len(storage):
                raise HintingException(f"storage index out of range: {index}")
            st.append(storage[index])

        def ws(ctx: ExecutionContext) -> None:  # WS
            st = ctx._stack
            value = st.pop()
            index = st.pop()
            storage = ctx._storage
            if index < 0 or index >= len(storage):
                raise HintingException(f"storage index out of range: {index}")
            storage[index] = value

        def rcvt(ctx: ExecutionContext) -> None:  # RCVT
            st = ctx._stack
            index = st.pop()
            cvt = ctx._control_values
            if index < 0 or index >= len(cvt):
                raise HintingException(f"cvt index out of range: {index}")
            st.append(cvt[index])

        def wcvtp(ctx: ExecutionContext) -> None:  # WCVTP
            st = ctx._stack
            value = st.pop()
            index = st.pop()
            cvt = ctx._control_values
            if index < 0 or index >= len(cvt):
                raise HintingException(f"cvt index out of range: {index}")
            cvt[index] = value

        def wcvtf(ctx: ExecutionContext) -> None:  # WCVTF
            st = ctx._stack
            value = st.pop()
            index = st.pop()
            cvt = ctx._control_values
            if index < 0 or index >= len(cvt):
                raise HintingException(f"cvt index out of range: {index}")
            cvt[index] = scale(value, ctx._ppem, ctx._units_per_em)

        d[0x43] = rs
        d[0x42] = ws
        d[0x45] = rcvt
        d[0x44] = wcvtp
        d[0x70] = wcvtf

    def _install_misc_ops(self) -> None:
        d = self._dispatch

        def mppem(ctx: ExecutionContext) -> None:  # MPPEM
            ctx.push(ctx._ppem)

        def mps(ctx: ExecutionContext) -> None:  # MPS
            ctx.push(ctx._point_size)

        def pop_only(ctx: ExecutionContext) -> None:  # DEBUG / SANGW: pop, no-op
            ctx._stack.pop()

        def aa(ctx: ExecutionContext) -> None:  # AA - deprecated no-op
            pass

        def getinfo(ctx: ExecutionContext) -> None:  # GETINFO
            st = ctx._stack
            selector = st.pop()
            result = 0
            if selector & 0x0001:
                # rasterizer version 40: FreeType's "minimal" subpixel interpreter, which we
                # mirror for grayscale antialiased rendering (lighter stems than the classic v35)
                result |= 40
            # we always render grayscale-subpixel ("lean"), non-LCD: report the subpixel bits a
            # v40 grayscale rasterizer returns so fonts take their lighter ClearType-aware code
            # paths. (the grayscale bit 12 is intentionally not set: FreeType clears
            # exc->grayscale in lean mode)
            if selector & 0x0040:
                result |= 1 << 13  # subpixel hinting active
            if selector & 0x0400:
                result |= 1 << 17  # ClearType hinting active
            if selector & 0x0800:
                result |= 1 << 18  # subpixel positioned
            if selector & 0x1000:
                result |= 1 << 19  # grayscale ClearType
            st.append(result)

        d[0x4B] = mppem
        d[0x4C] = mps
        d[0x4F] = pop_only  # DEBUG
        d[0x7E] = pop_only  # SANGW (deprecated, pops)
        d[0x7F] = aa
        d[0x88] = getinfo

    # --- vector setters --------------------------------------------------

    def _install_vector_ops(self) -> None:
        d = self._dispatch
        set_proj_and_freedom_axis = TrueTypeInterpreter._set_proj_and_freedom_axis
        set_projection_axis = TrueTypeInterpreter._set_projection_axis
        set_freedom_axis = TrueTypeInterpreter._set_freedom_axis

        def bind(fn: Callable[[ExecutionContext, bool], None], flag: bool) -> OpHandler:
            def handler(ctx: ExecutionContext) -> None:
                fn(ctx, flag)

            return handler

        d[0x00] = bind(set_proj_and_freedom_axis, False)  # SVTCA[0] y
        d[0x01] = bind(set_proj_and_freedom_axis, True)  # SVTCA[1] x
        d[0x02] = bind(set_projection_axis, False)  # SPVTCA[0] y
        d[0x03] = bind(set_projection_axis, True)  # SPVTCA[1] x
        d[0x04] = bind(set_freedom_axis, False)  # SFVTCA[0] y
        d[0x05] = bind(set_freedom_axis, True)  # SFVTCA[1] x
        d[0x06] = bind(self._set_projection_to_line, False)  # SPVTL[0] parallel
        d[0x07] = bind(self._set_projection_to_line, True)  # SPVTL[1] perpendicular
        d[0x08] = bind(self._set_freedom_to_line, False)  # SFVTL[0] parallel
        d[0x09] = bind(self._set_freedom_to_line, True)  # SFVTL[1] perpendicular
        d[0x86] = bind(self._set_dual_projection_to_line, False)  # SDPVTL[0]
        d[0x87] = bind(self._set_dual_projection_to_line, True)  # SDPVTL[1]

        def sfvtpv(ctx: ExecutionContext) -> None:  # SFVTPV
            pv = ctx._pv
            ctx._fv.set(pv._x, pv._y)

        # SPVFS/SFVFS: the low 16 bits, sign-extended, normalized; (0,0) leaves the vector
        # unchanged (FreeType's Ins_SPVFS/Ins_SFVFS)
        def spvfs(ctx: ExecutionContext) -> None:  # SPVFS
            st = ctx._stack
            y = _short(st.pop())
            x = _short(st.pop())
            if x != 0 or y != 0:
                v = UnitVector.normalize(x, y)
                ctx._pv.set(v._x, v._y)
                ctx._dv.set(v._x, v._y)

        def sfvfs(ctx: ExecutionContext) -> None:  # SFVFS
            st = ctx._stack
            y = _short(st.pop())
            x = _short(st.pop())
            if x != 0 or y != 0:
                v = UnitVector.normalize(x, y)
                ctx._fv.set(v._x, v._y)

        def gpv(ctx: ExecutionContext) -> None:  # GPV
            pv = ctx._pv
            ctx.push(pv._x)
            ctx.push(pv._y)

        def gfv(ctx: ExecutionContext) -> None:  # GFV
            fv = ctx._fv
            ctx.push(fv._x)
            ctx.push(fv._y)

        d[0x0E] = sfvtpv
        d[0x0A] = spvfs
        d[0x0B] = sfvfs
        d[0x0C] = gpv
        d[0x0D] = gfv

    @staticmethod
    def _set_proj_and_freedom_axis(ctx: ExecutionContext, x_axis: bool) -> None:
        TrueTypeInterpreter._set_projection_axis(ctx, x_axis)
        TrueTypeInterpreter._set_freedom_axis(ctx, x_axis)

    @staticmethod
    def _set_projection_axis(ctx: ExecutionContext, x_axis: bool) -> None:
        x = ONE_F2DOT14 if x_axis else 0
        y = 0 if x_axis else ONE_F2DOT14
        pv = ctx._pv
        pv._x = x
        pv._y = y
        dv = ctx._dv
        dv._x = x
        dv._y = y

    @staticmethod
    def _set_freedom_axis(ctx: ExecutionContext, x_axis: bool) -> None:
        fv = ctx._fv
        fv._x = ONE_F2DOT14 if x_axis else 0
        fv._y = 0 if x_axis else ONE_F2DOT14

    def _set_projection_to_line(self, ctx: ExecutionContext, perpendicular: bool) -> None:
        # FreeType's Ins_SPVTL: the dual vector follows the projection vector; only SDPVTL derives
        # it from the original outline
        v = self._line_vector(ctx, perpendicular, False)[0]
        ctx._pv.set(v._x, v._y)
        ctx._dv.set(v._x, v._y)

    def _set_freedom_to_line(self, ctx: ExecutionContext, perpendicular: bool) -> None:
        v = self._line_vector(ctx, perpendicular, False)[0]
        ctx._fv.set(v._x, v._y)

    def _set_dual_projection_to_line(self, ctx: ExecutionContext, perpendicular: bool) -> None:
        current, original = self._line_vector(ctx, perpendicular, True)
        ctx._pv.set(current._x, current._y)
        ctx._dv.set(original._x, original._y)  # type: ignore[union-attr]

    @staticmethod
    def _line_vector(
        ctx: ExecutionContext, perpendicular: bool, with_original: bool
    ) -> tuple[UnitVector, UnitVector | None]:
        """Pops two point numbers and returns the unit vector along (or across) their line.

        As FreeType's Ins_SxVTL/Ins_SDPVTL do: the top of the stack is a point
        in zp2, the one below it a point in zp1, and the line runs from the
        zp2 point to the zp1 point. A zero-length line gives the x axis,
        ignoring the perpendicular flag. Returns (current-based vector,
        original-based vector or ``None`` unless ``with_original``).
        """
        gs = ctx._graphics_state
        st = ctx._stack
        p2 = st.pop()
        p1 = st.pop()
        to = ctx.get_zone(gs._zp1)
        frm = ctx.get_zone(gs._zp2)
        ExecutionContext.check_point(to, p1)
        ExecutionContext.check_point(frm, p2)
        original = None
        perp = perpendicular
        if with_original:
            dx = _i32(to._original_x[p1] - frm._original_x[p2])
            dy = _i32(to._original_y[p1] - frm._original_y[p2])
            # FreeType clears the perpendicular flag on a zero-length original line and does not
            # restore it for the current line that follows
            perp = perp and (dx != 0 or dy != 0)
            original = TrueTypeInterpreter._line_unit_vector(dx, dy, perp)
        current = TrueTypeInterpreter._line_unit_vector(
            _i32(to._current_x[p1] - frm._current_x[p2]),
            _i32(to._current_y[p1] - frm._current_y[p2]),
            perp,
        )
        return current, original

    @staticmethod
    def _line_unit_vector(dx: int, dy: int, perpendicular: bool) -> UnitVector:
        if dx == 0 and dy == 0:
            return UnitVector.x_axis()
        # rotate before normalizing, as FreeType does, so rounding matches for negative components
        if perpendicular:
            return UnitVector.normalize(_i32(-dy), dx)
        return UnitVector.normalize(dx, dy)

    # --- rounding opcodes ------------------------------------------------

    def _install_round_ops(self) -> None:
        d = self._dispatch

        def round_op(ctx: ExecutionContext) -> None:  # ROUND[ab]
            st = ctx._stack
            st[-1] = ctx._graphics_state.round(st[-1])

        def nround(ctx: ExecutionContext) -> None:  # NROUND[ab]: pop and push back unchanged
            if not ctx._stack:
                raise HintingException("interpreter stack underflow")

        for k in range(4):
            d[0x68 + k] = round_op
            d[0x6C + k] = nround

    # --- point movement --------------------------------------------------

    def _install_point_ops(self) -> None:
        d = self._dispatch
        d[0x0F] = self._do_isect  # ISECT

        def bind(fn: Callable[[ExecutionContext, bool], None], flag: bool) -> OpHandler:
            def handler(ctx: ExecutionContext) -> None:
                fn(ctx, flag)

            return handler

        d[0x2E] = bind(self._do_mdap, False)  # MDAP[0] no round
        d[0x2F] = bind(self._do_mdap, True)  # MDAP[1] round
        d[0x3E] = bind(self._do_miap, False)  # MIAP[0] no round
        d[0x3F] = bind(self._do_miap, True)  # MIAP[1] round + cut-in
        d[0x3A] = bind(self._do_msirp, False)  # MSIRP[0]
        d[0x3B] = bind(self._do_msirp, True)  # MSIRP[1] set rp0
        d[0x3C] = self._do_align_rp  # ALIGNRP
        d[0x27] = self._do_align_pts  # ALIGNPTS
        d[0x29] = self._do_utp  # UTP
        d[0x38] = self._do_shpix  # SHPIX
        d[0x32] = bind(self._do_shp, False)  # SHP[0] rp2/zp1
        d[0x33] = bind(self._do_shp, True)  # SHP[1] rp1/zp0
        d[0x34] = bind(self._do_shc, False)  # SHC[0]
        d[0x35] = bind(self._do_shc, True)  # SHC[1]
        d[0x36] = bind(self._do_shz, False)  # SHZ[0]
        d[0x37] = bind(self._do_shz, True)  # SHZ[1]
        for op in range(0xC0, 0xE0):
            d[op] = TrueTypeInterpreter._make_mdrp(op)  # MDRP[abcde]
        for op in range(0xE0, 0x100):
            d[op] = TrueTypeInterpreter._make_mirp(op)  # MIRP[abcde]

    @staticmethod
    def _do_isect(ctx: ExecutionContext) -> None:
        """ISECT: moves a point to where line A (a0-a1, in zp1) crosses line B (b0-b1, in zp0).

        With u = a1 - a0 and v = b1 - b0 the crossing is a0 + t u, where
        t = ((b0 - a0) x v) / (u x v), solved exactly in integers. When the
        lines are within about 3 degrees of parallel (|u x v| at most 1/19 of
        |u . v|, the cut-off FreeType uses) the crossing is too unstable to
        use, and the point goes to the average of the four line points instead.
        """
        gs = ctx._graphics_state
        st = ctx._stack
        b1 = st.pop()
        b0 = st.pop()
        a1 = st.pop()
        a0 = st.pop()
        point = st.pop()
        line_a = ctx.get_zone(gs._zp1)
        line_b = ctx.get_zone(gs._zp0)
        target = ctx.get_zone(gs._zp2)
        check_point = ExecutionContext.check_point
        check_point(line_a, a0)
        check_point(line_a, a1)
        check_point(line_b, b0)
        check_point(line_b, b1)
        check_point(target, point)

        start_x = line_a._current_x[a0]
        start_y = line_a._current_y[a0]
        ux = line_a._current_x[a1] - start_x
        uy = line_a._current_y[a1] - start_y
        other_x = line_b._current_x[b0]
        other_y = line_b._current_y[b0]
        vx = line_b._current_x[b1] - other_x
        vy = line_b._current_y[b1] - other_y

        cross = ux * vy - uy * vx
        dot = ux * vx + uy * vy
        if abs(cross) * 19 > abs(dot):
            along = (other_x - start_x) * vy - (other_y - start_y) * vx
            x = _i32(start_x + _rounded_quotient(along, ux, cross))
            y = _i32(start_y + _rounded_quotient(along, uy, cross))
        else:
            sum_x = start_x + line_a._current_x[a1] + other_x + line_b._current_x[b1]
            sum_y = start_y + line_a._current_y[a1] + other_y + line_b._current_y[b1]
            # Java long division truncates towards zero
            x = _i32(sum_x // 4 if sum_x >= 0 else -((-sum_x) // 4))
            y = _i32(sum_y // 4 if sum_y >= 0 else -((-sum_y) // 4))
        target._current_x[point] = x
        target._current_y[point] = y
        target._touched_x[point] = True
        target._touched_y[point] = True

    @staticmethod
    def _do_mdap(ctx: ExecutionContext, round_: bool) -> None:
        gs = ctx._graphics_state
        point = ctx._stack.pop()
        zone = ctx.get_zone(gs._zp0)
        ExecutionContext.check_point(zone, point)
        cur = ctx.project(zone._current_x[point], zone._current_y[point])
        distance = gs.round(cur) if round_ else cur
        ctx.move_point(zone, point, distance - cur)
        gs._rp0 = point
        gs._rp1 = point

    @staticmethod
    def _do_miap(ctx: ExecutionContext, round_: bool) -> None:
        gs = ctx._graphics_state
        st = ctx._stack
        cvt_index = st.pop()
        point = st.pop()
        zone = ctx.get_zone(gs._zp0)
        ExecutionContext.check_point(zone, point)
        cvt = ctx._control_values
        value = cvt[cvt_index] if 0 <= cvt_index < len(cvt) else 0

        if gs._zp0 == 0:
            # twilight point: establish its position from the control value along the freedom
            # vector (FreeType's Ins_MIAP)
            fv = ctx._fv
            zone._original_x[point] = mul14(value, fv._x)
            zone._original_y[point] = mul14(value, fv._y)
            zone._current_x[point] = zone._original_x[point]
            zone._current_y[point] = zone._original_y[point]
        cur = ctx.project(zone._current_x[point], zone._current_y[point])
        if round_:
            if _abs32(value - cur) > gs._control_value_cut_in:
                value = cur
            value = gs.round(value)
        ctx.move_point(zone, point, value - cur)
        gs._rp0 = point
        gs._rp1 = point

    @staticmethod
    def _do_msirp(ctx: ExecutionContext, set_rp0: bool) -> None:
        gs = ctx._graphics_state
        st = ctx._stack
        distance = st.pop()
        point = st.pop()
        zp1 = ctx.get_zone(gs._zp1)
        zp0 = ctx.get_zone(gs._zp0)
        rp0 = gs._rp0
        ExecutionContext.check_point(zp1, point)
        ExecutionContext.check_point(zp0, rp0)
        if gs._zp1 == 0:
            # twilight point: place it at rp0's original position moved by the distance, as the
            # MS rasterizer does (undocumented; FreeType's Ins_MSIRP)
            zp1._original_x[point] = zp0._original_x[rp0]
            zp1._original_y[point] = zp0._original_y[rp0]
            ctx.move_original(zp1, point, distance)
            zp1._current_x[point] = zp1._original_x[point]
            zp1._current_y[point] = zp1._original_y[point]
        cur_dist = ctx.projected_distance(zp1, point, zp0, rp0)
        ctx.move_point(zp1, point, distance - cur_dist)
        gs._rp1 = rp0
        gs._rp2 = point
        if set_rp0:
            gs._rp0 = point

    @staticmethod
    def _do_align_rp(ctx: ExecutionContext) -> None:
        gs = ctx._graphics_state
        zp1 = ctx.get_zone(gs._zp1)
        zp0 = ctx.get_zone(gs._zp0)
        rp0 = gs._rp0
        st = ctx._stack
        projected_distance = ctx.projected_distance
        move_point = ctx.move_point
        for _ in range(gs._loop):
            point = st.pop()
            move_point(zp1, point, -projected_distance(zp1, point, zp0, rp0))
        gs._loop = 1

    @staticmethod
    def _do_align_pts(ctx: ExecutionContext) -> None:
        """ALIGNPTS, after FreeType's Ins_ALIGNPTS.

        The point below the top of the stack is in zp1, the top one in zp0,
        and each moves by half their projected distance (truncated), towards
        the other.
        """
        gs = ctx._graphics_state
        st = ctx._stack
        p2 = st.pop()
        p1 = st.pop()
        zp1 = ctx.get_zone(gs._zp1)
        zp0 = ctx.get_zone(gs._zp0)
        dist = ctx.projected_distance(zp0, p2, zp1, p1)
        distance = dist // 2 if dist >= 0 else -((-dist) // 2)
        ctx.move_point(zp1, p1, distance)
        ctx.move_point(zp0, p2, -distance)

    @staticmethod
    def _do_utp(ctx: ExecutionContext) -> None:
        gs = ctx._graphics_state
        zone = ctx.get_zone(gs._zp0)
        fv = ctx._fv
        point = ExecutionContext.check_point(zone, ctx._stack.pop())
        if fv._x != 0:
            zone._touched_x[point] = False
        if fv._y != 0:
            zone._touched_y[point] = False

    @staticmethod
    def _do_shpix(ctx: ExecutionContext) -> None:
        """SHPIX moves points by a raw pixel amount along the freedom vector.

        Under backward compatibility (v40 grayscale) FreeType treats a
        glyph-zone SHPIX like DELTAP - it only moves points already touched in
        y, and never after IUP - because an unconditional SHPIX pushes
        untouched points off their interpolated positions; twilight-zone points
        are always moved.
        """
        gs = ctx._graphics_state
        st = ctx._stack
        amount = st.pop()
        zp2 = ctx.get_zone(gs._zp2)
        twilight = zp2 is ctx._twilight_zone
        for _ in range(gs._loop):
            point = st.pop()
            if twilight or _delta_point_allowed(ctx, zp2, point):
                ctx.move_point(zp2, point, amount)
        gs._loop = 1

    @staticmethod
    def _do_shp(ctx: ExecutionContext, use_rp1: bool) -> None:
        gs = ctx._graphics_state
        ref = gs._rp1 if use_rp1 else gs._rp2
        ref_zone = ctx.get_zone(gs._zp0 if use_rp1 else gs._zp1)
        shift = _reference_shift(ctx, ref_zone, ref)
        zp2 = ctx.get_zone(gs._zp2)
        same_zone = ref_zone is zp2
        st = ctx._stack
        move_point = ctx.move_point
        for _ in range(gs._loop):
            point = st.pop()
            if not (same_zone and point == ref):
                move_point(zp2, point, shift)
        gs._loop = 1

    @staticmethod
    def _do_shc(ctx: ExecutionContext, use_rp1: bool) -> None:
        gs = ctx._graphics_state
        ref = gs._rp1 if use_rp1 else gs._rp2
        ref_zone = ctx.get_zone(gs._zp0 if use_rp1 else gs._zp1)
        shift = _reference_shift(ctx, ref_zone, ref)
        contour = ctx._stack.pop()
        zp2 = ctx.get_zone(gs._zp2)
        ends = zp2._contour_ends
        # the twilight zone counts as a single contour of all its points (FreeType's Ins_SHC)
        twilight = zp2 is ctx._twilight_zone
        if contour < 0 or contour >= (1 if twilight else len(ends)):
            return
        start = 0 if contour == 0 else ends[contour - 1] + 1
        end = zp2._point_count - 1 if twilight else ends[contour]
        same_zone = ref_zone is zp2
        move_point = ctx.move_point
        for i in range(start, end + 1):
            # FreeType's SHC does not move the reference point itself (it has already moved)
            if not (same_zone and i == ref):
                move_point(zp2, i, shift)

    @staticmethod
    def _do_shz(ctx: ExecutionContext, use_rp1: bool) -> None:
        gs = ctx._graphics_state
        ref = gs._rp1 if use_rp1 else gs._rp2
        ref_zone = ctx.get_zone(gs._zp0 if use_rp1 else gs._zp1)
        shift = _reference_shift(ctx, ref_zone, ref)
        zone = ctx.get_zone(ctx._stack.pop())
        same_zone = ref_zone is zone
        move_point = ctx.move_point
        for i in range(zone._point_count):
            if not (same_zone and i == ref):
                move_point(zone, i, shift)

    @staticmethod
    def _make_mdrp(op: int) -> OpHandler:
        flags = op & 0x1F
        set_rp0 = (flags & 0x10) != 0
        use_min = (flags & 0x08) != 0
        round_ = (flags & 0x04) != 0

        def mdrp(ctx: ExecutionContext) -> None:
            gs = ctx._graphics_state
            point = ctx._stack.pop()
            zp1 = ctx.get_zone(gs._zp1)
            zp0 = ctx.get_zone(gs._zp0)
            rp0 = gs._rp0
            if not 0 <= point < zp1._point_count:
                ExecutionContext.check_point(zp1, point)
            if not 0 <= rp0 < zp0._point_count:
                ExecutionContext.check_point(zp0, rp0)

            if gs._zp0 == 0 or gs._zp1 == 0:
                # twilight points have no font-unit source: measure their scaled originals
                org_dist = ctx.dual_projected_distance(zp1, point, zp0, rp0)
            else:
                # measure in font units and scale the distance, as FreeType's Ins_MDRP does
                # (orus): projecting the individually rounded scaled originals can land a
                # half-pixel distance on the other side of the rounding threshold and move the
                # point by a whole pixel
                dx = zp1._unscaled_x[point] - zp0._unscaled_x[rp0]
                dy = zp1._unscaled_y[point] - zp0._unscaled_y[rp0]
                dist = ctx.dual_project(
                    dx if _INT_MIN <= dx <= _INT_MAX else _i32(dx),
                    dy if _INT_MIN <= dy <= _INT_MAX else _i32(dy),
                )
                # a composite's unscaled coordinates are already device positions (scale 1)
                org_dist = dist if ctx._composite else scale(dist, ctx._ppem, ctx._units_per_em)
            org_dist = _apply_single_width(gs, org_dist)
            distance = gs.round(org_dist) if round_ else org_dist
            if use_min:
                distance = _apply_minimum_distance(gs, org_dist, distance)

            cur_dist = ctx.projected_distance(zp1, point, zp0, rp0)
            ctx.move_point(zp1, point, distance - cur_dist)
            gs._rp1 = rp0
            gs._rp2 = point
            if set_rp0:
                gs._rp0 = point

        return mdrp

    @staticmethod
    def _make_mirp(op: int) -> OpHandler:
        flags = op & 0x1F
        set_rp0 = (flags & 0x10) != 0
        use_min = (flags & 0x08) != 0
        round_ = (flags & 0x04) != 0

        def mirp(ctx: ExecutionContext) -> None:
            gs = ctx._graphics_state
            st = ctx._stack
            # the CVT entry number is on top of the stack, the point number below it
            cvt_index = st.pop()
            point = st.pop()
            cvt = ctx._control_values
            cvt_value = cvt[cvt_index] if 0 <= cvt_index < len(cvt) else 0
            cvt_value = _apply_single_width(gs, cvt_value)

            zp1 = ctx.get_zone(gs._zp1)
            zp0 = ctx.get_zone(gs._zp0)
            rp0 = gs._rp0
            if not 0 <= point < zp1._point_count:
                ExecutionContext.check_point(zp1, point)
            if not 0 <= rp0 < zp0._point_count:
                ExecutionContext.check_point(zp0, rp0)
            if gs._zp1 == 0:
                # twilight point: place it the control value away from rp0's original position
                # along the freedom vector, as the MS rasterizer does (undocumented; FreeType's
                # Ins_MIRP)
                fv = ctx._fv
                zp1._original_x[point] = _i32(zp0._original_x[rp0] + mul14(cvt_value, fv._x))
                zp1._original_y[point] = _i32(zp0._original_y[rp0] + mul14(cvt_value, fv._y))
                zp1._current_x[point] = zp1._original_x[point]
                zp1._current_y[point] = zp1._original_y[point]
            org_dist = ctx.dual_projected_distance(zp1, point, zp0, rp0)

            # auto-flip the control value to match the sign of the original distance
            if gs._auto_flip and (org_dist ^ cvt_value) < 0:
                cvt_value = _i32(-cvt_value)
            if round_:
                # the control value cut-in only applies when both points are in the same zone
                if (
                    gs._zp0 == gs._zp1
                    and _abs32(cvt_value - org_dist) > gs._control_value_cut_in
                ):
                    cvt_value = org_dist
                distance = gs.round(cvt_value)
            else:
                distance = cvt_value
            if use_min:
                distance = _apply_minimum_distance(gs, org_dist, distance)

            cur_dist = ctx.projected_distance(zp1, point, zp0, rp0)
            ctx.move_point(zp1, point, distance - cur_dist)
            gs._rp1 = rp0
            gs._rp2 = point
            if set_rp0:
                gs._rp0 = point

        return mirp

    # --- interpolation ---------------------------------------------------

    def _install_interpolation_ops(self) -> None:
        d = self._dispatch
        do_iup = TrueTypeInterpreter._do_iup

        def iup_y(ctx: ExecutionContext) -> None:  # IUP[0] y
            do_iup(ctx, False)

        def iup_x(ctx: ExecutionContext) -> None:  # IUP[1] x
            do_iup(ctx, True)

        d[0x30] = iup_y
        d[0x31] = iup_x
        d[0x39] = TrueTypeInterpreter._do_ip  # IP

    @staticmethod
    def _do_iup(ctx: ExecutionContext, x_axis: bool) -> None:
        # record that IUP ran on this axis; under backward-compatibility, once both axes are done
        # the glyph is frozen against further y moves (see ExecutionContext.move_point) and further
        # IUPs do nothing (FreeType's Ins_IUP)
        if ctx._backward_compatibility and ctx._iupx_called and ctx._iupy_called:
            return
        if x_axis:
            ctx._iupx_called = True
        else:
            ctx._iupy_called = True
        # IUP always operates on the glyph zone, directly on the x or y coordinate
        zone = ctx.get_zone(1)
        if x_axis:
            cur = zone._current_x
            org = zone._original_x
            orus = zone._unscaled_x
            touched = zone._touched_x
        else:
            cur = zone._current_y
            org = zone._original_y
            orus = zone._unscaled_y
            touched = zone._touched_y
        start = 0
        point_count = zone._point_count
        for end in zone._contour_ends:
            if end >= point_count:
                # malformed contour data: upstream fails here with an index out of bounds
                raise HintingException(
                    f"IUP: contour end {end} out of range, zone has {point_count} points"
                )
            _interpolate_contour(cur, org, orus, touched, start, end)
            start = end + 1

    @staticmethod
    def _do_ip(ctx: ExecutionContext) -> None:
        gs = ctx._graphics_state
        z0 = ctx.get_zone(gs._zp0)
        z1 = ctx.get_zone(gs._zp1)
        z2 = ctx.get_zone(gs._zp2)
        rp1 = ExecutionContext.check_point(z0, gs._rp1)
        rp2 = ExecutionContext.check_point(z1, gs._rp2)
        # Measure the original positions in unscaled font units (FreeType's orus) so the
        # interpolation ratio keeps full precision; the scaled F26Dot6 originals round each
        # coordinate and can shift an interpolated point by a unit, which a later rounding opcode
        # then amplifies to a whole pixel. Exception: twilight-zone points have no font-unit
        # source, so their unscaled coordinates are (0,0); using them would collapse every
        # original distance to zero. When any zone here is the twilight zone, FreeType measures
        # the scaled originals instead, so we do the same.
        twilight = gs._zp0 == 0 or gs._zp1 == 0 or gs._zp2 == 0
        project = ctx.project
        dual_project = ctx.dual_project
        cur_rp1 = project(z0._current_x[rp1], z0._current_y[rp1])
        cur_rp2 = project(z1._current_x[rp2], z1._current_y[rp2])
        if twilight:
            org_rp1 = dual_project(z0._original_x[rp1], z0._original_y[rp1])
            org_rp2 = dual_project(z1._original_x[rp2], z1._original_y[rp2])
            src_x = z2._original_x
            src_y = z2._original_y
        else:
            org_rp1 = dual_project(z0._unscaled_x[rp1], z0._unscaled_y[rp1])
            org_rp2 = dual_project(z1._unscaled_x[rp2], z1._unscaled_y[rp2])
            src_x = z2._unscaled_x
            src_y = z2._unscaled_y
        org_range = org_rp2 - org_rp1
        if not _INT_MIN <= org_range <= _INT_MAX:
            org_range = _i32(org_range)
        cur_range = cur_rp2 - cur_rp1
        if not _INT_MIN <= cur_range <= _INT_MAX:
            cur_range = _i32(cur_range)
        cur_x = z2._current_x
        cur_y = z2._current_y
        count = z2._point_count
        st = ctx._stack
        move_point = ctx.move_point
        for _ in range(gs._loop):
            point = st.pop()
            if not 0 <= point < count:
                ExecutionContext.check_point(z2, point)
            org_p = dual_project(src_x[point], src_y[point])
            cur_p = project(cur_x[point], cur_y[point])
            if org_range == 0:
                new_p = cur_rp1 + (org_p - org_rp1)
            else:
                delta = org_p - org_rp1
                if not _INT_MIN <= delta <= _INT_MAX:
                    delta = _i32(delta)
                new_p = cur_rp1 + mul_div(delta, cur_range, org_range)
            move_point(z2, point, new_p - cur_p)
        gs._loop = 1

    # --- measurement -----------------------------------------------------

    def _install_measure_ops(self) -> None:
        d = self._dispatch

        def gc_cur(ctx: ExecutionContext) -> None:  # GC[0] current
            zone = ctx.get_zone(ctx._graphics_state._zp2)
            st = ctx._stack
            point = ExecutionContext.check_point(zone, st.pop())
            st.append(ctx.project(zone._current_x[point], zone._current_y[point]))

        def gc_org(ctx: ExecutionContext) -> None:  # GC[1] original
            zone = ctx.get_zone(ctx._graphics_state._zp2)
            st = ctx._stack
            point = ExecutionContext.check_point(zone, st.pop())
            st.append(ctx.dual_project(zone._original_x[point], zone._original_y[point]))

        def scfs(ctx: ExecutionContext) -> None:  # SCFS
            st = ctx._stack
            value = st.pop()
            point = st.pop()
            zone = ctx.get_zone(ctx._graphics_state._zp2)
            ExecutionContext.check_point(zone, point)
            cur = ctx.project(zone._current_x[point], zone._current_y[point])
            ctx.move_point(zone, point, value - cur)

        def md_grid(ctx: ExecutionContext) -> None:  # MD[0] grid-fitted
            gs = ctx._graphics_state
            st = ctx._stack
            p2 = st.pop()
            p1 = st.pop()
            zp0 = ctx.get_zone(gs._zp0)
            zp1 = ctx.get_zone(gs._zp1)
            # FreeType measures project(zp0[p1] - zp1[p2]); p1 is the deeper operand, p2 the top
            st.append(ctx.projected_distance(zp0, p1, zp1, p2))

        def md_org(ctx: ExecutionContext) -> None:  # MD[1] original
            gs = ctx._graphics_state
            st = ctx._stack
            p2 = st.pop()
            p1 = st.pop()
            zp0 = ctx.get_zone(gs._zp0)
            zp1 = ctx.get_zone(gs._zp1)
            st.append(ctx.dual_projected_distance(zp0, p1, zp1, p2))

        d[0x46] = gc_cur
        d[0x47] = gc_org
        d[0x48] = scfs
        d[0x49] = md_grid
        d[0x4A] = md_org

    # --- delta exceptions ------------------------------------------------

    def _install_delta_ops(self) -> None:
        d = self._dispatch

        def make_deltap(band: int) -> OpHandler:
            def deltap(ctx: ExecutionContext) -> None:
                gs = ctx._graphics_state
                zone = ctx.get_zone(gs._zp0)
                st = ctx._stack
                n = st.pop()
                ppem = ctx._ppem
                for _ in range(n):
                    point = st.pop()
                    arg = st.pop()
                    if _delta_target_ppem(gs, arg, band) == ppem and _delta_point_allowed(
                        ctx, zone, point
                    ):
                        ctx.move_point(zone, point, _decode_delta(arg & 0x0F, gs._delta_shift))

            return deltap

        def make_deltac(band: int) -> OpHandler:
            def deltac(ctx: ExecutionContext) -> None:
                gs = ctx._graphics_state
                cvt = ctx._control_values
                st = ctx._stack
                n = st.pop()
                ppem = ctx._ppem
                for _ in range(n):
                    cvt_index = st.pop()
                    arg = st.pop()
                    if _delta_target_ppem(gs, arg, band) == ppem and 0 <= cvt_index < len(cvt):
                        cvt[cvt_index] = _i32(
                            cvt[cvt_index] + _decode_delta(arg & 0x0F, gs._delta_shift)
                        )

            return deltac

        d[0x5D] = make_deltap(0)  # DELTAP1
        d[0x71] = make_deltap(1)  # DELTAP2
        d[0x72] = make_deltap(2)  # DELTAP3
        d[0x73] = make_deltac(0)  # DELTAC1
        d[0x74] = make_deltac(1)  # DELTAC2
        d[0x75] = make_deltac(2)  # DELTAC3

    # --- flip and scan-conversion ----------------------------------------

    def _install_flip_ops(self) -> None:
        d = self._dispatch

        def flipon(ctx: ExecutionContext) -> None:  # FLIPON
            ctx._graphics_state._auto_flip = True

        def flipoff(ctx: ExecutionContext) -> None:  # FLIPOFF
            ctx._graphics_state._auto_flip = False

        def flippt(ctx: ExecutionContext) -> None:  # FLIPPT
            glyph = ctx.get_zone(1)
            on_curve = glyph._on_curve
            gs = ctx._graphics_state
            st = ctx._stack
            for _ in range(gs._loop):
                point = ExecutionContext.check_point(glyph, st.pop())
                on_curve[point] = not on_curve[point]
            gs._loop = 1

        def fliprgon(ctx: ExecutionContext) -> None:  # FLIPRGON
            TrueTypeInterpreter._flip_range(ctx, True)

        def fliprgoff(ctx: ExecutionContext) -> None:  # FLIPRGOFF
            TrueTypeInterpreter._flip_range(ctx, False)

        def scanctrl(ctx: ExecutionContext) -> None:  # SCANCTRL
            ctx._graphics_state._scan_control = ctx._stack.pop()

        def scantype(ctx: ExecutionContext) -> None:  # SCANTYPE
            ctx._graphics_state._scan_type = ctx._stack.pop()

        d[0x4D] = flipon
        d[0x4E] = flipoff
        d[0x80] = flippt
        d[0x81] = fliprgon
        d[0x82] = fliprgoff
        d[0x85] = scanctrl
        d[0x8D] = scantype
        d[0x8E] = TrueTypeInterpreter._do_instctrl  # INSTCTRL

    @staticmethod
    def _do_instctrl(ctx: ExecutionContext) -> None:
        """INSTCTRL, after FreeType's Ins_INSTCTRL.

        The selector is an index 1..3 naming one flag bit, and the value must
        be 0 or that bit. In ``prep`` it sets or clears the bit in the graphics
        state, which ``GlyphHinter`` reads before each glyph: bit 1 turns
        hinting off, bit 2 makes glyph programs start from the default graphics
        state, bit 4 waives v40 backward compatibility. A glyph program may
        only use selector 3, to waive (or restore) backward compatibility for
        itself - native-ClearType fonts do that per glyph. Anything else is
        ignored.
        """
        st = ctx._stack
        selector = st.pop()
        value = st.pop()
        if selector < 1 or selector > 3:
            return
        flag = 1 << (selector - 1)
        if value != 0 and value != flag:
            return
        if ctx._code_range is _CONTROL_VALUE:
            gs = ctx._graphics_state
            gs._instruct_control = (gs._instruct_control & ~flag) | value
        elif ctx._code_range is _GLYPH and selector == 3:
            ctx._backward_compatibility = value == 0

    @staticmethod
    def _flip_range(ctx: ExecutionContext, on_curve: bool) -> None:
        flags = ctx.get_zone(1)._on_curve
        st = ctx._stack
        high = st.pop()
        low = st.pop()
        for i in range(max(low, 0), min(high + 1, len(flags))):
            flags[i] = on_curve


# --- module-level helpers (upstream's private static methods) ---------------


def _rounded_quotient(a: int, b: int, c: int) -> int:
    """``a * b / c`` rounded to the nearest integer, halves away from zero, without overflow."""
    product = a * b
    divisor = abs(c)
    q, r = divmod(abs(product), divisor)
    if 2 * r >= divisor:
        q += 1
    return -q if (product < 0) != (c < 0) and product != 0 else q


def _reference_shift(ctx: ExecutionContext, ref_zone: Zone, ref: int) -> int:
    """The projected distance the reference point (rp1 in zp0, or rp2 in zp1) has been moved."""
    ExecutionContext.check_point(ref_zone, ref)
    dx = ref_zone._current_x[ref] - ref_zone._original_x[ref]
    dy = ref_zone._current_y[ref] - ref_zone._original_y[ref]
    return ctx.project(
        dx if _INT_MIN <= dx <= _INT_MAX else _i32(dx),
        dy if _INT_MIN <= dy <= _INT_MAX else _i32(dy),
    )


def _apply_single_width(gs: GraphicsState, distance: int) -> int:
    swv = gs._single_width_value
    if _abs32(distance - swv) < gs._single_width_cut_in:
        return swv if distance >= 0 else _i32(-swv)
    return distance


def _apply_minimum_distance(gs: GraphicsState, org_dist: int, distance: int) -> int:
    md = gs._minimum_distance
    if org_dist >= 0:
        return max(distance, md)
    neg_md = _i32(-md)
    return min(distance, neg_md)


def _delta_point_allowed(ctx: ExecutionContext, zone: Zone, point: int) -> bool:
    """Backward-compatibility (v40 grayscale) gate shared by DELTAP and SHPIX.

    Once IUP has run the move is dropped, and before IUP it is applied only to
    points already touched in y (or, for composites, when the freedom vector
    has a y component). Outside backward-compatibility mode the move always
    applies. This keeps DELTAP/SHPIX from nudging untouched points off their
    interpolated grayscale positions (FreeType Ins_DELTAP / Ins_SHPIX).
    """
    if not ctx._backward_compatibility:
        return True
    if ctx._iupx_called and ctx._iupy_called:
        return False
    touched_y = 0 <= point < len(zone._touched_y) and zone._touched_y[point]
    return touched_y or (ctx._composite and ctx._fv._y != 0)


def _delta_target_ppem(gs: GraphicsState, arg: int, band: int) -> int:
    v = ((arg >> 4) & 0x0F) + gs._delta_base + band * 16
    return v if _INT_MIN <= v <= _INT_MAX else _i32(v)


def _decode_delta(steps: int, delta_shift: int) -> int:
    relative = steps - 8 if steps < 8 else steps - 7  # 0..15 -> -8..-1, 1..8
    unit = ONE >> (delta_shift & 31)  # 1 / 2^deltaShift of a pixel (Java masks the shift count)
    return relative * unit


def _interpolate_contour(
    cur: list[int], org: list[int], orus: list[int], touched: list[bool], start: int, end: int
) -> None:
    """Interpolates the untouched points of one contour, after FreeType's Ins_IUP.

    A single touched point shifts the whole contour by its movement;
    otherwise each run of untouched points between two touched ones is
    shifted by the nearer one's movement when it lies outside their original
    span, and interpolated between them when inside - by the unscaled
    (font-unit) coordinates.
    """
    if end < start:
        return
    touched_points = [i for i in range(start, end + 1) if touched[i]]
    count = len(touched_points)
    if count == 0:
        return
    if count == 1:
        first = touched_points[0]
        delta = cur[first] - org[first]
        if not _INT_MIN <= delta <= _INT_MAX:
            delta = _i32(delta)
        if delta != 0:
            for i in range(start, end + 1):
                if i != first:
                    v = cur[i] + delta
                    cur[i] = v if _INT_MIN <= v <= _INT_MAX else _i32(v)
        return
    # walk the contour cyclically from the first touched point, interpolating the untouched run
    # between each touched pair (the last pair wraps around to the first touched point)
    prev = touched_points[-1]
    for t in touched_points:
        _interpolate_run(cur, org, orus, prev, t, start, end)
        prev = t


def _interpolate_run(
    cur: list[int], org: list[int], orus: list[int], frm: int, to: int, start: int, end: int
) -> None:
    """Places the untouched points between two touched points, walking forward from ``frm``.

    As the TrueType specification describes for IUP: a point whose original
    coordinate lies between the two touched points' originals keeps its
    relative position between them, measured on the unscaled (font unit)
    outline for precision; a point outside that range moves by the same amount
    as the touched point on its side. The ratio of the hinted to the
    font-unit span is held in 16.16 fixed point, the precision FreeType
    interpolates at, so results agree with it to the 1/64 px.
    """
    if frm + 1 == to or (to == start and frm == end):
        return  # no points between them
    # the touched point lower in the outline, and the one higher; on a tie, the first one
    if orus[frm] <= orus[to]:
        lower = frm
        upper = to
    else:
        lower = to
        upper = frm
    orus_lower = orus[lower]
    font_unit_span = orus[upper] - orus_lower
    if not _INT_MIN <= font_unit_span <= _INT_MAX:
        font_unit_span = _i32(font_unit_span)
    cur_lower = cur[lower]
    cur_upper = cur[upper]
    org_lower = org[lower]
    org_upper = org[upper]
    shift_lower = cur_lower - org_lower
    shift_upper = cur_upper - org_upper
    if font_unit_span == 0:
        ratio = 0
    else:
        cur_span = cur_upper - cur_lower
        if _INT_MIN <= cur_span <= _INT_MAX and font_unit_span > 0:
            # div_fix inlined for the common positive span
            if cur_span >= 0:
                ratio = ((cur_span << 16) + (font_unit_span >> 1)) // font_unit_span
            else:
                ratio = -(((-cur_span << 16) + (font_unit_span >> 1)) // font_unit_span)
            if not _INT_MIN <= ratio <= _INT_MAX:
                ratio = _i32(ratio)
        else:
            ratio = div_fix(_i32(cur_span), font_unit_span)
    # the untouched points strictly between, wrapping round the end of the contour
    points = range(frm + 1, to) if frm < to else chain(range(frm + 1, end + 1), range(start, to))
    for i in points:
        o = org[i]
        if o <= org_lower:
            v = o + shift_lower
        elif o >= org_upper:
            v = o + shift_upper
        elif font_unit_span == 0:
            v = cur_lower
        else:
            # cur[lower] + FT_MulFix(orus[i] - orus[lower], ratio), rounding half away from zero
            p = (orus[i] - orus_lower) * ratio
            v = cur_lower + ((p + 0x8000) >> 16) if p >= 0 else cur_lower - ((0x8000 - p) >> 16)
        cur[i] = v if _INT_MIN <= v <= _INT_MAX else _i32(v)


__all__ = ["TrueTypeInterpreter"]
